"""Estado de cuenta: productos pendientes de Shopify, abonos reales y saldo local, sin duplicar deuda."""
import io,json,datetime as dt
from zoneinfo import ZoneInfo
from pathlib import Path
from html import escape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.lib.enums import TA_LEFT,TA_RIGHT
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,KeepTogether,Image
from reportlab.lib.pagesizes import A4

LOGO=Path(__file__).resolve().parent/'static'/'logo.png'

def snapshot(c,cid,balance,issued):
    cl=c.execute('SELECT * FROM clients WHERE id=?',(cid,)).fetchone()
    if not cl:raise ValueError('Clienta no encontrada.')
    orders=[]
    for row in c.execute("SELECT * FROM orders WHERE client_id=? AND status='active' ORDER BY purchased,id",(cid,)):
        o=dict(row);o['balance']=balance(c,o['id'])
        if o['balance']<=0:continue
        o['items']=json.loads(o['items'])
        o['payments']=[dict(p) for p in c.execute('SELECT * FROM payments WHERE order_id=? AND reversed=0 ORDER BY date,id',(o['id'],))]
        ins=[dict(i) for i in c.execute('''SELECT i.*, COALESCE((SELECT SUM(a.amount) FROM allocations a JOIN payments p ON p.id=a.payment_id WHERE a.installment_id=i.id AND p.reversed=0),0) paid FROM installments i WHERE order_id=? ORDER BY number''',(o['id'],))]
        for i in ins:
            i['allocations']=[dict(a) for a in c.execute('''SELECT a.amount, p.date, p.method FROM allocations a JOIN payments p ON p.id=a.payment_id WHERE a.installment_id=? AND p.reversed=0 ORDER BY p.date, p.id''',(i['id'],))]
        o['installments']=ins
        orders.append(o)
    cfg={r['key']:json.loads(r['value']) for r in c.execute('SELECT key,value FROM settings')}
    shopify_orders=[{k:r.get(k) for k in ('shopify_id','number','purchased','items','total','financial_status')}
                    for r in cfg.get('shopify_pending_orders',[]) if r.get('client_id')==cid]
    shopify_orders.sort(key=lambda r:(str(r['purchased']),str(r['number'])))
    # All active-account payments, including payments that closed a purchase. Archived imports stay excluded.
    history=[{'date':r['date'],'amount':r['amount'],'kind':'payment','method':r['method']}
             for r in c.execute("SELECT p.* FROM payments p JOIN orders o ON o.id=p.order_id WHERE o.client_id=? AND o.status='active' AND p.reversed=0 ORDER BY p.date,p.id",(cid,))]
    for r in c.execute('SELECT date,amount,kind FROM cxc_payment_history WHERE client_id=? AND current=0 ORDER BY date,key',(cid,)):
        history.append({'date':r['date'],'amount':r['amount'],'kind':r['kind'],'method':''})
    for r in c.execute("SELECT base_paid FROM orders WHERE client_id=? AND status='active' AND base_paid>0",(cid,)):
        history.append({'date':'','amount':r['base_paid'],'kind':'prior','method':''})
    history.sort(key=lambda r:(r['date'] or '9999',r['amount'],r['kind']))
    return dict(client=dict(cl),orders=orders,shopify_orders=shopify_orders,payment_history=history,issued=issued,total=sum(o['total'] for o in orders),paid=sum(o['total']-o['balance'] for o in orders),balance=sum(o['balance'] for o in orders))

