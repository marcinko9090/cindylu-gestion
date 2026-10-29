"""Estado de cuenta: productos pendientes de Shopify, abonos reales y saldo local, sin duplicar deuda."""
import io,json,re,datetime as dt
from zoneinfo import ZoneInfo
from pathlib import Path
from html import escape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.lib.enums import TA_LEFT,TA_RIGHT
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,KeepTogether,Image,HRFlowable
from reportlab.lib.pagesizes import A4

LOGO=Path(__file__).resolve().parent/'static'/'logo.png'


def payment_display_history(history,purchases):
    """Display filter only: never recalculate balances or change stored payments."""
    def day(value):
        text=str(value or '')
        try:
            if 'T' in text:
                return dt.datetime.fromisoformat(text.replace('Z','+00:00')).astimezone(ZoneInfo('America/Santiago')).date().isoformat()
            return dt.date.fromisoformat(text).isoformat()
        except (ValueError,TypeError):
            return ''
    dates=[day(o.get('purchased')) for o in purchases]
    cutoff=min((d for d in dates if d),default='')
    return [p for p in history if not cutoff or not day(p.get('date')) or day(p.get('date'))>=cutoff]

def purchase_records(stored,remote):
    """The same display-only purchases as the client file, with no debt calculation."""
    def number(o):return str(o.get('number') or '').strip().lstrip('#')
    def same(a,b):
        if a.get('shopify_id') and b.get('shopify_id'):return a['shopify_id']==b['shopify_id']
        return bool(number(a) and number(a)==number(b) and a['total']==b['total'])
    def detailed(o):
        return any(str(i.get('title') or '').strip() and not re.match(r'^(?:pedido|compra)(?:\s*#?\d+)?$',str(i['title']).strip(),re.I)
                   and not re.match(r'^(?:saldo|corte)\b',str(i['title']).strip(),re.I) for i in o.get('items') or [])
    stored=[o for o in stored if o.get('source')!='cxc' and o.get('status') in ('active','restructured')]
    entries=[]
    for row in remote:
        o=dict(row)
        if not detailed(o):
            available=next((s for s in stored if same(o,s) and detailed(s)),None)
            if available:o['items']=available['items']
        entries.append(o)
    entries += [dict(o,previous=o['status']=='restructured') for o in stored
                if not any(same(o,r) for r in remote) and (o['status']=='active' or detailed(o))]
    entries.sort(key=lambda o:str(o.get('number') or ''))
    entries.sort(key=lambda o:str(o.get('purchased') or ''),reverse=True)
    return entries

def snapshot(c,cid,balance,issued):
    cl=c.execute('SELECT c.*,cc.code,cc.work AS workplace,cc.raw_phone FROM clients c LEFT JOIN client_codes cc ON cc.client_id=c.id WHERE c.id=?',(cid,)).fetchone()
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
    stored=[dict(r) for r in c.execute("SELECT * FROM orders WHERE client_id=? AND status IN ('active','restructured') ORDER BY purchased,id",(cid,))]
    for o in stored:o['items']=json.loads(o['items'])
    historical=[]
    for row in c.execute("SELECT * FROM purchase_history WHERE client_id=? AND kind='purchase'",(cid,)):
        h=dict(row)
        items=json.loads(h['items'])
        if items:
            historical.append(dict(number=h['number'],purchased=h['date'],total=h['amount'],items=items,previous=True,status='restructured',source='history'))
    # Match the ficha: only displayed cards suppress historical product details.
    purchases=purchase_records(stored,shopify_orders)
    seen={str(o.get('number') or '').strip().lstrip('#') for o in purchases}
    for h in historical:
        key=str(h['number']).strip().lstrip('#')
        if key not in seen and purchase_records([h],[]):
            purchases.append(h)
            seen.add(key)
    purchases.sort(key=lambda o:str(o.get('number') or ''))
    purchases.sort(key=lambda o:str(o.get('purchased') or ''),reverse=True)
    # All active-account payments, including payments that closed a purchase. Archived imports stay excluded.
    history=[{'date':r['date'],'amount':r['amount'],'kind':'payment','method':r['method'],'number':r['number'] if r['source']!='cxc' else 'Abonos realizados'}
             for r in c.execute("SELECT p.*,o.number,o.source FROM payments p JOIN orders o ON o.id=p.order_id WHERE o.client_id=? AND o.status='active' AND p.reversed=0 ORDER BY p.date,p.id",(cid,))]
    for r in c.execute('SELECT date,amount,kind FROM cxc_payment_history WHERE client_id=? AND current=0 ORDER BY date,key',(cid,)):
        history.append({'date':r['date'],'amount':r['amount'],'kind':r['kind'],'method':''})
    for r in c.execute("SELECT base_paid,number,source FROM orders WHERE client_id=? AND status='active' AND base_paid>0",(cid,)):
        history.append({'date':'','amount':r['base_paid'],'kind':'prior','method':'','number':r['number'] if r['source']!='cxc' else 'Abonos realizados'})
    history.sort(key=lambda r:(r['date'] or '9999',r['amount'],r['kind']))
    return dict(client=dict(cl),orders=orders,shopify_orders=shopify_orders,purchases=purchases,payment_history=payment_display_history(history,purchases),issued=issued,total=sum(o['total'] for o in orders),paid=sum(o['total']-o['balance'] for o in orders),balance=sum(o['balance'] for o in orders))

