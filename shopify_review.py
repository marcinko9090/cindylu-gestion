"""Review metadata only. This module never writes debts or payments."""
import hashlib
import json
from decimal import Decimal, InvalidOperation

def review_record(c, order, outcome, error, stamp, balance):
    def money(field):
        m=order.get(field,{}).get('shopMoney',{})
        return str(m.get('amount','')),str(m.get('currencyCode',''))
    total,currency=money('currentTotalPriceSet');outstanding,_=money('totalOutstandingSet')
    negative=False
    for v in (total,outstanding):
        try:negative=negative or (Decimal(v).is_finite() and Decimal(v)<0)
        except InvalidOperation:pass
    kind='negative' if negative else 'amount' if error else 'new' if outcome=='pending' else 'difference'
    number=str(order.get('name') or '')
    matches=c.execute("SELECT * FROM orders WHERE shopify_id=? OR trim(ltrim(trim(number),'#'))=?",
                      (order['id'],number.strip().lstrip('#').strip())).fetchall()
    reason=str(error) if error else 'Pedido nuevo: falta confirmar si fue al contado o fiado y sus abonos.'
    if negative:reason='Shopify informa un monto negativo. Revisa los pagos, las ediciones de productos y cualquier reembolso pendiente.'
    local=None
    if outcome=='conflict' and not error:
        if len(matches)>1:reason='Hay varios registros locales con este número de pedido.'
        elif matches:
            local=dict(matches[0])
            if order.get('cancelledAt'):reason='El pedido figura anulado en Shopify.'
            elif str(local['total'])!=total and Decimal(total)!=local['total']:reason='El total de Shopify y el total registrado aquí son diferentes.'
            else:reason='Revisar la identidad de la clienta, el vínculo o los cambios de productos y pagos en Shopify.'
        else:reason='No se pudo vincular este pedido con seguridad.'
    if len(matches)==1:local=dict(matches[0])
    customer=order.get('customer') or {};shipping=order.get('shippingAddress') or {}
    label=customer.get('displayName') or ' '.join(filter(None,[shipping.get('firstName'),shipping.get('lastName')])) or 'Sin nombre informado'
    fingerprint=hashlib.sha256(json.dumps(order,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    numeric_id=str(order['id']).rsplit('/',1)[-1]
    return {'shopify_id':order['id'],'fingerprint':fingerprint,'number':number,'purchased':order.get('createdAt',''),
            'client_name':label,'total':total,'outstanding':outstanding,'currency':currency,'kind':kind,'reason':reason,
            'local_order_id':local['id'] if local else None,'client_id':local['client_id'] if local else None,
            'local_total':local['total'] if local else None,'local_balance':balance(c,local['id']) if local else None,
            'shopify_numeric_id':numeric_id if numeric_id.isdigit() else '',
            'last_seen':stamp,'status':'pending','note':''}

def merge_review_records(previous, current, completed):
    previous={r['shopify_id']:r for r in previous}
    merged={k:v for k,v in previous.items() if k not in completed}
    for row in current:
        old=previous.get(row['shopify_id'])
        if old and old['fingerprint']==row['fingerprint']:
            for field in ('status','note','reviewed_at','reviewed_by','previous_note'):
                if field in old:row[field]=old[field]
        elif old and (old.get('note') or old.get('previous_note')):
            row['previous_note']=old.get('note') or old['previous_note']
        merged[row['shopify_id']]=row
    return list(merged.values())