def pdf(data):
    buf=io.BytesIO();styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name='Muted',fontName='Helvetica',fontSize=8.5,leading=12,textColor=colors.HexColor('#665e52')))
    styles.add(ParagraphStyle(name='Gold',parent=styles['Heading2'],textColor=colors.HexColor('#966c20'),spaceAfter=4))
    styles.add(ParagraphStyle(name='DocTitle',parent=styles['Title'],alignment=TA_LEFT,fontSize=22,leading=26,spaceAfter=6,textColor=colors.HexColor('#292821')))
    styles.add(ParagraphStyle(name='ClientName',parent=styles['Heading2'],fontSize=14,leading=18,spaceBefore=2,spaceAfter=4,textColor=colors.HexColor('#292821')))
    styles.add(ParagraphStyle(name='Money',parent=styles['Muted'],fontName='Helvetica-Bold',alignment=TA_RIGHT,fontSize=9,leading=13))
    p=lambda s,style='BodyText':Paragraph(escape(str(s)),styles[style])
    money=lambda n:'$'+format(n,',').replace(',','.')
    def date(s):
        text=str(s or '')
        if 'T' in text:
            try:text=dt.datetime.fromisoformat(text.replace('Z','+00:00')).astimezone(ZoneInfo('America/Santiago')).date().isoformat()
            except ValueError:pass
        text=text[:10];return '/'.join(reversed(text.split('-'))) if text else 'Sin fecha registrada'
    head_left=[p('CINDY LÚ · TIENDA','Gold'),p('Estado de cuenta','DocTitle'),p(data['client']['name'],'ClientName'),p('Emitido: '+data['issued']+' · Moneda: pesos chilenos (CLP)','Muted')]
    if LOGO.is_file():
        logo=Image(str(LOGO),width=112,height=94,mask='auto')
        logo.hAlign='RIGHT'
        header=Table([[head_left,logo]],colWidths=[370,125],hAlign='LEFT')
        header.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE'),('ALIGN',(1,0),(1,0),'RIGHT'),('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0),('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),2)]))
        story=[header,Spacer(1,8)]
    else:
        story=head_left+[Spacer(1,10)]
    def table(rows,widths):
        t=Table([[p(v,'Money' if str(v).startswith('$') else 'Muted') for v in r] for r in rows],colWidths=widths,repeatRows=1,hAlign='LEFT')
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#f3e8ce')),('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,0),.7,colors.HexColor('#c6a159')),('LINEBELOW',(0,1),(-1,-1),.3,colors.HexColor('#e8e3da')),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]));return t
    story += [table([['Saldo de deuda actual'],[money(data['balance'])]],[495]),Spacer(1,12)]
    remote=data.get('shopify_orders',[])
    def norm_number(n):return str(n or '').strip().lstrip('#')
    local=[o for o in data['orders'] if o['source']!='cxc' and not any(
           (o.get('shopify_id') and o['shopify_id']==r.get('shopify_id')) or
           (norm_number(o['number'])==norm_number(r['number']) and o['total']==r['total']) for r in remote)]
    if remote:story.append(p('Productos con pago pendiente en Shopify','Gold'))
    for o in remote+local:
        title=str(o['number'])+' - '+data['client']['name']
        when=o.get('purchased','')
        status=('Pago parcial en Shopify' if o.get('financial_status')=='PARTIALLY_PAID' else 'Pago pendiente en Shopify') if o in remote else 'Compra registrada'
        intro=[p(title,'Heading3'),p(date(when)+' - '+status,'Muted')]
        items=o.get('items') or []
        # Keep the heading with at least one product, then allow long orders to flow across pages.
        if items:intro.append(p(str(items[0].get('quantity',1))+' x '+str(items[0].get('title','Artículo'))))
        story.append(KeepTogether(intro))
        for item in items[1:]:story.append(p(str(item.get('quantity',1))+' x '+str(item.get('title','Artículo'))))
        if not items:story.append(p('Detalle de productos pendiente de vinculación.','Muted'))
        story += [p('Total de la compra: '+money(o['total']),'Heading3'),Spacer(1,9)]
    if not remote and not local:
        story.append(p('No hay pedidos vinculados para detallar sus productos.','Muted'))
    if remote:
        story.append(p('Los productos corresponden a los pedidos vinculados de Shopify. El saldo actual corresponde a la cuenta registrada y no suma estos pedidos nuevamente.','Muted'))
    history=data.get('payment_history')
    if history is None:
        history=[{'date':x['date'],'amount':x['amount'],'method':x.get('method',''),'kind':'payment'} for o in data['orders'] for x in o.get('payments',[])]
    story += [Spacer(1,9),p('Abonos realizados','Gold')]
    if history:
        def label(row):
            if row['kind']=='last_payment_reference':return 'Abono informado'
            if row['kind']=='prior':return 'Abono previo sin fecha registrada'
            return {'transferencia':'Transferencia','efectivo':'Efectivo','otro':'Abono a la cuenta'}.get(row.get('method'),'Abono a la cuenta')
        story.append(table([['Fecha del abono','Monto','Detalle']]+[[date(x['date']),money(x['amount']),label(x)] for x in history],[130,130,235]))
    else:story.append(p('No hay abonos registrados.','Muted'))
    story += [Spacer(1,14),p('SALDO ACTUAL PENDIENTE: '+money(data['balance']),'Gold'),
              p('El saldo actual ya considera los abonos registrados. El historial se presenta para consulta. Los comprobantes sin confirmar no descuentan deuda.','Muted')]
    def footer(canvas,doc):
        canvas.setFont('Helvetica',8);canvas.setFillColor(colors.HexColor('#776b58'));canvas.drawString(50,25,'Cindy Lú · Estado de cuenta al momento de emisión');canvas.drawRightString(A4[0]-50,25,'Página '+str(doc.page))
    SimpleDocTemplate(buf,pagesize=A4,rightMargin=50,leftMargin=50,topMargin=32,bottomMargin=38,title='Estado de cuenta - Cindy Lú').build(story,onFirstPage=footer,onLaterPages=footer)
    buf.seek(0);return buf