def pdf(data):
    buf=io.BytesIO();styles=getSampleStyleSheet()
    gold=colors.HexColor('#a3823c');ink=colors.HexColor('#302b25')
    styles.add(ParagraphStyle(name='Muted',fontName='Helvetica',fontSize=8,leading=11,textColor=colors.HexColor('#70685c')))
    styles.add(ParagraphStyle(name='Gold',parent=styles['Heading2'],fontSize=12,leading=16,textColor=gold,spaceAfter=6))
    styles.add(ParagraphStyle(name='DocTitle',parent=styles['Title'],alignment=TA_LEFT,fontSize=21,leading=25,spaceAfter=6,textColor=ink))
    styles.add(ParagraphStyle(name='ClientName',parent=styles['Heading2'],fontSize=14,leading=18,spaceBefore=1,spaceAfter=4,textColor=ink))
    styles.add(ParagraphStyle(name='Purchase',fontName='Helvetica-Bold',fontSize=10.5,leading=14,textColor=ink,spaceAfter=5))
    styles.add(ParagraphStyle(name='Product',fontName='Helvetica',fontSize=9,leading=13,textColor=ink,spaceAfter=3))
    styles.add(ParagraphStyle(name='Money',parent=styles['Muted'],fontName='Helvetica-Bold',alignment=TA_RIGHT,fontSize=9,leading=12))
    styles.add(ParagraphStyle(name='Balance',fontName='Helvetica-Bold',fontSize=17,leading=23,textColor=gold))
    p=lambda s,style='Product':Paragraph(escape(str(s)),styles[style])
    money=lambda n:'$'+format(n,',').replace(',','.')
    months=('ENE','FEB','MAR','ABR','MAY','JUN','JUL','AGO','SEPT','OCT','NOV','DIC')
    def date(value,upper=False):
        text=str(value or '')
        if 'T' in text:
            try:text=dt.datetime.fromisoformat(text.replace('Z','+00:00')).astimezone(ZoneInfo('America/Santiago')).date().isoformat()
            except ValueError:return 'Sin fecha registrada'
        try:
            if re.fullmatch(r'\d{4}-\d{2}',text):
                d=dt.date.fromisoformat(text+'-01');return months[d.month-1]+' '+str(d.year)
            d=dt.date.fromisoformat(text[:10])
            return f'{d.day:02} {months[d.month-1] if upper else months[d.month-1].lower()} {d.year}'
        except ValueError:return 'Sin fecha registrada'
    cl=data['client']
    head=[p('CINDY LÚ · TIENDA','Gold'),p('Estado de cuenta','DocTitle'),p(cl['name'],'ClientName')]
    workplace=cl.get('workplace') or ''
    if not workplace:
        match=re.search(r'(?:^|[·\n])\s*(?:lugar de trabajo|trabajo|empresa|instituci[oó]n)\s*:\s*([^·\n]+)',cl.get('notes') or '',re.I)
        if not match:match=re.match(r'^COD\s+\S+\s*·\s*([^·\n]+)',cl.get('notes') or '',re.I)
        if match:workplace=match[1].strip()
    for line in (' · '.join(filter(None,[('Código '+cl['code']) if cl.get('code') else '',workplace])),
                 ' · '.join(filter(None,[('+'+cl['phone']) if cl.get('phone') else cl.get('raw_phone'),cl.get('email')])),
                 'Emitido: '+data['issued']+' · Pesos chilenos (CLP)'):
        if line:head.append(p(line,'Muted'))
    if LOGO.is_file():
        logo=Image(str(LOGO),width=100,height=84,mask='auto');logo.hAlign='RIGHT'
        header=Table([[head,logo]],colWidths=[385,110],hAlign='LEFT')
        header.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0),('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0)]))
        story=[header,Spacer(1,16)]
    else:story=head+[Spacer(1,16)]
    purchases=data.get('purchases')
    if purchases is None:purchases=purchase_records(data.get('orders',[]),data.get('shopify_orders',[]))
    for o in purchases:
        intro=[p('COMPRA '+str(o['number']),'Purchase'),p('Realizada el '+date(o.get('purchased'),True),'Muted')]
        status={'PENDING':'Pago pendiente en Shopify','PARTIALLY_PAID':'Pago parcial en Shopify'}.get(o.get('financial_status'),'Compra anterior · detalle de referencia' if o.get('previous') else '')
        if status:intro.append(p(status,'Muted'))
        intro += [Spacer(1,7),p('Detalle de productos:','Purchase')]
        items=o.get('items') or []
        if items:intro.append(p(str(items[0].get('quantity',1))+' × '+str(items[0].get('title') or 'Detalle no informado')))
        else:intro.append(p('Detalle de productos no informado.','Muted'))
        story.append(KeepTogether(intro))
        for item in items[1:]:story.append(p(str(item.get('quantity',1))+' × '+str(item.get('title') or 'Detalle no informado')))
        story += [Spacer(1,5),KeepTogether([p('Total de la compra: '+money(o['total']),'Purchase'),Spacer(1,9),HRFlowable(width='100%',thickness=.7,color=gold),Spacer(1,15)])]
    if not purchases:story += [p('Compras','Gold'),p('Todavía no hay productos vinculados a esta ficha.','Muted'),Spacer(1,12)]
    history=data.get('payment_history')
    if history is None:history=[dict(x,number=o['number']) for o in data.get('orders',[]) for x in o.get('payments',[])]
    history=payment_display_history(history,purchases)
    heading=p('Abonos realizados','Gold')
    if history:
        rows=[['Fecha de pago','Compra','Monto']]
        rows += [[date(x.get('date')),x.get('number') or 'Abonos realizados',money(x['amount'])] for x in history]
        table=Table([[p(v,'Money' if str(v).startswith('$') else 'Muted') for v in row] for row in rows],colWidths=[135,240,120],repeatRows=1,hAlign='LEFT')
        table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#f5eddd')),('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,0),.7,gold),('LINEBELOW',(0,1),(-1,-1),.3,colors.HexColor('#e9e3d8')),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]))
        story += [heading,table]
    else:story += [heading,p('Todavía no hay abonos registrados.','Muted')]
    story += [Spacer(1,18),KeepTogether([HRFlowable(width='100%',thickness=.7,color=gold),Spacer(1,12),p('Saldo vigente   '+money(data['balance']),'Balance')])]
    def footer(canvas,doc):
        canvas.setFont('Helvetica',8);canvas.setFillColor(colors.HexColor('#776b58'));canvas.drawString(50,25,'Cindy Lú · Estado de cuenta al momento de emisión');canvas.drawRightString(A4[0]-50,25,'Página '+str(doc.page))
    SimpleDocTemplate(buf,pagesize=A4,rightMargin=50,leftMargin=50,topMargin=32,bottomMargin=38,title='Estado de cuenta - Cindy Lú').build(story,onFirstPage=footer,onLaterPages=footer)
    buf.seek(0);return buf

