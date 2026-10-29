"""Cindy Lú · aplicación independiente, Flask + SQLite. Montos CLP enteros."""
import os, json, sqlite3, secrets, datetime as dt, calendar, hashlib, hmac, base64, re, io, zipfile, threading, time, urllib.request, urllib.error
from pathlib import Path
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation
import shopify_auth
from shopify_review import review_record, merge_review_records, shopify_items
from flask import Flask, request, session, jsonify, send_file, render_template
from seasons import season_for
import cindy_import
from shopify_pending import pending_record
import shopify_tags
from werkzeug.security import generate_password_hash, check_password_hash

PAYMENT_CONFIRMATION="Confirmamos tu abono de {monto}.\n\n*Tu saldo total pendiente es {saldo_total}*\n\n¡Gracias por comprar en Cindy Lú!\n\nRECUERDA: TODO DISPONIBLE EN MI WEB\nhttps://cindylu.cl/\n\nAgrega lo que quieras a tu cuenta, hasta en 3 cuotas 🤑"

ROOT=Path(__file__).resolve().parent
# Optional local configuration, never exposed to the browser.
if (ROOT/'.env').exists():
    for line in (ROOT/'.env').read_text(encoding='utf-8-sig').splitlines():
        if '=' in line and not line.lstrip().startswith('#'):
            k,v=line.split('=',1); k=k.strip()
            if re.fullmatch(r'[A-Z][A-Z0-9_]*',k):os.environ.setdefault(k,v.strip().strip('"').strip("'"))
DATA=Path(os.environ.get('CINDY_DATA',ROOT/'data')).resolve()
DATA.mkdir(parents=True,exist_ok=True); (DATA/'media').mkdir(exist_ok=True)
DEMO=os.getenv('CINDY_DEMO','0')=='1'
secret=DATA/'session.key'
if not secret.exists(): secret.write_text(secrets.token_hex(48)); secret.chmod(0o600)
app=Flask(__name__)
if os.getenv('CINDY_TRUST_PROXY')=='1':
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app=ProxyFix(app.wsgi_app,x_proto=1,x_host=1)

app.config.update(SECRET_KEY=secret.read_text(),MAX_CONTENT_LENGTH=30*1024*1024,SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE='Strict',SESSION_COOKIE_SECURE=os.getenv('CINDY_HTTPS')=='1',PERMANENT_SESSION_LIFETIME=dt.timedelta(hours=12))
DB=DATA/'cindy.sqlite3'

def now(): return dt.datetime.now(dt.timezone.utc).isoformat()
def today():
    # Fixed UTC-3 fallback is avoided: tzdata dependency supplies Chile DST on Windows.
    from zoneinfo import ZoneInfo
    return dt.datetime.now(ZoneInfo('America/Santiago')).date().isoformat()
def amount(v):
    try:n=Decimal(str(v))
    except (InvalidOperation,TypeError):raise ValueError('Monto inválido.')
    if not n.is_finite() or n!=int(n) or n<0 or n>10**11: raise ValueError('Usa montos enteros en pesos chilenos.')
    return int(n)
def phone(v):
    if isinstance(v,(int,float)) and not isinstance(v,bool):
        if int(v)!=v:raise ValueError('Teléfono inválido.')
        v=str(int(v))
    p=re.sub(r'[^0-9]','',str(v or ''))
    if len(p)==9 and p.startswith('9'): p='56'+p
    if p and not re.fullmatch(r'[1-9][0-9]{7,14}',p): raise ValueError('Teléfono inválido. Usa código de país.')
    return p
def date(v): return dt.date.fromisoformat(str(v)[:10]).isoformat()
@contextmanager
def db(write=False):
    c=sqlite3.connect(DB,timeout=30); c.row_factory=sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    try:
        if write: c.execute('BEGIN IMMEDIATE')
        yield c
        c.commit()
    except: c.rollback(); raise
    finally: c.close()
def rows(c,q,args=()): return [dict(r) for r in c.execute(q,args)]
def one(c,q,args=()):
    r=c.execute(q,args).fetchone()
    if not r: raise ValueError('Registro no encontrado.')
    return dict(r)
def audit(c,event,data): c.execute('INSERT INTO audit(event,data,created) VALUES(?,?,?)',(event,json.dumps(data,ensure_ascii=False),now()))
def init():
    with db() as c:
        c.executescript('''
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,email TEXT UNIQUE NOT NULL,password TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS clients(id INTEGER PRIMARY KEY,name TEXT NOT NULL,phone TEXT NOT NULL DEFAULT '',email TEXT NOT NULL DEFAULT '',shopify_id TEXT UNIQUE,notes TEXT DEFAULT '',consent INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY,client_id INTEGER NOT NULL REFERENCES clients(id),shopify_id TEXT UNIQUE,number TEXT NOT NULL,purchased TEXT NOT NULL,total INTEGER NOT NULL,base_paid INTEGER NOT NULL DEFAULT 0,items TEXT NOT NULL,currency TEXT DEFAULT 'CLP',source TEXT DEFAULT 'manual',status TEXT DEFAULT 'active',review TEXT DEFAULT '',remote TEXT DEFAULT '',updated TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS installments(id INTEGER PRIMARY KEY,order_id INTEGER NOT NULL REFERENCES orders(id),number INTEGER NOT NULL,due TEXT NOT NULL,amount INTEGER NOT NULL,UNIQUE(order_id,number));
        CREATE TABLE IF NOT EXISTS receipts(id INTEGER PRIMARY KEY,client_id INTEGER NOT NULL REFERENCES clients(id),filename TEXT NOT NULL,mime TEXT NOT NULL,path TEXT DEFAULT '',media_id TEXT UNIQUE,status TEXT DEFAULT 'pending',created TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS payments(id INTEGER PRIMARY KEY,order_id INTEGER NOT NULL REFERENCES orders(id),amount INTEGER NOT NULL,date TEXT NOT NULL,method TEXT NOT NULL,receipt_id INTEGER REFERENCES receipts(id),operation TEXT UNIQUE NOT NULL,reversed INTEGER DEFAULT 0,note TEXT DEFAULT '',created TEXT NOT NULL);
        CREATE UNIQUE INDEX IF NOT EXISTS active_receipt ON payments(receipt_id) WHERE reversed=0 AND receipt_id IS NOT NULL;
        CREATE TABLE IF NOT EXISTS allocations(payment_id INTEGER NOT NULL REFERENCES payments(id),installment_id INTEGER NOT NULL REFERENCES installments(id),amount INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY,client_id INTEGER NOT NULL REFERENCES clients(id),direction TEXT NOT NULL,body TEXT NOT NULL,wa_id TEXT UNIQUE,receipt_id INTEGER REFERENCES receipts(id),status TEXT NOT NULL,created TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS reminders(id INTEGER PRIMARY KEY,client_id INTEGER NOT NULL REFERENCES clients(id),at TEXT NOT NULL,body TEXT NOT NULL,status TEXT DEFAULT 'pending',error TEXT DEFAULT '');
        CREATE TABLE IF NOT EXISTS payment_shares(payment_id INTEGER PRIMARY KEY REFERENCES payments(id) ON DELETE CASCADE,body TEXT NOT NULL,phone TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS payment_notices(payment_id INTEGER PRIMARY KEY REFERENCES payments(id),client_id INTEGER NOT NULL REFERENCES clients(id),body TEXT NOT NULL,status TEXT NOT NULL,error TEXT DEFAULT '',created TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS statement_sends(id INTEGER PRIMARY KEY,operation TEXT UNIQUE NOT NULL,client_id INTEGER NOT NULL REFERENCES clients(id),digest TEXT NOT NULL,body TEXT NOT NULL,phone TEXT NOT NULL,balance INTEGER NOT NULL,path TEXT DEFAULT '',filename TEXT NOT NULL,status TEXT NOT NULL,wa_id TEXT UNIQUE,error TEXT DEFAULT '',created TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS statement_links(token_hash TEXT PRIMARY KEY,pdf BLOB NOT NULL,expires INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,event TEXT,data TEXT,created TEXT);
        ''')
        cindy_import.init_schema(c)
        for k,v in {'auto_reply':False,'payment_notify':False,'payment_text':PAYMENT_CONFIRMATION,'sending':False,'reply_text':'Gracias, recibimos tu comprobante. Revisaremos la transferencia y te confirmaremos el abono.','template':'','template_language':'es_CL','statement_template':'','statement_language':'es_CL','sync_at':'','sync_error':'','shopify_domain':'cindylu.myshopify.com','shopify_token':'','shopify_credit_mode':'credit_when_paid','shopify_default_installments':0}.items(): c.execute('INSERT OR IGNORE INTO settings VALUES(?,?)',(k,json.dumps(v)))
        if settings(c).get('payment_text') in ("Hola, {nombre} ✨ Confirmamos tu abono de {monto} para la compra {compra}. Saldo de esta compra: {saldo_compra}. Tu saldo total pendiente es {saldo_total}. ¡Gracias por comprar en Cindy Lú!", "Hola, {nombre}. Confirmamos tu abono de {monto} para la compra {compra}. Saldo de esta compra: {saldo_compra}. Tu saldo total pendiente es {saldo_total}. ¡Gracias por comprar en Cindy Lú!"):
            setval(c,'payment_text',PAYMENT_CONFIRMATION)
        c.execute("UPDATE payment_notices SET status='review',error='Envío interrumpido; revisar antes de reenviar.' WHERE status='sending'")
        c.execute("UPDATE statement_sends SET status='review',error='Envío interrumpido; revisar WhatsApp antes de reenviar.' WHERE status IN ('preparing','sending')")
        c.execute("UPDATE messages SET status='review' WHERE status='sending'")
        c.execute("UPDATE reminders SET status='review',error='Envío interrumpido; revisar antes de reenviar.' WHERE status='sending'")
def settings(c): return {r['key']:json.loads(r['value']) for r in c.execute('SELECT * FROM settings')}
def setval(c,k,v): c.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',(k,json.dumps(v)))
def balance(c,oid):
    o=one(c,'SELECT * FROM orders WHERE id=?',(oid,))
    paid=c.execute('SELECT COALESCE(SUM(amount),0) FROM payments WHERE order_id=? AND reversed=0',(oid,)).fetchone()[0]
    return o['total']-o['base_paid']-paid

