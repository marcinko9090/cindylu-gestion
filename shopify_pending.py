"""Read-only Shopify pending orders; Excel remains the authority for payments."""
import hashlib
import json
from decimal import Decimal, InvalidOperation
from shopify_review import shopify_items

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def pending_record(c,order,clean_phone,stamp,links):
    if order.get('cancelledAt') or order.get('displayFinancialStatus') not in ('PENDING','PARTIALLY_PAID'):
        return None
    values=[]
    for field in ('currentTotalPriceSet','totalOutstandingSet'):
        money=order.get(field,{}).get('shopMoney',{})
        try:
            n=Decimal(str(money.get('amount')))
            if money.get('currencyCode')!='CLP' or not n.is_finite() or n!=int(n) or not 0<=n<=10**11:return None
        except (InvalidOperation,ValueError,TypeError):return None
        values.append(int(n))
    total,outstanding=values
    if not 0<outstanding<=total:return None
    customer=order.get('customer') or {};shipping=order.get('shippingAddress') or {}
    sid=customer.get('id') or ''
    try:phone=clean_phone(customer.get('phone') or shipping.get('phone'))
    except ValueError:phone=''
    email=str(customer.get('email') or '').strip().lower()
    name=customer.get('displayName') or ' '.join(filter(None,[shipping.get('firstName'),shipping.get('lastName')])) or 'Sin nombre informado'
    identity=digest([sid,phone,email,name])
    candidates=[]
    for client in c.execute('SELECT id,name,shopify_id,phone,email FROM clients'):
        try:local_phone=clean_phone(client['phone'])
        except ValueError:local_phone=''
        if sid and client['shopify_id'] and sid!=client['shopify_id']:continue
        if phone and local_phone and phone!=local_phone:continue
        if (sid and sid==client['shopify_id']) or (phone and phone==local_phone) or (email and email==str(client['email'] or '').strip().lower()):
            candidates.append(client['id'])
    client_id=candidates[0] if len(candidates)==1 else None
    match='contact' if client_id else ''
    manual=links.get(order['id'],{})
    if manual.get('identity')==identity and c.execute('SELECT 1 FROM clients WHERE id=?',(manual.get('client_id'),)).fetchone():
        client_id=manual['client_id'];match='manual'
    numeric=str(order['id']).rsplit('/',1)[-1]
    return {'shopify_id':order['id'],'number':str(order.get('name') or ''),'purchased':order.get('createdAt',''),
            'client_name':name,'customer_id':sid,'phone':phone,'email':email,'identity':identity,
            'client_id':client_id,'match':match,'items':shopify_items(order),'total':total,'outstanding':outstanding,
            'financial_status':order['displayFinancialStatus'],'last_seen':stamp,'fingerprint':digest(order),
            'shopify_numeric_id':numeric if numeric.isdigit() else ''}
