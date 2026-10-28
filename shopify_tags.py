"""Customer tags classify local fichas without changing Excel contact or financial data."""
import time
from collections import defaultdict

QUERY='''query CustomerTags($cursor:String){customers(first:100,after:$cursor){pageInfo{hasNextPage endCursor} nodes{id displayName phone email tags}}}'''

def fetch_customers(request):
    cursor=None;customers=[];seen=set()
    while True:
        result=request(QUERY,{'cursor':cursor})
        for attempt in range(2):
            errors=result.get('errors') or []
            if not errors or not all(e.get('extensions',{}).get('code')=='THROTTLED' for e in errors):break
            time.sleep(2*(attempt+1));result=request(QUERY,{'cursor':cursor})
        if result.get('errors') or not isinstance(result.get('data',{}).get('customers'),dict):
            raise ValueError('No se pudieron consultar las etiquetas. Verifica el permiso read_customers de Shopify.')
        page=result['data']['customers'];customers.extend(page['nodes'])
        if not page['pageInfo']['hasNextPage']:return customers
        next_cursor=page['pageInfo'].get('endCursor')
        if not next_cursor or next_cursor in seen:raise ValueError('Shopify no completó la consulta de etiquetas. Intenta actualizar otra vez.')
        seen.add(next_cursor);cursor=next_cursor
        cost=result.get('extensions',{}).get('cost',{});throttle=cost.get('throttleStatus',{})
        remaining=throttle.get('currentlyAvailable',1000);rate=throttle.get('restoreRate',50)
        wait=max(0,(cost.get('requestedQueryCost',101)-remaining)/max(1,rate))
        if wait:time.sleep(min(wait,10))

def classify(c,customers,clean_phone,pending):
    clients={r['id']:dict(r) for r in c.execute('SELECT id,shopify_id,phone,email FROM clients')}
    by_id=defaultdict(set);by_phone=defaultdict(set);by_email=defaultdict(set)
    def phone(value):
        try:return clean_phone(value)
        except ValueError:return ''
    for cid,cl in clients.items():
        if cl['shopify_id']:by_id[cl['shopify_id']].add(cid)
        cl['normalized_phone']=phone(cl['phone'])
        if cl['normalized_phone']:by_phone[cl['normalized_phone']].add(cid)
        if cl['email']:by_email[cl['email'].strip().lower()].add(cid)
    manual=defaultdict(set)
    for r in pending:
        if r.get('match')=='manual' and r.get('customer_id') and r.get('client_id') in clients:
            manual[r['customer_id']].add(r['client_id'])
    found=defaultdict(dict)
    for customer in customers:
        sid=customer['id'];p=phone(customer.get('phone'));email=str(customer.get('email') or '').strip().lower()
        candidates=manual.get(sid) or by_id.get(sid) or (by_phone.get(p,set())|by_email.get(email,set()))
        valid=[]
        for cid in candidates:
            cl=clients[cid]
            if not manual.get(sid):
                if cl['shopify_id'] and cl['shopify_id']!=sid:continue
                if p and cl['normalized_phone'] and p!=cl['normalized_phone']:continue
            valid.append(cid)
        if len(valid)!=1:continue
        tags=list(dict.fromkeys(t.strip()[:255] for t in customer.get('tags',[]) if isinstance(t,str) and t.strip()))
        found[valid[0]][sid]={'customer_id':sid,'tags':tags}
    # Do not choose between different Shopify identities that share a local phone/email.
    return {str(cid):next(iter(records.values())) for cid,records in found.items() if len(records)==1}