def make_plan(c,d):
    oid=int(d['order_id']); o=one(c,'SELECT * FROM orders WHERE id=?',(oid,))
    if o['review'] or o['status']!='active': raise ValueError('Revisa primero los cambios de esta compra.')
    if c.execute('SELECT 1 FROM payments WHERE order_id=?',(oid,)).fetchone(): raise ValueError('El plan tiene historial de abonos y no puede reemplazarse.')
    n=int(d['count']); first=dt.date.fromisoformat(d['first']); freq=d.get('frequency','monthly')
    if n<1 or n>60 or freq not in ('monthly','weekly','fortnight'): raise ValueError('Plan de cuotas inválido.')
    pending=balance(c,oid)
    if pending<n: raise ValueError('El saldo debe permitir al menos $1 por cuota.')
    c.execute('DELETE FROM installments WHERE order_id=?',(oid,))
    for i in range(n):
        if freq=='monthly':
            m=first.year*12+first.month-1+i; y,mo=divmod(m,12); mo+=1
            due=dt.date(y,mo,min(first.day,calendar.monthrange(y,mo)[1]))
        else: due=first+dt.timedelta(days=i*(7 if freq=='weekly' else 15))
        value=pending//n+(1 if i<pending%n else 0)
        c.execute('INSERT INTO installments(order_id,number,due,amount) VALUES(?,?,?,?)',(oid,i+1,due.isoformat(),value))
    audit(c,'plan',{'order_id':oid,'count':n})
def pay(c,d):
    op=str(d.get('operation',''))
    if not re.fullmatch(r'[a-zA-Z0-9_-]{16,100}',op): raise ValueError('Falta identificador del abono.')
    old=c.execute('SELECT id FROM payments WHERE operation=?',(op,)).fetchone()
    if old:return old[0]
    oid=int(d['order_id']); o=one(c,'SELECT * FROM orders WHERE id=?',(oid,)); a=amount(d['amount'])
    if o['review'] or o['status']!='active':raise ValueError('Compra bloqueada para revisión de cambios de Shopify.')
    if a<=0 or a>balance(c,oid): raise ValueError('El abono debe ser mayor a cero y no superar el saldo de esta compra.')
    rid=int(d['receipt_id']) if d.get('receipt_id') else None
    if rid:
        r=one(c,'SELECT * FROM receipts WHERE id=?',(rid,))
        if r['client_id']!=o['client_id'] or r['status']!='pending':raise ValueError('Comprobante ya revisado o de otra clienta.')
    ins=rows(c,'''SELECT i.*,i.amount-COALESCE((SELECT SUM(a.amount) FROM allocations a JOIN payments p ON p.id=a.payment_id WHERE a.installment_id=i.id AND p.reversed=0),0) pending FROM installments i WHERE order_id=? ORDER BY due,number''',(oid,))
    method=d.get('method','transferencia')
    if method not in ('transferencia','efectivo','otro'): raise ValueError('Medio de pago inválido.')
    pid=c.execute('INSERT INTO payments(order_id,amount,date,method,receipt_id,operation,note,created) VALUES(?,?,?,?,?,?,?,?)',(oid,a,date(d.get('date',today())),method,rid,op,str(d.get('note',''))[:1000],now())).lastrowid
    left=a
    for i in ins:
        take=min(left,i['pending'])
        if take>0:c.execute('INSERT INTO allocations VALUES(?,?,?)',(pid,i['id'],take)); left-=take
    if rid:c.execute("UPDATE receipts SET status='confirmed' WHERE id=?",(rid,))
    audit(c,'payment_confirmed',{'id':pid,'amount':a,'order':oid})
    return pid

failures={}; fail_lock=threading.Lock()
@app.before_request
def security():
    if request.method == 'POST' and request.path != '/webhooks/whatsapp':
        origin=request.headers.get('Origin')
        # Prefer the server-configured public origin behind a TLS proxy.
        public_url = (os.getenv('CINDY_PUBLIC_URL') or os.getenv('RENDER_EXTERNAL_URL') or request.host_url).rstrip('/')
        if origin and origin != public_url:
            return jsonify(error='Origen de solicitud no permitido.'),403
    if request.path in ('/','/api/session','/api/login','/api/setup','/api/health','/api/demo') or request.path.startswith('/static/') or request.path=='/webhooks/whatsapp':return
    if request.endpoint=='shared_statement_pdf' and request.method in ('GET','HEAD'):return
    if not session.get('user'):return jsonify(error='Inicia sesión.'),401
    if request.method!='GET' and not hmac.compare_digest(request.headers.get('X-CSRF-Token',''),session.get('csrf','missing')):return jsonify(error='Sesión vencida. Actualiza la página.'),403
@app.after_request
def headers(r):
    r.headers['X-Content-Type-Options']='nosniff';r.headers['X-Frame-Options']='DENY';r.headers['Referrer-Policy']='no-referrer'
    r.headers['Content-Security-Policy']="default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'"
    if not request.path.startswith('/static/'):r.headers['Cache-Control']='no-store'
    return r
@app.errorhandler(ValueError)
def invalid(e):return jsonify(error=str(e)),400
@app.errorhandler(sqlite3.IntegrityError)
def conflict(e):return jsonify(error='El registro ya existe o cambió. Actualiza y vuelve a revisar.'),409
@app.errorhandler(413)
def large(e):return jsonify(error='Archivo demasiado grande (máximo 8 MB).'),413
@app.route('/')
def index():return render_template('index.html',season=season_for())
@app.post('/api/demo')
def demo_access():
    if not DEMO:return jsonify(error='La demostración no está habilitada.'),403
    with db() as c:r=one(c,'SELECT id FROM users LIMIT 1')
    session.clear();session['user']=r['id'];session['csrf']=secrets.token_urlsafe(32)
    return jsonify(ok=True)
@app.get('/api/health')
def health():return jsonify(ok=True)
@app.get('/api/session')
def sess():
    with db() as c: setup=not c.execute('SELECT 1 FROM users').fetchone()
    return jsonify(authenticated=bool(session.get('user')),csrf=session.get('csrf'),setup=setup,demo=DEMO,season=season_for())
@app.post('/api/setup')
def setup():
    # Initial account can only be created on the computer running the server.
    if request.remote_addr not in ('127.0.0.1','::1'):return jsonify(error='Crea el primer acceso desde el servidor local.'),403
    d=request.get_json(); email=str(d.get('email','')).strip().lower(); password=str(d.get('password',''))
    if '@' not in email or len(email)>200 or len(password)<12:raise ValueError('Ingresa un correo y una contraseña de al menos 12 caracteres.')
    with db(True) as c:
        if c.execute('SELECT 1 FROM users').fetchone():raise ValueError('El acceso ya fue creado.')
        c.execute('INSERT INTO users(email,password) VALUES(?,?)',(email,generate_password_hash(password)))
    return jsonify(ok=True)
@app.post('/api/login')
def login():
    d=request.get_json(); ip=request.remote_addr
    with fail_lock:
        times=[t for t in failures.get(ip,[]) if time.time()-t<900]
        if len(times)>=10:return jsonify(error='Demasiados intentos. Espera 15 minutos.'),429
        failures[ip]=times+[time.time()]
    with db() as c:r=c.execute('SELECT * FROM users WHERE email=?',(str(d.get('email','')).strip().lower(),)).fetchone()
    if not r or not check_password_hash(r['password'],str(d.get('password',''))):return jsonify(error='Correo o contraseña incorrectos.'),401
    with fail_lock:failures.pop(ip,None)
    session.clear();session['user']=r['id'];session['csrf']=secrets.token_urlsafe(32);session.permanent=True
    return jsonify(ok=True,csrf=session['csrf'])
@app.post('/api/logout')
def logout():session.clear();return jsonify(ok=True)
@app.get('/api/state')
def state():
    with db() as c:
        clients=rows(c,'''SELECT c.*,cc.code,cc.work AS workplace,cc.raw_phone FROM clients c LEFT JOIN client_codes cc ON cc.client_id=c.id ORDER BY c.name''')
        history=rows(c,'SELECT * FROM purchase_history ORDER BY date,period,number,key')
        for h in history:h['items']=json.loads(h['items'])
        cxc_history=rows(c,'SELECT * FROM cxc_payment_history ORDER BY date,key')
        cxc_accounts=rows(c,'SELECT * FROM cxc_accounts')
        orders=rows(c,'SELECT * FROM orders ORDER BY purchased DESC,id DESC')
        for o in orders:o['items']=json.loads(o['items']);o['balance']=balance(c,o['id'])
        ins=rows(c,'''SELECT i.*,i.amount-COALESCE((SELECT SUM(a.amount) FROM allocations a JOIN payments p ON p.id=a.payment_id WHERE a.installment_id=i.id AND p.reversed=0),0) pending FROM installments i ORDER BY due,number''')
        cfg=settings(c)
        allocs=rows(c,'SELECT a.payment_id,a.installment_id,a.amount,p.date,p.method,p.order_id FROM allocations a JOIN payments p ON p.id=a.payment_id WHERE p.reversed=0 ORDER BY p.date,p.id')
        shop_tok=shopify_auth.configured(cfg)
        safe_cfg={k:v for k,v in cfg.items() if k!='shopify_token'}
        safe_cfg['has_shopify_token']=bool(cfg.get('shopify_token'))
        return jsonify(purchase_history=history,cxc_history=cxc_history,cxc_accounts=cxc_accounts,statement_sends=rows(c,'SELECT id,client_id,body,phone,balance,filename,status,wa_id,error,created FROM statement_sends ORDER BY id'),clients=clients,orders=orders,installments=ins,payments=rows(c,'SELECT * FROM payments ORDER BY id DESC'),allocations=allocs,receipts=rows(c,'SELECT id,client_id,filename,mime,status,created FROM receipts ORDER BY id DESC'),messages=rows(c,'SELECT * FROM messages ORDER BY id'),reminders=rows(c,'SELECT * FROM reminders ORDER BY at'),payment_notices=rows(c,'SELECT * FROM payment_notices ORDER BY payment_id DESC'),settings=safe_cfg,today=today(),season=season_for(),demo=DEMO,integrations={'shopify':shop_tok and not DEMO,'whatsapp':bool(os.getenv('WA_ACCESS_TOKEN') and os.getenv('WA_PHONE_NUMBER_ID') and os.getenv('WA_APP_SECRET')) and not DEMO,'shop':os.getenv('SHOPIFY_DOMAIN') or cfg.get('shopify_domain') or 'cindylu.myshopify.com'})
