"""Create missing Shopify client files once, preserving ambiguous identities for review."""
import json,re
from shopify_pending import full_name,order_number_client

def create_missing(c,records,clean_phone,amount,stamp):
    def safe_phone(value):
        try:return clean_phone(value)
        except ValueError:return ''
    created=0;added=0
    codes=[int(r[0]) for r in c.execute('SELECT code FROM client_codes') if re.fullmatch(r'\d+',str(r[0]))]
    code=max(codes,default=0)
    generated={r[0] for r in c.execute("SELECT client_id FROM orders WHERE source='shopify_confirmed_new'")}
    for r in records:
        if r.get('client_id'):continue
        if r.get('financial_status') not in ('PENDING','PARTIALLY_PAID'):continue
        try:
            total=amount(r['total']);pending=amount(r['outstanding']);p=clean_phone(r.get('phone'))
        except (ValueError,KeyError,TypeError):continue
        if not 0<pending<=total:continue
        sid=r.get('customer_id') or None;email=str(r.get('email') or '').strip().lower()
        name=str(r.get('client_name') or '').strip()
        if not name or full_name(name)=='sin nombre informado' or not (sid or p or email):continue
        numbered,has_number=order_number_client(c,r.get('number'))
        clients=[dict(x) for x in c.execute('SELECT * FROM clients')]
        candidates=[x for x in clients if (sid and x['shopify_id']==sid) or (p and safe_phone(x['phone'])==p) or (email and str(x['email'] or '').lower()==email)]
        named=[x for x in clients if full_name(x['name'])==full_name(name)]
        if has_number:
            if not numbered:continue
            cid=numbered
        elif candidates:
            if len(candidates)!=1:continue
            x=candidates[0]
            if sid and x['shopify_id'] and sid!=x['shopify_id']:continue
            cid=x['id']
        elif named:
            # A name-only collision needs explicit human linkage.
            continue
        else:
            cid=c.execute('INSERT INTO clients(name,phone,email,shopify_id,notes) VALUES(?,?,?,?,?)',(name,p,email,sid,'Ficha creada desde Shopify')).lastrowid
            code+=1
            work=' · '.join(str(t) for t in r.get('tags',[]) if str(t).strip())
            c.execute('INSERT INTO client_codes VALUES(?,?,?,?)',(str(code),cid,work,str(r.get('phone') or '')))
            generated.add(cid);created+=1
        r.update(client_id=cid,match='contact')
        if cid not in generated:continue
        key=str(r.get('number') or '').strip().lstrip('#').strip()
        if not key:continue
        if c.execute("SELECT 1 FROM orders WHERE shopify_id=? OR trim(ltrim(trim(number),'#'))=?",(r['shopify_id'],key)).fetchone():continue
        if c.execute("SELECT 1 FROM purchase_history WHERE trim(ltrim(trim(number),'#'))=?",(key,)).fetchone():continue
        remote=json.dumps({'total':total,'outstanding':pending,'cancelled':None,'items':r['items']},sort_keys=True,ensure_ascii=False)
        c.execute("INSERT INTO orders(client_id,shopify_id,number,purchased,total,base_paid,items,source,status,remote,updated) VALUES(?,?,?,?,?,?,?,'shopify_confirmed_new','active',?,?)",(cid,r['shopify_id'],r['number'],r['purchased'],total,total-pending,json.dumps(r['items'],ensure_ascii=False),remote,stamp))
        added+=1
    return {'clients_created':created,'purchases_added':added}

def incorporate_review_pending(c,records,reviews,amount,stamp):
    """Explicitly authorized pending reviews: add each unregistered order once."""
    added=0
    for r in records:
        review=next((x for x in reviews if x['shopify_id']==r['shopify_id']),None)
        if not review:continue
        old=c.execute("SELECT * FROM orders WHERE shopify_id=?",(r['shopify_id'],)).fetchone()
        if old:
            if old['source'] in ('shopify_confirmed','shopify_confirmed_new') and old['client_id']==r.get('client_id'):
                review.update(status='reviewed',note='Compra incorporada a la deuda de la clienta.',reviewed_at=stamp)
            continue
        if review.get('kind')!='new' or review.get('fingerprint')!=r.get('fingerprint'):continue
        if r.get('financial_status') not in ('PENDING','PARTIALLY_PAID'):continue
        cid=r.get('client_id')
        if not cid or not c.execute('SELECT 1 FROM clients WHERE id=?',(cid,)).fetchone():continue
        try:total=amount(r['total']);pending=amount(r['outstanding'])
        except (ValueError,KeyError,TypeError):continue
        if not 0<pending<=total:continue
        key=str(r.get('number') or '').strip().lstrip('#').strip()
        if not key:continue
        if c.execute("SELECT 1 FROM orders WHERE trim(ltrim(trim(number),'#'))=?",(key,)).fetchone():continue
        if c.execute("SELECT 1 FROM purchase_history WHERE trim(ltrim(trim(number),'#'))=? AND kind='purchase'",(key,)).fetchone():continue
        remote=json.dumps({'total':total,'outstanding':pending,'cancelled':None,'items':r['items']},sort_keys=True,ensure_ascii=False)
        oid=c.execute("INSERT INTO orders(client_id,shopify_id,number,purchased,total,base_paid,items,source,status,remote,updated) VALUES(?,?,?,?,?,?,?,'shopify_confirmed','active',?,?)",(cid,r['shopify_id'],r['number'],r['purchased'],total,total-pending,json.dumps(r['items'],ensure_ascii=False),remote,stamp)).lastrowid
        c.execute('INSERT INTO audit(event,data,created) VALUES(?,?,?)',('shopify_review_debt_added',json.dumps({'order_id':oid,'client_id':cid,'shopify_id':r['shopify_id'],'added_balance':pending}),stamp))
        review.update(status='reviewed',note='Compra incorporada a la deuda de la clienta.',reviewed_at=stamp)
        added+=1
    return added
