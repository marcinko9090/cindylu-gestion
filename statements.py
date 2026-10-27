"""Estado de cuenta: solo compras con saldo, nunca suma cuotas y compras dos veces."""
import io,json
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
    return dict(client=dict(cl),orders=orders,issued=issued,total=sum(o['total'] for o in orders),paid=sum(o['total']-o['balance'] for o in orders),balance=sum(o['balance'] for o in orders))

def pdf(data):
    buf=io.BytesIO();styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name='Muted',fontName='Helvetica',fontSize=8.5,leading=12,textColor=colors.HexColor('#665e52')))
    styles.add(ParagraphStyle(name='Gold',parent=styles['Heading2'],textColor=colors.HexColor('#966c20'),spaceAfter=4))
    styles.add(ParagraphStyle(name='DocTitle',parent=styles['Title'],alignment=TA_LEFT,fontSize=22,leading=26,spaceAfter=6,textColor=colors.HexColor('#292821')))
    styles.add(ParagraphStyle(name='ClientName',parent=styles['Heading2'],fontSize=14,leading=18,spaceBefore=2,spaceAfter=4,textColor=colors.HexColor('#292821')))
    p=lambda s,style='BodyText':Paragraph(escape(str(s)),styles[style])
    money=lambda n:'$'+format(n,',').replace(',','.')
    def date(s):
        s=str(s)[:10];return '/'.join(reversed(s.split('-')))
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
        t=Table([[p(v,'Muted') for v in r] for r in rows],colWidths=widths,repeatRows=1,hAlign='LEFT')
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#f3e8ce')),('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,0),.7,colors.HexColor('#c6a159')),('LINEBELOW',(0,1),(-1,-1),.3,colors.HexColor('#e8e3da')),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]));return t
    story += [table([['Compras con deuda','Pagado en estas compras','Saldo pendiente'],[money(data['total']),money(data['paid']),money(data['balance'])]],[165,165,165]),Spacer(1,6),p('Solo se incluyen compras con saldo pendiente. Las compras totalmente pagadas y las anuladas quedan excluidas.','Muted')]
    if not data['orders']:story.append(p('No hay compras con deuda pendiente.','Heading2'))
    for o in data['orders']:
        intro=[Spacer(1,10),p(o['number']+' · Compra del '+date(o['purchased']),'Gold')]
        story.append(KeepTogether(intro))
        for item in o['items']:story.append(p(str(item.get('quantity',1))+' × '+str(item.get('title','Artículo'))))
        confirmed_paid=sum(x['amount'] for x in o.get('payments',[]))
        story.append(p('Total compra: '+money(o['total'])+' − Pagos previos: '+money(o.get('base_paid',0))+' − Abonos confirmados: '+money(confirmed_paid)+' = Saldo pendiente: '+money(o['balance']),'Heading3'))
        if o['review']:story.append(p('POR REVISAR: '+o['review']+' Este documento refleja el saldo local registrado.','Muted'))
        if o['base_paid']:story.append(p('Pagos previos al registro: '+money(o['base_paid'])+'.','Muted'))
        if o['payments']:
            story.extend([p('Abonos confirmados de esta compra','Heading3'),table([['Fecha de pago','Monto','Medio']]+[[date(x['date']),money(x['amount']),x['method']] for x in o['payments']],[165,165,165])])
        else:story.append(p('Sin abonos confirmados en esta plataforma.','Muted'))
    story += [Spacer(1,10),p('TOTAL PENDIENTE: '+money(data['balance']),'Gold'),p('Los abonos confirmados ya están descontados del saldo. Los comprobantes pendientes de revisión no descuentan deuda.','Muted')]
    def footer(canvas,doc):
        canvas.setFont('Helvetica',8);canvas.setFillColor(colors.HexColor('#776b58'));canvas.drawString(50,25,'Cindy Lú · Estado de cuenta al momento de emisión');canvas.drawRightString(A4[0]-50,25,'Página '+str(doc.page))
    SimpleDocTemplate(buf,pagesize=A4,rightMargin=50,leftMargin=50,topMargin=32,bottomMargin=38,title='Estado de cuenta - Cindy Lú').build(story,onFirstPage=footer,onLaterPages=footer)
    buf.seek(0);return buf