@app.post('/api/clients/<int:cid>/statement-link')
def create_statement_link(cid):
    from statements import snapshot,pdf
    token=secrets.token_urlsafe(32)
    expires=int(time.time())+7*86400
    with db(True) as c:
        data=snapshot(c,cid,balance,dt.datetime.now(__import__('zoneinfo').ZoneInfo('America/Santiago')).strftime('%d/%m/%Y %H:%M'))
        document=pdf(data).getvalue()
        c.execute('DELETE FROM statement_links WHERE expires<=?',(int(time.time()),))
        c.execute('INSERT INTO statement_links VALUES(?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),document,expires))
    return jsonify(path='/estado/'+token+'.pdf',expires=expires,balance=data['balance'])

@app.get('/estado/<token>.pdf')
def shared_statement_pdf(token):
    if not re.fullmatch(r'[A-Za-z0-9_-]{43}',token):
        return 'Enlace no disponible o vencido.',404
    with db() as c:
        row=c.execute('SELECT pdf FROM statement_links WHERE token_hash=? AND expires>?',(hashlib.sha256(token.encode()).hexdigest(),int(time.time()))).fetchone()
    if not row:return 'Enlace no disponible o vencido.',404
    response=send_file(io.BytesIO(row['pdf']),mimetype='application/pdf',as_attachment=True,download_name='Estado-de-cuenta-Cindy-Lu.pdf')
    response.headers['X-Robots-Tag']='noindex, nofollow, noarchive'
    return response

@app.get('/api/clients/<int:cid>/statement.pdf')
def statement_pdf(cid):
    from statements import snapshot,pdf
    with db() as c:
        c.execute('BEGIN')
        data=snapshot(c,cid,balance,dt.datetime.now(__import__('zoneinfo').ZoneInfo('America/Santiago')).strftime('%d/%m/%Y %H:%M'))
    return send_file(pdf(data),mimetype='application/pdf',as_attachment=True,download_name='Estado-de-cuenta-'+str(cid)+'.pdf')

def statement_preview_data(c,cid):
    from statements import snapshot
    data=snapshot(c,cid,balance,dt.datetime.now(__import__('zoneinfo').ZoneInfo('America/Santiago')).strftime('%d/%m/%Y %H:%M'))
    client=data['client'];cfg=settings(c)
    incoming=c.execute("SELECT created FROM messages WHERE client_id=? AND direction='in' AND wa_id IS NOT NULL ORDER BY created DESC LIMIT 1",(cid,)).fetchone()
    recent=False
    if incoming:
        elapsed=(dt.datetime.now(dt.timezone.utc)-dt.datetime.fromisoformat(incoming[0])).total_seconds()
        recent=0<=elapsed<86400
    mode='demo' if DEMO else 'document' if recent else 'template'
    body='Hola, '+client['name']+', te enviamos tu estado de cuenta de Cindy Lú. Tu saldo pendiente es $'+format(data['balance'],',').replace(',','.')+'. El PDF incluye tus compras con deuda y sus abonos.'
    blocked=''
    if not client['phone']:blocked='Completa el teléfono de la clienta en su ficha.'
    elif any(o['review'] for o in data['orders']):blocked='Hay compras con cambios de Shopify pendientes de revisión. Revisa los saldos antes de enviar.'
    elif not DEMO:
        if not all(os.getenv(k) for k in ('WA_ACCESS_TOKEN','WA_PHONE_NUMBER_ID','WA_APP_SECRET')) or not cfg['sending']:blocked='Vincula WhatsApp y habilita los envíos en Configuración.'
        elif not client['consent']:blocked='Registra en la ficha la autorización de la clienta para recibir mensajes.'
        elif not recent and not cfg['statement_template']:blocked='Se necesita una plantilla aprobada con encabezado PDF. Configúrala en Mensajes y respuestas.'
    proof={k:v for k,v in data.items() if k!='issued'}
    proof.update(mode=mode,template=cfg['statement_template'] if mode=='template' else '',language=cfg['statement_language'] if mode=='template' else '',sending=cfg['sending'])
    digest=hashlib.sha256(json.dumps(proof,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    return data,dict(client_id=cid,name=client['name'],phone=client['phone'],balance=data['balance'],purchases=len(data['orders']),body=body,mode=mode,template=cfg['statement_template'],language=cfg['statement_language'],blocked=blocked,digest=digest)

@app.get('/api/clients/<int:cid>/statement-preview')
def statement_preview(cid):
    with db() as c:
        c.execute('BEGIN');_,preview=statement_preview_data(c,cid)
    return jsonify(preview)

@app.get('/api/statement-sends/<int:sid>/file')
def statement_sent_file(sid):
    with db() as c:r=one(c,'SELECT * FROM statement_sends WHERE id=?',(sid,))
    if not r['path'] or not (DATA/'media'/r['path']).is_file():raise ValueError('PDF no disponible.')
    return send_file(DATA/'media'/r['path'],mimetype='application/pdf',as_attachment=True,download_name=r['filename'])

@app.post('/api/statement-sends')
def statement_send():
    d=request.get_json();cid=int(d['client_id']);operation=str(d.get('operation',''))
    if not re.fullmatch(r'[a-zA-Z0-9-]{16,100}',operation):raise ValueError('Operación de envío no válida.')
    with db(True) as c:
        old=c.execute('SELECT * FROM statement_sends WHERE operation=?',(operation,)).fetchone()
        if old:
            if old['client_id']!=cid or old['digest']!=d.get('digest'):raise ValueError('La operación corresponde a otro envío.')
            return jsonify(id=old['id'],status=old['status'],error=old['error'],duplicate=True)
        data,preview=statement_preview_data(c,cid)
        if preview['blocked']:raise ValueError(preview['blocked'])
        if d.get('digest')!=preview['digest']:raise ValueError('La cuenta o sus datos cambiaron. Vuelve a seleccionar la clienta para revisar el estado actualizado.')
        filename='Estado-de-cuenta-'+str(cid)+'-'+today()+'.pdf'
        sid=c.execute('INSERT INTO statement_sends(operation,client_id,digest,body,phone,balance,filename,status,created) VALUES(?,?,?,?,?,?,?,?,?)',(operation,cid,preview['digest'],preview['body'],preview['phone'],preview['balance'],filename,'preparing',now())).lastrowid
    try:
        from statements import pdf
        document=pdf(data).getvalue()
        if len(document)>8*1024*1024:raise ValueError('El PDF supera el máximo de 8 MB.')
        key='statement-'+secrets.token_hex(20)+'.pdf';(DATA/'media'/key).write_bytes(document)
        with db(True) as c:c.execute("UPDATE statement_sends SET path=?,status=? WHERE id=?",(key,'demo' if DEMO else 'sending',sid))
        if not DEMO:
            from wa_documents import upload_pdf
            media_id=upload_pdf(document,filename)
            payload={'messaging_product':'whatsapp','to':preview['phone']}
            attachment={'id':media_id,'filename':filename}
            if preview['mode']=='document':payload.update(type='document',document={**attachment,'caption':preview['body']})
            else:
                payload.update(type='template',template={'name':preview['template'],'language':{'code':preview['language']},'components':[{'type':'header','parameters':[{'type':'document','document':attachment}]},{'type':'body','parameters':[{'type':'text','text':preview['name']},{'type':'text','text':'$'+format(preview['balance'],',').replace(',','.')}]}]})
            result=graph('/'+os.environ['WA_PHONE_NUMBER_ID']+'/messages',payload)
            waid=result['messages'][0]['id']
            with db(True) as c:c.execute("UPDATE statement_sends SET status='sent',wa_id=? WHERE id=?",(waid,sid))
        with db(True) as c:audit(c,'statement_sent' if not DEMO else 'statement_demo',{'id':sid,'client':cid,'balance':preview['balance']})
        return jsonify(id=sid,status='demo' if DEMO else 'sent',duplicate=False)
    except Exception:
        with db(True) as c:c.execute("UPDATE statement_sends SET status='review',error='No se confirmó el envío. Revisa WhatsApp antes de reenviar.' WHERE id=?",(sid,))
        return jsonify(id=sid,status='review',error='No se confirmó el envío. Revisa WhatsApp antes de reenviar.'),502

@app.post('/api/clients')
def clients():
    d=request.get_json(); name=str(d.get('name','')).strip()
    if not name or len(name)>150:raise ValueError('Ingresa el nombre completo.')
    with db(True) as c:
        cid=c.execute('INSERT INTO clients(name,phone,email,notes,consent) VALUES(?,?,?,?,?)',(name,phone(d.get('phone','')),str(d.get('email',''))[:200],str(d.get('notes',''))[:2000],int(bool(d.get('consent'))))).lastrowid
        audit(c,'client_created',{'id':cid})
    return jsonify(id=cid)
@app.post('/api/orders')
def manual_order():
    d=request.get_json(); total=amount(d['total']); initial=amount(d.get('initial',0))
    if total<=0 or initial>total:raise ValueError('Total o abono previo inválido.')
    with db(True) as c:
        one(c,'SELECT id FROM clients WHERE id=?',(int(d['client_id']),))
        oid=c.execute('INSERT INTO orders(client_id,number,purchased,total,base_paid,items,updated) VALUES(?,?,?,?,?,?,?)',(int(d['client_id']),'MAN-'+secrets.token_hex(3).upper(),date(d['purchased']),total,initial,json.dumps([{'title':str(d['article'])[:300],'quantity':1}]),now())).lastrowid
        audit(c,'manual_order',{'id':oid})
    return jsonify(id=oid)
@app.post('/api/plan')
def plan():
    with db(True) as c:make_plan(c,request.get_json())
    return jsonify(ok=True)
@app.post('/api/payments')
def payment():
    d=request.get_json()
    with db(True) as c:
        existing=c.execute('SELECT id FROM payments WHERE operation=?',(str(d.get('operation','')),)).fetchone()
        pid=pay(c,d)
        if not existing and bool(d.get('notify',settings(c)['payment_notify'])):
            custom=d.get('notice_template')
            if custom is not None and (not isinstance(custom,str) or not custom.strip() or len(custom)>1000):
                raise ValueError('Escribe un mensaje de confirmación de entre 1 y 1000 caracteres, o desmarca el envío por WhatsApp.')
            cid,body=payment_text(c,pid,custom.strip() if custom is not None else None)
            c.execute('INSERT INTO payment_notices(payment_id,client_id,body,status,created) VALUES(?,?,?,?,?)',(pid,cid,body,'demo' if DEMO else 'pending',now()))
            audit(c,'payment_notice_queued',{'payment_id':pid})
        notice=c.execute('SELECT payment_id,body,status,error FROM payment_notices WHERE payment_id=?',(pid,)).fetchone()
        notice=dict(notice) if notice else None
        share=c.execute('SELECT body,phone FROM payment_shares WHERE payment_id=?',(pid,)).fetchone()
        if not share:
            cid,body=payment_text(c,pid)
            phone=one(c,'SELECT phone FROM clients WHERE id=?',(cid,))['phone']
            c.execute('INSERT INTO payment_shares(payment_id,body,phone) VALUES(?,?,?)',(pid,body,phone))
            share={'body':body,'phone':phone}
        share=dict(share);share['status']='ready'
    return jsonify(id=pid,notice=notice,share=share)
@app.post('/api/payments/<int:pid>/reverse')
def reverse(pid):
    reason=str(request.get_json().get('reason','')).strip()
    if len(reason)<5:raise ValueError('Indica el motivo de la anulación.')
    with db(True) as c:
        p=one(c,'SELECT * FROM payments WHERE id=?',(pid,))
        if p['reversed']:raise ValueError('Abono ya anulado.')
        c.execute('UPDATE payments SET reversed=1 WHERE id=?',(pid,))
        c.execute("UPDATE payment_notices SET status='cancelled' WHERE payment_id=? AND status='pending'",(pid,))
        if p['receipt_id']:c.execute("UPDATE receipts SET status='pending' WHERE id=?",(p['receipt_id'],))
        audit(c,'payment_reversed',{'id':pid,'reason':reason[:1000]})
    return jsonify(ok=True)
def filetype(data):
    if data.startswith(b'\x89PNG\r\n\x1a\n'):return 'image/png','.png'
    if data.startswith(b'\xff\xd8\xff'):return 'image/jpeg','.jpg'
    if data[:4]==b'RIFF' and data[8:12]==b'WEBP':return 'image/webp','.webp'
    if data.startswith(b'%PDF-'):return 'application/pdf','.pdf'
    raise ValueError('Usa JPG, PNG, WEBP o PDF.')
def save_media(data):
    if not data or len(data)>8*1024*1024:raise ValueError('El comprobante no puede superar 8 MB.')
    mime,ext=filetype(data); key=secrets.token_hex(24)+ext;(DATA/'media'/key).write_bytes(data);return key,mime
@app.post('/api/receipts')
def upload():
    cid=int(request.form['client_id']); f=request.files['file']
    with db(True) as c:
        one(c,'SELECT id FROM clients WHERE id=?',(cid,));key,mime=save_media(f.read(8*1024*1024+1))
        rid=c.execute('INSERT INTO receipts(client_id,filename,mime,path,created) VALUES(?,?,?,?,?)',(cid,(f.filename or 'Comprobante')[:150],mime,key,now())).lastrowid
        c.execute('INSERT INTO messages(client_id,direction,body,receipt_id,status,created) VALUES(?,?,?,?,?,?)',(cid,'in','Comprobante cargado manualmente',rid,'received',now()))
    return jsonify(id=rid)
@app.post('/api/receipts/<int:rid>/reject')
def reject(rid):
    with db(True) as c:
        r=one(c,'SELECT * FROM receipts WHERE id=?',(rid,))
        if r['status']!='pending':raise ValueError('Comprobante ya revisado.')
        c.execute("UPDATE receipts SET status='rejected' WHERE id=?",(rid,));audit(c,'receipt_rejected',{'id':rid})
    return jsonify(ok=True)
@app.get('/api/receipts/<int:rid>/file')
def media(rid):
    with db() as c:r=one(c,'SELECT * FROM receipts WHERE id=?',(rid,))
    if not r['path'] and r['media_id']:
        info=graph('/'+r['media_id']); url=info.get('url','')
        from urllib.parse import urlparse
        host=urlparse(url).hostname or ''
        if urlparse(url).scheme!='https' or not (host.endswith('.fbcdn.net') or host.endswith('.facebook.com') or host.endswith('.fbsbx.com')):raise ValueError('Ubicación de archivo no válida.')
        req=urllib.request.Request(url,headers={'Authorization':'Bearer '+os.getenv('WA_ACCESS_TOKEN','')})
        with urllib.request.urlopen(req,timeout=25) as response:data=response.read(8*1024*1024+1)
        key,mime=save_media(data)
        with db(True) as c:c.execute('UPDATE receipts SET path=?,mime=? WHERE id=?',(key,mime,rid))
        r['path']=key;r['mime']=mime
    if not r['path']:raise ValueError('Comprobante no disponible; revisa la conexión de WhatsApp.')
    return send_file(DATA/'media'/r['path'],mimetype=r['mime'],download_name=r['filename'],as_attachment=r['mime']=='application/pdf')
@app.post('/api/settings')
def config():
    d=request.get_json()
    with db(True) as c:
        for k in ('auto_reply','sending','payment_notify','payment_text','reply_text','template','template_language','statement_template','statement_language','shopify_domain','shopify_credit_mode','whatsapp_statement_text','explain_intro','explain_bank','explain_outro','explain_show_summary','explain_show_payments','explain_show_installments','explain_show_bank'):
            if k in d:setval(c,k,bool(d[k]) if k in ('auto_reply','sending','payment_notify','explain_show_summary','explain_show_payments','explain_show_installments','explain_show_bank') else str(d[k])[:1000])
        if 'mark_seen_order_id' in d:
            seen=list(settings(c).get('seen_new_orders') or [])
            oid_seen=int(d['mark_seen_order_id'])
            if oid_seen not in seen:seen.append(oid_seen)
            setval(c,'seen_new_orders',seen[-2000:])
        if 'mark_all_seen' in d and d['mark_all_seen']:
            all_ids=[r['id'] for r in rows(c,'SELECT id FROM orders')]
            setval(c,'seen_new_orders',all_ids[-2000:])
        if 'shopify_default_installments' in d:
            setval(c,'shopify_default_installments',max(0,min(60,int(d.get('shopify_default_installments') or 0))))
        if 'shopify_token' in d and str(d['shopify_token']).strip():
            setval(c,'shopify_token',str(d['shopify_token']).strip()[:500])
    return jsonify(ok=True)


@app.post('/api/orders/<int:oid>/items')
def edit_order_items(oid):
    d=request.get_json() or {}
    article=str(d.get('article') or '').strip()[:400]
    order_num=str(d.get('number') or '').strip()[:40]
    purchased=date(d.get('purchased') or today())
    if not article:raise ValueError('Escribe el detalle de los productos de la venta.')
    items=[{'title':x.strip()[:200],'quantity':1} for x in article.split(',') if x.strip()] or [{'title':article[:200],'quantity':1}]
    with db(True) as c:
        o=one(c,'SELECT * FROM orders WHERE id=?',(oid,))
        new_num=order_num if order_num else o['number']
        c.execute('UPDATE orders SET number=?,purchased=?,items=?,updated=? WHERE id=?',(new_num,purchased,json.dumps(items,ensure_ascii=False),now(),oid))
        audit(c,'order_items_edited',{'order_id':oid,'number':new_num})
    return jsonify(ok=True)

@app.post('/api/orders/<int:oid>/adjust')
def adjust_order(oid):
    d=request.get_json() or {}
    with db(True) as c:
        o=one(c,'SELECT * FROM orders WHERE id=?',(oid,))
        paid_sum=c.execute('SELECT COALESCE(SUM(amount),0) FROM payments WHERE order_id=? AND reversed=0',(oid,)).fetchone()[0]
        new_total=amount(d.get('total',o['total']))
        new_base=amount(d.get('base_paid',o['base_paid']))
        if new_total<=0 or new_base+paid_sum>new_total:
            raise ValueError('El total debe cubrir los pagos previos y los abonos ya confirmados ('+str(new_base+paid_sum)+').')
        c.execute("UPDATE orders SET total=?,base_paid=?,review='',status='active',updated=? WHERE id=?",(new_total,new_base,now(),oid))
        count=int(d.get('count') or 0)
        if count>0:
            first=dt.date.fromisoformat(str(d.get('first') or today())[:10])
            freq=d.get('frequency','monthly')
            if count<1 or count>60 or freq not in ('monthly','weekly','fortnight'):raise ValueError('Plan de cuotas inválido.')
            distributable=new_total-new_base
            if distributable<count:raise ValueError('El monto a financiar en cuotas debe permitir al menos $1 por cuota.')
            c.execute('DELETE FROM allocations WHERE installment_id IN (SELECT id FROM installments WHERE order_id=?)',(oid,))
            c.execute('DELETE FROM installments WHERE order_id=?',(oid,))
            ins_ids=[]
            for i in range(count):
                if freq=='monthly':
                    m=first.year*12+first.month-1+i; y,mo=divmod(m,12); mo+=1
                    due=dt.date(y,mo,min(first.day,calendar.monthrange(y,mo)[1]))
                else:due=first+dt.timedelta(days=i*(7 if freq=='weekly' else 15))
                val=distributable//count+(1 if i<distributable%count else 0)
                iid=c.execute('INSERT INTO installments(order_id,number,due,amount) VALUES(?,?,?,?)',(oid,i+1,due.isoformat(),val)).lastrowid
                ins_ids.append([iid,val])
            # Re-allocate existing active payments in chronological order across the new installments
            for p in rows(c,'SELECT id,amount FROM payments WHERE order_id=? AND reversed=0 ORDER BY date,id',(oid,)):
                left=p['amount']
                for slot in ins_ids:
                    if left<=0:break
                    take=min(left,slot[1])
                    if take>0:
                        c.execute('INSERT INTO allocations(payment_id,installment_id,amount) VALUES(?,?,?)',(p['id'],slot[0],take))
                        slot[1]-=take;left-=take
        audit(c,'order_adjusted',{'order_id':oid,'total':new_total,'base_paid':new_base,'count':count})
    return jsonify(ok=True)

def httpjson(url,data=None,headers=None):
    req=urllib.request.Request(url,data=json.dumps(data).encode() if data is not None else None,headers={'Content-Type':'application/json',**(headers or {})})
    try:
        with urllib.request.urlopen(req,timeout=25) as r:return json.load(r)
    except urllib.error.HTTPError as e:raise ValueError('El servicio respondió HTTP '+str(e.code)+'. Revisa las credenciales y permisos.')
    except (urllib.error.URLError,TimeoutError):raise ValueError('No se pudo contactar al servicio. Revisa la conexión.')
def graph(path,data=None):
    if DEMO or not os.getenv('WA_ACCESS_TOKEN'):raise ValueError('WhatsApp aún no está vinculado.')
    return httpjson('https://graph.facebook.com/'+os.getenv('WA_API_VERSION','v23.0')+path,data,{'Authorization':'Bearer '+os.environ['WA_ACCESS_TOKEN']})
def send_message(cid,body,template=False):
    with db(True) as c:
        cfg=settings(c); client=one(c,'SELECT * FROM clients WHERE id=?',(cid,))
        if DEMO or not cfg['sending'] or not os.getenv('WA_PHONE_NUMBER_ID'):raise ValueError('WhatsApp no está listo para enviar. Configúralo primero.')
        if not client['consent']:raise ValueError('La clienta debe autorizar los mensajes por WhatsApp.')
        if not client['phone']:raise ValueError('La clienta no tiene teléfono.')
        incoming=c.execute("SELECT created FROM messages WHERE client_id=? AND direction='in' AND wa_id IS NOT NULL ORDER BY id DESC LIMIT 1",(cid,)).fetchone()
        recent=incoming and (dt.datetime.now(dt.timezone.utc)-dt.datetime.fromisoformat(incoming[0])).total_seconds()<86400
        payload={'messaging_product':'whatsapp','to':client['phone']}
        if template or not recent:
            if not cfg['template']:raise ValueError('Fuera de 24 horas se necesita una plantilla aprobada en Meta.')
            payload.update(type='template',template={'name':cfg['template'],'language':{'code':cfg['template_language']},'components':[{'type':'body','parameters':[{'type':'text','text':client['name']},{'type':'text','text':body}]}]})
        else:payload.update(type='text',text={'body':body})
        mid=c.execute('INSERT INTO messages(client_id,direction,body,status,created) VALUES(?,?,?,?,?)',(cid,'out',body,'sending',now())).lastrowid
    try:
        result=graph('/'+os.environ['WA_PHONE_NUMBER_ID']+'/messages',payload);waid=result['messages'][0]['id']
        with db(True) as c:c.execute("UPDATE messages SET status='sent',wa_id=? WHERE id=?",(waid,mid))
    except Exception:
        with db(True) as c:c.execute("UPDATE messages SET status='review' WHERE id=?",(mid,))
        raise ValueError('No se confirmó el envío. Revisa WhatsApp antes de volver a enviar.')
@app.post('/api/messages')
def message():
    d=request.get_json();body=str(d.get('body','')).strip()
    if not body or len(body)>3000:raise ValueError('Mensaje vacío o demasiado largo.')
    send_message(int(d['client_id']),body);return jsonify(ok=True)
@app.post('/api/consent/<int:cid>')
def consent(cid):
    with db(True) as c:
        one(c,'SELECT id FROM clients WHERE id=?',(cid,));c.execute('UPDATE clients SET consent=? WHERE id=?',(int(bool(request.get_json().get('consent'))),cid));audit(c,'consent',{'client':cid})
    return jsonify(ok=True)
@app.route('/webhooks/whatsapp',methods=['GET','POST'])
def webhook():
    if DEMO:return '',403
    if request.method=='GET':
        token=os.getenv('WA_VERIFY_TOKEN','')
        if token and request.args.get('hub.mode')=='subscribe' and hmac.compare_digest(request.args.get('hub.verify_token',''),token):return request.args.get('hub.challenge','')
        return '',403
    secret=os.getenv('WA_APP_SECRET','');raw=request.get_data()
    expected='sha256='+hmac.new(secret.encode(),raw,hashlib.sha256).hexdigest()
    if not secret or not hmac.compare_digest(expected,request.headers.get('X-Hub-Signature-256','')):return '',403
    payload=request.get_json();replies=[]
    with db(True) as c:
        for entry in payload.get('entry',[]):
            for change in entry.get('changes',[]):
                val=change.get('value',{})
                if val.get('metadata',{}).get('phone_number_id')!=os.getenv('WA_PHONE_NUMBER_ID'):continue
                for s in val.get('statuses',[]):
                    c.execute('UPDATE messages SET status=? WHERE wa_id=?',(s.get('status','unknown'),s.get('id','')))
                    if s.get('status') in ('sent','delivered','read','failed'):
                        c.execute("UPDATE statement_sends SET status=CASE WHEN status='read' THEN status WHEN status='delivered' AND ?!='read' THEN status ELSE ? END WHERE wa_id=?",(s['status'],s['status'],s.get('id','')))

                for m in val.get('messages',[]):
                    if c.execute('SELECT id FROM messages WHERE wa_id=?',(m['id'],)).fetchone():continue
                    p=phone(m['from']); matches=rows(c,'SELECT * FROM clients WHERE phone=?',(p,))
                    if len(matches)>1: raise ValueError('Teléfono duplicado: unifica las fichas antes de recibir mensajes.')
                    if matches:cid=matches[0]['id']
                    else:
                        name=next((x.get('profile',{}).get('name') for x in val.get('contacts',[]) if x.get('wa_id')==p),p)
                        cid=c.execute('INSERT INTO clients(name,phone) VALUES(?,?)',(name or p,p)).lastrowid
                    typ=m.get('type');body=m.get('text',{}).get('body','');rid=None
                    if typ in ('image','document'):
                        media=m[typ];body=media.get('caption','Comprobante recibido');rid=c.execute('INSERT INTO receipts(client_id,filename,mime,media_id,created) VALUES(?,?,?,?,?)',(cid,media.get('filename','Comprobante'),media.get('mime_type','application/octet-stream'),media['id'],now())).lastrowid
                        if settings(c)['auto_reply']:replies.append((cid,settings(c)['reply_text']))
                    if not body:body='Mensaje recibido: '+str(typ)
                    created=dt.datetime.fromtimestamp(int(m['timestamp']),dt.timezone.utc).isoformat()
                    c.execute('INSERT INTO messages(client_id,direction,body,wa_id,receipt_id,status,created) VALUES(?,?,?,?,?,?,?)',(cid,'in',body,m['id'],rid,'received',created))
    for cid,body in replies:
        try:send_message(cid,body)
        except Exception:pass
    return jsonify(ok=True)

class ShopifyMoneyError(ValueError):
    """An external order needs review; never round it into the local ledger."""

def shopify_amount(o,field,label):
    money=o[field]['shopMoney']
    number=str(o.get('name') or o.get('id') or 'Pedido')[:100]
    if money['currencyCode']!='CLP':
        raise ShopifyMoneyError(number+': '+label+' no está en CLP. No se modificó esta compra.')
    try:return amount(money['amount'])
    except ValueError:
        value=str(money['amount'])[:60]
        raise ShopifyMoneyError(number+': '+label+' recibido de Shopify ('+value+' CLP) tiene decimales, es negativo o está fuera del rango permitido. No se redondeó ni se modificó esta compra.') from None

SHOP_QUERY='''query Orders($cursor:String){orders(first:50,after:$cursor,sortKey:UPDATED_AT){pageInfo{hasNextPage endCursor} nodes{id name createdAt updatedAt cancelledAt displayFinancialStatus currentTotalPriceSet{shopMoney{amount currencyCode}} totalOutstandingSet{shopMoney{amount currencyCode}} customer{id displayName email phone} shippingAddress{phone firstName lastName} lineItems(first:250){pageInfo{hasNextPage endCursor} nodes{title quantity currentQuantity variantTitle}}}}}'''
def import_shop_order(c,o,allow_new=True):
    total=shopify_amount(o,'currentTotalPriceSet','total')
    outstanding=shopify_amount(o,'totalOutstandingSet','saldo')
    if outstanding>total:raise ShopifyMoneyError(str(o.get('name','Pedido'))[:100]+': el saldo de Shopify supera el total. No se modificó esta compra.')
    cfg=settings(c)
    mode=cfg.get('shopify_credit_mode','credit_when_paid')
    # En Cindy Lú se vende en cuotas aunque en Shopify se marque como Pagado (outstanding==0).
    if mode=='credit_all':base_paid=0
    elif mode=='credit_when_paid' and outstanding==0:base_paid=0
    else:base_paid=total-outstanding
    old=c.execute('SELECT * FROM orders WHERE shopify_id=?',(o['id'],)).fetchone()
    items=shopify_items(o)
    snapshot=json.dumps({'total':total,'outstanding':outstanding,'cancelled':o.get('cancelledAt'),'items':items},sort_keys=True,ensure_ascii=False)
    cust=o.get('customer') or {};shipping=o.get('shippingAddress') or {}; sid=cust.get('id')
    try:remote_phone=phone(cust.get('phone') or shipping.get('phone'))
    except ValueError:remote_phone=''
    remote_email=str(cust.get('email') or '').strip().lower()
    def same_client(client):
        # A name alone is never sufficient to merge a financial record.
        try:local_phone=phone(client['phone'])
        except ValueError:local_phone=''
        if sid and client['shopify_id'] and sid!=client['shopify_id']:return False
        if local_phone and remote_phone and local_phone!=remote_phone:return False
        return bool((sid and sid==client['shopify_id']) or (local_phone and local_phone==remote_phone)
                    or (remote_email and remote_email==str(client['email'] or '').strip().lower()))
    if cindy_import.enrich_history(c,o,items,total,remote_phone,remote_email,sid):
        return 'updated'
    if not old:
        normalized=str(o['name']).strip().lstrip('#').strip()
        matches=rows(c,"SELECT * FROM orders WHERE trim(ltrim(trim(number),'#'))=?",(normalized,))
        if matches:
            if len(matches)!=1:return 'conflict'
            candidate=matches[0]
            client=one(c,'SELECT * FROM clients WHERE id=?',(candidate['client_id'],))
            if candidate['shopify_id'] or candidate['source']!='excel' or candidate['total']!=total or o.get('cancelledAt') or not same_client(client):
                return 'conflict'
            # Link and enrich only: never replace the Excel ledger or allocations.
            c.execute('UPDATE orders SET shopify_id=?,items=?,remote=?,updated=? WHERE id=?',
                      (o['id'],json.dumps(items,ensure_ascii=False),snapshot,now(),candidate['id']))
            audit(c,'shopify_excel_linked',{'order_id':candidate['id'],'shopify_id':o['id']})
            return 'linked'
    if old:
        if old['source']=='excel':
            if old['total']!=total or o.get('cancelledAt'):
                c.execute("UPDATE orders SET review='El total o la anulación cambiaron en Shopify. Revisa la compra antes de modificar su saldo.',updated=? WHERE id=?",(now(),old['id']))
                return 'conflict'
            c.execute('UPDATE orders SET items=?,remote=?,updated=? WHERE id=?',
                      (json.dumps(items,ensure_ascii=False),snapshot,now(),old['id']))
        elif old['remote']!=snapshot:
            c.execute("UPDATE orders SET review='La compra o sus pagos cambiaron en Shopify. Usa «Ajustar compra / cuotas» para conciliar el saldo.',updated=? WHERE id=?",(now(),old['id']))
            return 'conflict'
        return 'updated'
    if not allow_new:return 'pending'
    cl=c.execute('SELECT id FROM clients WHERE shopify_id=?',(sid,)).fetchone() if sid else None
    if cl:cid=cl[0]
    else:
        name=cust.get('displayName') or ' '.join(filter(None,[shipping.get('firstName'),shipping.get('lastName')])) or 'Compra '+o['name']
        try:p=phone(cust.get('phone') or shipping.get('phone'))
        except ValueError:p=''
        candidates=rows(c,'SELECT id FROM clients WHERE phone=? AND shopify_id IS NULL',(p,)) if p else []
        if len(candidates)==1 and sid:
            cid=candidates[0]['id'];c.execute('UPDATE clients SET shopify_id=? WHERE id=?',(sid,cid))
        else:cid=c.execute('INSERT INTO clients(name,phone,email,shopify_id) VALUES(?,?,?,?)',(name,p,cust.get('email') or '',sid)).lastrowid
    status='cancelled' if o.get('cancelledAt') else 'active'
    oid=c.execute('INSERT INTO orders(client_id,shopify_id,number,purchased,total,base_paid,items,source,status,remote,updated) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(cid,o['id'],o['name'],o['createdAt'],total,base_paid,json.dumps(items,ensure_ascii=False),'shopify',status,snapshot,now())).lastrowid
    return 'created'
def create_shopify_client_files(c):
    from shopify_clients import create_missing,incorporate_review_pending
    decisions=settings(c).get('shopify_order_decisions',{})
    records=[r for r in settings(c).get('shopify_pending_orders',[]) if r['shopify_id'] not in decisions]
    result=create_missing(c,records,phone,amount,now())
    reviews=settings(c).get('shopify_review_orders',[])
    result['purchases_added']+=incorporate_review_pending(c,records,reviews,amount,now())
    for r in reviews:
        if r['shopify_id'] in decisions:
            r.update(status='reviewed',note='Al contado' if decisions[r['shopify_id']]['decision']=='cash' else 'Compra agregada al saldo')
    setval(c,'shopify_review_orders',reviews)
    setval(c,'shopify_pending_orders',records)
    if result['clients_created'] or result['purchases_added']:audit(c,'shopify_client_files_created',result)
    return result

SYNC_LOCK=threading.Lock()
def sync_shop():
    with db() as c:cfg=settings(c)
    domain=shopify_auth.domain(cfg)
    if DEMO:raise ValueError('Shopify no está disponible en demostración.')
    if not SYNC_LOCK.acquire(False):raise ValueError('Ya hay una sincronización en curso.')
    summary={'count':0,'linked':0,'updated':0,'pending':0,'conflict':0}
    issues=[];review_queue=[];completed=set();pending_orders=[]
    try:
        cursor=None
        while True:
            # Reacquire a cached token per page, renewing before expiry.
            token=shopify_auth.access_token(cfg)
            result=httpjson('https://'+domain+'/admin/api/'+os.getenv('SHOPIFY_API_VERSION','2026-10')+'/graphql.json',{'query':SHOP_QUERY,'variables':{'cursor':cursor}},{'X-Shopify-Access-Token':token})
            if result.get('errors'):raise ValueError('Shopify rechazó la consulta. Revisa permisos de pedidos y datos de clientes.')
            page=result['data']['orders']
            with db(True) as c:
                for o in page['nodes']:
                    if o['lineItems']['pageInfo']['hasNextPage']:raise ValueError('Un pedido supera 250 artículos; requiere importación ampliada. No se importó parcialmente.')
                    record=pending_record(c,o,phone,now(),cfg.get('shopify_pending_links',{}))
                    if record:pending_orders.append(record)
                    error=None
                    try:outcome=import_shop_order(c,o,allow_new=False)
                    except ShopifyMoneyError as exc:
                        error=str(exc);outcome='conflict'
                        if len(issues)<100:issues.append(error)
                    if outcome in ('conflict','pending'):review_queue.append(review_record(c,o,outcome,error,now(),balance))
                    else:completed.add(o['id'])
                    summary[outcome]+=1;summary['count']+=1
            if not page['pageInfo']['hasNextPage']:break
            cursor=page['pageInfo']['endCursor']
        tag_customers=None;tags_error=''
        try:
            def tags_request(query,variables):
                return httpjson('https://'+domain+'/admin/api/'+os.getenv('SHOPIFY_API_VERSION','2026-10')+'/graphql.json',{'query':query,'variables':variables},{'X-Shopify-Access-Token':shopify_auth.access_token(cfg)})
            tag_customers=shopify_tags.fetch_customers(tags_request)
        except ValueError as exc:tags_error=str(exc)
        with db(True) as c:
            setval(c,'sync_at',now());setval(c,'sync_error','');setval(c,'shopify_sync_summary',summary)
            setval(c,'shopify_sync_issues',issues)
            current_links=settings(c).get('shopify_pending_links',{})
            for record in pending_orders:
                link=current_links.get(record['shopify_id'],{})
                if link.get('identity')==record['identity'] and c.execute('SELECT 1 FROM clients WHERE id=?',(link.get('client_id'),)).fetchone():
                    record.update(client_id=link['client_id'],match='manual')
            if tag_customers is not None:
                tag_lookup={ct['id']:ct.get('tags',[]) for ct in tag_customers}
                for record in pending_orders:record['tags']=tag_lookup.get(record['customer_id'],[])
            else:
                old_tags={r['shopify_id']:r.get('tags',[]) for r in settings(c).get('shopify_pending_orders',[])}
                for record in pending_orders:record['tags']=old_tags.get(record['shopify_id'],[])
            setval(c,'shopify_pending_orders',pending_orders)
            setval(c,'shopify_tags_error',tags_error)
            if tag_customers is not None:
                setval(c,'shopify_client_tags',shopify_tags.classify(c,tag_customers,phone,pending_orders))
                setval(c,'shopify_tags_at',now())
            setval(c,'shopify_review_orders',merge_review_records(settings(c).get('shopify_review_orders',[]),review_queue,completed))
            create_shopify_client_files(c)
            setval(c,'shopify_auto_sync',True);audit(c,'shopify_sync',summary)
        return summary
    finally:SYNC_LOCK.release()
@app.post('/api/shopify/sync')
def sync():return jsonify(sync_shop())
@app.post('/api/shopify/pending/add-debt')
def add_shopify_debt():
    d=request.get_json() or {}
    sid=str(d.get('shopify_id',''))
    with db(True) as c:
        cfg=settings(c)
        item=next((r for r in cfg.get('shopify_pending_orders',[]) if r['shopify_id']==sid),None)
        if not item or item['fingerprint']!=d.get('fingerprint'):raise ValueError('El pedido cambió. Actualiza Shopify y vuelve a revisar.')
        cid=int(d.get('client_id',0))
        if not cid or cid!=item.get('client_id'):raise ValueError('Vincula primero el pedido a la ficha correcta.')
        one(c,'SELECT id FROM clients WHERE id=?',(cid,))
        existing=c.execute('SELECT * FROM orders WHERE shopify_id=?',(sid,)).fetchone()
        if existing:
            if existing['source'] in ('shopify_confirmed','shopify_confirmed_new') and existing['client_id']==cid:return jsonify(ok=True,already_added=True,order_id=existing['id'])
            raise ValueError('Este pedido ya tiene un registro. Revisa su saldo en la ficha; no se sumó nuevamente.')
        key=str(item.get('number') or '').strip().lstrip('#').strip()
        if not key:raise ValueError('Falta el número del pedido.')
        if c.execute("SELECT 1 FROM orders WHERE trim(ltrim(trim(number),'#'))=?",(key,)).fetchone() or c.execute("SELECT 1 FROM purchase_history WHERE trim(ltrim(trim(number),'#'))=? AND kind='purchase'",(key,)).fetchone():
            raise ValueError('El número de pedido ya existe en el historial. Revisa la cuenta antes de agregar deuda.')
        total=amount(item['total']);pending=amount(item['outstanding'])
        if item.get('financial_status') not in ('PENDING','PARTIALLY_PAID') or not 0<pending<=total:raise ValueError('El pedido no tiene un saldo pendiente válido.')
        if amount(d.get('outstanding'))!=pending:raise ValueError('El saldo cambió. Revisa el pedido nuevamente.')
        if d.get('confirm_not_in_balance') is not True:raise ValueError('Confirma que esta compra no está incluida en el saldo actual.')
        remote=json.dumps({'total':total,'outstanding':pending,'cancelled':None,'items':item['items']},sort_keys=True,ensure_ascii=False)
        oid=c.execute("INSERT INTO orders(client_id,shopify_id,number,purchased,total,base_paid,items,source,status,remote,updated) VALUES(?,?,?,?,?,?,?,'shopify_confirmed','active',?,?)",
            (cid,sid,item['number'],item['purchased'],total,total-pending,json.dumps(item['items'],ensure_ascii=False),remote,now())).lastrowid
        audit(c,'shopify_debt_confirmed',{'order_id':oid,'client_id':cid,'shopify_id':sid,'added_balance':pending,'fingerprint':item['fingerprint'],'user':session['user']})
    return jsonify(ok=True,order_id=oid)

def resolve_shopify_review(c, d):
    sid=str(d.get('shopify_id',''));decision=d.get('decision')
    if decision not in ('cash','debt'):raise ValueError('Selecciona Al contado o Agregar al saldo.')
    cfg=settings(c);decisions=cfg.get('shopify_order_decisions',{})
    previous=decisions.get(sid)
    if previous:
        if previous['decision']==decision and previous['fingerprint']==d.get('fingerprint'):return
        raise ValueError('Este pedido ya fue resuelto. Revisa su ficha antes de cambiarlo.')
    reviews=cfg.get('shopify_review_orders',[])
    item=next((r for r in reviews if r['shopify_id']==sid),None)
    if not item or item['fingerprint']!=d.get('fingerprint'):raise ValueError('El pedido cambió. Actualiza y vuelve a revisar.')
    existing=c.execute('SELECT * FROM orders WHERE shopify_id=?',(sid,)).fetchone()
    oid=existing['id'] if existing else None
    if decision=='cash':
        # Preserve purchases and payments in history, without an outstanding debt.
        if existing:
            c.execute("UPDATE orders SET status='cancelled',review='',updated=? WHERE id=?",(now(),oid))
    else:
        if item.get('currency')!='CLP':raise ValueError('Revisa la moneda del pedido antes de agregarlo.')
        total=amount(item['total']);pending=amount(item['outstanding'])
        if not 0<pending<=total:raise ValueError('El pedido no tiene un saldo pendiente válido. Revisa sus montos.')
        snapshot=next((r for r in cfg.get('shopify_pending_orders',[]) if r['shopify_id']==sid),{})
        cid=item.get('client_id') or snapshot.get('client_id')
        if not cid:raise ValueError('Vincula el pedido a la ficha correcta desde Pedidos de Shopify y vuelve a revisar.')
        one(c,'SELECT id FROM clients WHERE id=?',(cid,))
        if existing:
            if existing['client_id']!=cid or existing['status']!='active' or existing['total']!=total or existing['review']:
                raise ValueError('La compra existente tiene diferencias. Revisa Ajustar compra en su ficha antes de incorporarla.')
        else:
            key=str(item.get('number') or '').strip().lstrip('#').strip()
            if not key:raise ValueError('Falta el número del pedido.')
            if c.execute("SELECT 1 FROM orders WHERE trim(ltrim(trim(number),'#'))=?",(key,)).fetchone() or c.execute("SELECT 1 FROM purchase_history WHERE trim(ltrim(trim(number),'#'))=? AND kind='purchase'",(key,)).fetchone():
                raise ValueError('La compra ya está en el historial. Revisa la ficha para evitar duplicar deuda.')
            remote=json.dumps({'total':total,'outstanding':pending,'cancelled':None,'items':item['items']},sort_keys=True,ensure_ascii=False)
            oid=c.execute("INSERT INTO orders(client_id,shopify_id,number,purchased,total,base_paid,items,source,status,remote,updated) VALUES(?,?,?,?,?,?,?,'shopify_confirmed','active',?,?)",
                (cid,sid,item['number'],item['purchased'],total,total-pending,json.dumps(item['items'],ensure_ascii=False),remote,now())).lastrowid
    decisions[sid]={'decision':decision,'fingerprint':item['fingerprint'],'order_id':oid,'at':now()}
    setval(c,'shopify_order_decisions',decisions)
    item.update(status='reviewed',note='Al contado' if decision=='cash' else 'Compra agregada al saldo',reviewed_at=now(),reviewed_by=session['user'])
    setval(c,'shopify_review_orders',reviews)
    setval(c,'shopify_pending_orders',[r for r in cfg.get('shopify_pending_orders',[]) if r['shopify_id']!=sid])
    audit(c,'shopify_review_resolved',{'shopify_id':sid,**decisions[sid],'user':session['user']})

@app.post('/api/shopify/review')
def save_shopify_review():
    d=request.get_json() or {}
    if 'decision' in d:
        with db(True) as c:resolve_shopify_review(c,d)
        return jsonify(ok=True)
    sid=str(d.get('shopify_id',''));fingerprint=str(d.get('fingerprint',''))
    status=d.get('status');note=str(d.get('note','')).strip()
    if status not in ('pending','reviewed') or len(note)>2000 or (status=='reviewed' and len(note)<5):
        raise ValueError('Agrega una observación de al menos 5 caracteres para marcar como revisado (máximo 2000).')
    with db(True) as c:
        records=settings(c).get('shopify_review_orders',[])
        item=next((r for r in records if r['shopify_id']==sid),None)
        if not item:raise ValueError('El pedido ya no está en revisión. Actualiza la página.')
        if item['fingerprint']!=fingerprint:raise ValueError('El pedido cambió en Shopify. Actualiza y revisa sus nuevos datos.')
        item.update(status=status,note=note,reviewed_at=now(),reviewed_by=session['user'])
        setval(c,'shopify_review_orders',records)
        audit(c,'shopify_review_saved',{'shopify_id':sid,'status':status,'user':session['user']})
    return jsonify(ok=True)
@app.post('/api/shopify/pending/link')
def link_pending_client():
    d=request.get_json() or {}
    try:cid=int(d.get('client_id',0))
    except (ValueError,TypeError):raise ValueError('Selecciona una ficha existente.')
    with db(True) as c:
        one(c,'SELECT id FROM clients WHERE id=?',(cid,))
        cfg=settings(c);records=cfg.get('shopify_pending_orders',[])
        item=next((r for r in records if r['shopify_id']==str(d.get('shopify_id',''))),None)
        if not item or item['fingerprint']!=str(d.get('fingerprint','')):
            raise ValueError('El pedido cambió. Actualiza la página antes de vincularlo.')
        links=cfg.get('shopify_pending_links',{})
        links[item['shopify_id']]={'client_id':cid,'identity':item['identity']}
        item.update(client_id=cid,match='manual')
        setval(c,'shopify_pending_links',links);setval(c,'shopify_pending_orders',records)
        audit(c,'shopify_pending_client_linked',{'shopify_id':item['shopify_id'],'client_id':cid})
    return jsonify(ok=True)
@app.post('/api/shopify/test')
def test_shopify_connection():
    if DEMO:raise ValueError('Shopify no está disponible en demostración.')
    with db() as c:cfg=settings(c)
    token=shopify_auth.access_token(cfg)
    result=httpjson('https://'+shopify_auth.domain(cfg)+'/admin/api/'+os.getenv('SHOPIFY_API_VERSION','2026-10')+'/graphql.json',
                    {'query':'{shop{name myshopifyDomain} orders(first:1){nodes{id}}}'},{'X-Shopify-Access-Token':token})
    if result.get('errors'):raise ValueError('Shopify rechazó la prueba. Verifica el permiso read_orders y la instalación de la app.')
    return jsonify(ok=True,shop=result['data']['shop']['name'])
@app.post('/api/reminders')
def reminder():
    raise ValueError('Las fechas de cobro están desactivadas. Registra los abonos en la ficha de la clienta.')
@app.post('/api/reminders/<int:rid>/cancel')
def cancel_reminder(rid):
    with db(True) as c:c.execute("UPDATE reminders SET status='cancelled' WHERE id=? AND status='pending'",(rid,))
    return jsonify(ok=True)
@app.get('/api/backup')
def backup():
    bio=io.BytesIO(); tmp=DATA/('backup-'+secrets.token_hex(8)+'.sqlite3')
    try:
        with db() as c:
            out=sqlite3.connect(tmp);c.backup(out);out.close()
        with zipfile.ZipFile(bio,'w',zipfile.ZIP_DEFLATED) as z:
            z.write(tmp,'cindy.sqlite3')
            for p in (DATA/'media').iterdir():
                if p.is_file():z.write(p,'media/'+p.name)
        bio.seek(0);return send_file(bio,mimetype='application/zip',download_name='CindyLu-respaldo-'+today()+'.zip',as_attachment=True)
    finally:tmp.unlink(missing_ok=True)

def payment_text(c,pid,template=None):
    p=one(c,'SELECT * FROM payments WHERE id=?',(pid,));o=one(c,'SELECT * FROM orders WHERE id=?',(p['order_id'],));cl=one(c,'SELECT * FROM clients WHERE id=?',(o['client_id'],))
    total=sum(balance(c,x['id']) for x in rows(c,"SELECT id FROM orders WHERE client_id=? AND status='active'",(cl['id'],)))
    fmt=lambda v:'$'+f'{v:,}'.replace(',','.')
    values={'nombre':cl['name'],'monto':fmt(p['amount']),'compra':o['number'],'saldo_compra':fmt(balance(c,o['id'])),'saldo_total':fmt(total),'fecha':p['date']}
    text=settings(c)['payment_text'] if template is None else template
    text=re.sub(r'\{(nombre|monto|compra|saldo_compra|saldo_total|fecha)\}',lambda match:str(values[match[1]]),text)
    return cl['id'],text

def process_payment_notices():
    # Claim one at a time. Never retry an uncertain external send.
    with db(True) as c:
        cfg=settings(c)
        if DEMO or not cfg['sending'] or not os.getenv('WA_ACCESS_TOKEN') or not os.getenv('WA_PHONE_NUMBER_ID'):return
        job=c.execute("SELECT n.* FROM payment_notices n JOIN payments p ON p.id=n.payment_id WHERE n.status='pending' AND p.reversed=0 ORDER BY n.payment_id LIMIT 1").fetchone()
        if not job:return
        job=dict(job);c.execute("UPDATE payment_notices SET status='sending' WHERE payment_id=?",(job['payment_id'],))
    try:
        send_message(job['client_id'],job['body'])
        with db(True) as c:c.execute("UPDATE payment_notices SET status='sent' WHERE payment_id=?",(job['payment_id'],))
    except Exception as e:
        with db(True) as c:c.execute("UPDATE payment_notices SET status='review',error=? WHERE payment_id=?",(str(e)[:300],job['payment_id']))

@app.post('/api/payments/<int:pid>/notification/cancel')
def cancel_payment_notice(pid):
    with db(True) as c:c.execute("UPDATE payment_notices SET status='cancelled' WHERE payment_id=? AND status='pending'",(pid,))
    return jsonify(ok=True)


def worker():
    last=0
    while True:
        try:
            process_payment_notices()
            with db() as c:shop_cfg=settings(c)
            if not DEMO and shop_cfg.get('shopify_auto_sync') and shopify_auth.configured(shop_cfg) and time.time()-last>300:
                last=time.time()
                try:sync_shop()
                except Exception as e:
                    with db(True) as c:setval(c,'sync_error',str(e)[:300])
            # Payment dates remain in the ledger. Scheduled collection dates are disabled.
        except Exception:pass
        time.sleep(20)
@app.post('/api/clients/<int:cid>')
def edit_client(cid):
    d=request.get_json(); name=str(d.get('name','')).strip()
    if not name or len(name)>150:raise ValueError('Nombre obligatorio.')
    with db(True) as c:
        one(c,'SELECT id FROM clients WHERE id=?',(cid,))
        c.execute('UPDATE clients SET name=?,phone=?,email=?,notes=? WHERE id=?',(name,phone(d.get('phone','')),str(d.get('email',''))[:200],str(d.get('notes',''))[:2000],cid))
        audit(c,'client_edited',{'id':cid})
    return jsonify(ok=True)

@app.post('/api/import/cindy-review')
def review_cindy():
    from cindy_sources import inspect_files
    fs=request.files.getlist('files')
    if len(fs)!=2:raise ValueError('Selecciona los dos Excel: CLUB CINDYLÚ histórico y CXC del año vigente.')
    files=[]
    for f in fs:
        if not (f.filename or '').lower().endswith('.xlsx'):raise ValueError('Usa archivos .xlsx de Excel.')
        content=f.read(25*1024*1024+1)
        if len(content)>25*1024*1024:raise ValueError('Cada Excel debe pesar hasta 25 MB.')
        files.append((f.filename,content))
    payload=inspect_files(files)
    with db() as c:review=cindy_import.plan(c,payload,balance)
    token=secrets.token_hex(24)
    folder=DATA/'imports';folder.mkdir(exist_ok=True)
    staged={'owner':session['user'],'created':now(),'payload':payload,'review':review}
    target=folder/(token+'.json');target.write_text(json.dumps(staged,ensure_ascii=False),encoding='utf8');target.chmod(0o600)
    return jsonify(token=token,summary=payload['summary'],sheets=payload['sheets'],warnings=payload['warnings'],
                   review={k:v for k,v in review.items() if k not in ('matches','replace_ids','fingerprint')})

@app.post('/api/import/cindy-confirm')
def confirm_cindy():
    d=request.get_json() or {};token=str(d.get('token') or '')
    if not re.fullmatch(r'[a-f0-9]{48}',token):raise ValueError('Analiza nuevamente los dos Excel con el importador actualizado.')
    path=DATA/'imports'/(token+'.json')
    if not path.is_file():raise ValueError('La revisión ya no está disponible. Analiza nuevamente los Excel.')
    staged=json.loads(path.read_text(encoding='utf8'))
    if staged['owner']!=session['user'] or dt.datetime.now(dt.timezone.utc)-dt.datetime.fromisoformat(staged['created'])>dt.timedelta(hours=12):
        raise ValueError('La revisión venció o pertenece a otro acceso. Analiza otra vez los Excel.')
    with db() as c:
        check=cindy_import.plan(c,staged['payload'],balance)
        if check['already_imported']:return jsonify(check['result'])
        if check['blocked']:raise ValueError(' '.join(check['blocked'][:4]))
        if check['fingerprint']!=staged['review']['fingerprint']:raise ValueError('Hubo cambios desde la revisión. Analiza otra vez antes de importar.')
        backup_dir=DATA/'backups';backup_dir.mkdir(exist_ok=True)
        backup_path=backup_dir/('antes-reestructuracion-'+token+'.sqlite3')
        out=sqlite3.connect(backup_path)
        try:c.backup(out)
        finally:out.close()
        backup_path.chmod(0o600)
    with db(True) as c:
        result=cindy_import.apply(c,staged['payload'],staged['review'],now,pay,balance)
        audit(c,'cindy_sources_restructured',{'digest':staged['payload']['digest'],**result})
    return jsonify(result)

@app.post('/api/import/preview')
def import_preview():
    import csv,unicodedata
    f=request.files['file']; content=f.read(5*1024*1024+1)
    if len(content)>5*1024*1024:raise ValueError('Excel o CSV: máximo 5 MB.')
    if f.filename.lower().endswith('.xlsx'):
        from openpyxl import load_workbook
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            if sum(i.file_size for i in z.infolist())>30*1024*1024:raise ValueError('Excel demasiado grande.')
        book=load_workbook(io.BytesIO(content),read_only=True,data_only=True)
        sheet=book.worksheets[0]; records=list(__import__('itertools').islice(sheet.values,1002));book.close()
    else:
        text=content.decode('utf-8-sig'); delimiter=';' if text.splitlines()[0].count(';')>text.splitlines()[0].count(',') else ','
        records=list(csv.reader(io.StringIO(text),delimiter=delimiter))
    if not records or len(records)>1001:raise ValueError('Importa hasta 1000 filas por archivo.')
    def norm(s):return ''.join(x for x in unicodedata.normalize('NFD',str(s or '').strip().lower()) if unicodedata.category(x)!='Mn')
    keys=[norm(v) for v in records[0]]
    if 'nombre' not in keys or 'telefono' not in keys:raise ValueError('La primera fila debe incluir nombre y telefono. Opcionales: correo, deuda, fecha.')
    result=[]
    for i,row in enumerate(records[1:],2):
        if not any(x not in ('',None) for x in row):continue
        vals=dict(zip(keys,row)); name=str(vals.get('nombre') or '').strip()
        try:
            p=phone(vals.get('telefono')); debt=amount(vals.get('deuda') or vals.get('saldo') or 0)
            tot=amount(vals.get('total') or vals.get('total_compra') or debt)
            if tot<debt:tot=debt
            ins_cnt=amount(vals.get('cuotas') or 0)
            art=str(vals.get('articulo') or 'Saldo inicial importado (Excel/CSV)').strip()[:250]
            venc=date(vals['vencimiento']) if vals.get('vencimiento') else today()
            if not name or not p:raise ValueError('Falta nombre o teléfono.')
            value={'name':name,'phone':p,'email':str(vals.get('correo') or ''),'debt':debt,'total':tot,'installments':min(ins_cnt,60),'article':art,'first_due':venc,'date':date(vals['fecha']) if vals.get('fecha') else today()}
            result.append({'row':i,'data':value})
        except Exception as e:result.append({'row':i,'error':str(e)})
    return jsonify(rows=result)

@app.post('/api/import/confirm')
def import_confirm():
    data=request.get_json().get('rows',[])
    if len(data)>1000:raise ValueError('Máximo 1000 filas.')
    inserted=0;skipped=0
    with db(True) as c:
        for d in data:
            p=phone(d.get('phone'));name=str(d.get('name','')).strip()[:150];debt=amount(d.get('debt',0))
            if not p or not name:raise ValueError('Nombre y teléfono obligatorios.')
            if c.execute('SELECT id FROM clients WHERE phone=?',(p,)).fetchone():skipped+=1;continue
            cid=c.execute('INSERT INTO clients(name,phone,email,notes) VALUES(?,?,?,?)',(name,p,str(d.get('email',''))[:200],'Importada desde Excel/CSV')).lastrowid
            if debt:
                tot=max(amount(d.get('total',debt)),debt)
                art=str(d.get('article') or 'Saldo inicial importado (no es un pedido de Shopify)')[:250]
                oid=c.execute('INSERT INTO orders(client_id,number,purchased,total,base_paid,items,source,updated) VALUES(?,?,?,?,?,?,?,?)',(cid,'SALDO-'+str(cid),date(d.get('date',today())),tot,tot-debt,json.dumps([{'title':art,'quantity':1}],ensure_ascii=False),'excel',now())).lastrowid
            inserted+=1
        audit(c,'clients_imported',{'inserted':inserted,'skipped':skipped})
    return jsonify(inserted=inserted,skipped=skipped)

@app.get('/api/import/template')
def import_template():
    return send_file(io.BytesIO('nombre;telefono;correo;deuda;fecha\n'.encode('utf-8-sig')),mimetype='text/csv',download_name='Plantilla-clientas.csv',as_attachment=True)


init()
with db(True) as c:create_shopify_client_files(c)
if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--no-browser',action='store_true');args=parser.parse_args()
    host=os.getenv('CINDY_HOST','127.0.0.1');port=int(os.getenv('PORT','8765'))
    threading.Thread(target=worker,daemon=True).start()
    if not args.no_browser:
        import webbrowser
        threading.Timer(1,lambda:webbrowser.open('http://localhost:'+str(port))).start()
    print('Cindy Lú disponible en http://localhost:'+str(port),flush=True)
    from waitress import serve
    serve(app,host=host,port=port,threads=8)





