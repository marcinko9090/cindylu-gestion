"""Reversible, staged import of Cindy's settled history and authoritative CXC cut."""
import datetime as dt
import json
import re
from cindy_sources import MONTHS, digest, norm

def init_schema(c):
    c.executescript('''
    CREATE TABLE IF NOT EXISTS cindy_batches(digest TEXT PRIMARY KEY,created TEXT NOT NULL,result TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS client_codes(code TEXT PRIMARY KEY,client_id INTEGER NOT NULL REFERENCES clients(id),work TEXT NOT NULL,raw_phone TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS purchase_history(key TEXT PRIMARY KEY,client_id INTEGER NOT NULL REFERENCES clients(id),number TEXT NOT NULL,date TEXT NOT NULL,period TEXT NOT NULL,amount INTEGER NOT NULL,kind TEXT NOT NULL,detail TEXT NOT NULL,items TEXT NOT NULL,source TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS cxc_snapshots(key TEXT PRIMARY KEY,client_id INTEGER NOT NULL REFERENCES clients(id),period TEXT NOT NULL,opening INTEGER NOT NULL,movement INTEGER NOT NULL,balance INTEGER NOT NULL,source TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS cxc_payment_history(key TEXT PRIMARY KEY,client_id INTEGER NOT NULL REFERENCES clients(id),date TEXT NOT NULL,amount INTEGER NOT NULL,kind TEXT NOT NULL,sources TEXT NOT NULL,current INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS cxc_accounts(client_id INTEGER PRIMARY KEY REFERENCES clients(id),period TEXT NOT NULL,order_id INTEGER REFERENCES orders(id),credit INTEGER NOT NULL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS historical_ambiguities(key TEXT PRIMARY KEY,client_id INTEGER REFERENCES clients(id),data TEXT NOT NULL);
    ''')

def fingerprint(c):
    # Detect edits between review and apply, including sync and any new payments.
    data={t:[tuple(r) for r in c.execute('SELECT * FROM '+t+' ORDER BY 1')] for t in
          ('clients','orders','payments','client_codes','purchase_history','cxc_accounts','cindy_batches','payment_notices')}
    return digest(data)

def plan(c,payload,balance):
    if payload.get('format')!='cindylu-sources-v2':raise ValueError('Formato de importación no reconocido.')
    completed=c.execute('SELECT result FROM cindy_batches WHERE digest=?',(payload['digest'],)).fetchone()
    if completed:return {'already_imported':True,'result':json.loads(completed[0]),'blocked':[],'changes':[]}
    blocked=[];matches={};clients=[dict(r) for r in c.execute('SELECT * FROM clients')]
    coded={}
    for r in c.execute('SELECT code,client_id FROM client_codes'):coded.setdefault(r[0],set()).add(r[1])
    for cl in clients:
        m=re.match(r'^COD\s+(\d+)(?:\s|$)',cl['notes'] or '')
        if m:coded.setdefault(m[1],set()).add(cl['id'])
    lookup={cl['id']:cl for cl in clients}
    for ct in payload['contacts']:
        k=ct['code'];candidates=coded.get(k,set())
        if not candidates and ct['phone']:
            ph=[cl for cl in clients if cl['phone']==ct['phone'] and norm(cl['name'])==norm(ct['name'])]
            # Shared family phone numbers are not identity keys by themselves.
            candidates={cl['id'] for cl in ph if not any(cl['id'] in ids for code,ids in coded.items() if code!=k)}
        if len(candidates)>1:blocked.append('El código '+k+' coincide con más de una ficha existente.');continue
        matches[k]=next(iter(candidates),None)
    seen={}
    for k,cid in matches.items():
        if cid is not None and cid in seen:blocked.append('Los códigos '+seen[cid]+' y '+k+' coinciden con la misma ficha.')
        if cid is not None:seen[cid]=k
    current_month=next(k for k,v in MONTHS.items() if v==int(payload['summary']['period'][5:]))
    for w in payload['warnings']:
        if w['kind'] in ('contact_conflict','duplicate_current_code','missing_current_contact') or (w['kind'] in ('balance_difference','missing_balance') and norm(w.get('sheet'))==current_month):
            blocked.append('Revisar '+w['kind']+' para el código '+w.get('code','')+'.')
    mapped={cid for cid in matches.values() if cid is not None}
    old=[dict(o) for o in c.execute("SELECT * FROM orders WHERE status='active'")]
    replace=[o for o in old if o['source']=='excel' and o['client_id'] in mapped]
    unmatched=[o for o in old if o['source']=='excel' and o['client_id'] not in mapped]
    if unmatched:blocked.append(str(len(unmatched))+' compras Excel no tienen una coincidencia por código; revisa esas fichas antes de reemplazar saldos.')
    for o in old:
        if o['client_id'] in mapped and o['source'] not in ('excel',) and balance(c,o['id'])>0:
            blocked.append('La ficha '+lookup[o['client_id']]['name']+' tiene una compra activa ajena al Excel ('+o['number']+'). Hay que conciliarla antes.')
    ids={o['id'] for o in replace}
    for p in c.execute('SELECT * FROM payments WHERE reversed=0'):
        if p['order_id'] in ids and not str(p['operation']).startswith(('cindy-','sheet-','exc-')):
            blocked.append('Hay abonos registrados en la plataforma después de importar Excel. Hay que conciliarlos antes de cambiar el saldo de su compra.')
            break
    if c.execute('SELECT 1 FROM cxc_accounts LIMIT 1').fetchone():blocked.append('Ya existe una reestructuración CXC. Para actualizarla hay que conciliar los abonos posteriores; no se superpondrán dos cortes.')
    pending=c.execute("SELECT 1 FROM payment_notices WHERE status IN ('pending','sending') LIMIT 1").fetchone()
    if pending:blocked.append('Hay avisos de pago pendientes de envío; resuélvelos antes de cambiar los registros asociados.')
    current={r['code']:r for r in payload['snapshots'] if r['period']==payload['summary']['period']}
    for r in current.values():
        if r['movement']>0 or (r['balance']>=0 and r['opening']<0):blocked.append('El corte vigente contiene un cargo o crédito que requiere revisión: COD '+r['code'])
        if r['payment'] and (not r['payment_date'] or r['balance']<0):blocked.append('El abono vigente tiene fecha ausente o excede la deuda: COD '+r['code'])
    changes=[]
    for ct in payload['contacts']:
        cid=matches.get(ct['code']);entry=current.get(ct['code']);before=sum(balance(c,o['id']) for o in old if o['client_id']==cid) if cid else 0
        after=max(0,entry['balance']) if entry else 0
        if before or after or (entry and entry['balance']<0):changes.append({'code':ct['code'],'name':ct['name'],'before':before,'after':after,'credit':max(0,-entry['balance']) if entry else 0})
    return {'already_imported':False,'matches':matches,'replace_ids':sorted(ids),'archive_count':len(ids),'blocked':list(dict.fromkeys(blocked)),
            'new_clients':sum(cid is None for cid in matches.values()),'changes':changes,'fingerprint':fingerprint(c)}

def apply(c,payload,review,now,pay,balance):
    check=plan(c,payload,balance)
    if check['already_imported']:return check['result']
    if check['blocked']:raise ValueError(' '.join(check['blocked'][:4]))
    if review['fingerprint']!=check['fingerprint']:raise ValueError('Los datos cambiaron desde la revisión. Analiza otra vez antes de importar.')
    mapped={};new=0
    for ct in payload['contacts']:
        cid=check['matches'][ct['code']]
        if cid is None:
            notes='COD '+ct['code']+(' · '+ct['work'] if ct['work'] else '')
            cid=c.execute('INSERT INTO clients(name,phone,email,notes) VALUES(?,?,?,?)',(ct['name'],ct['phone'],ct['email'],notes)).lastrowid;new+=1
        else:
            # Fill blanks, keeping manually edited contact data intact.
            c.execute("UPDATE clients SET phone=CASE WHEN phone='' THEN ? ELSE phone END,email=CASE WHEN email='' THEN ? ELSE email END WHERE id=?",(ct['phone'],ct['email'],cid))
        c.execute('INSERT INTO client_codes VALUES(?,?,?,?)',(ct['code'],cid,ct['work'],ct['raw_phone']))
        mapped[ct['code']]=cid
    historical=0
    for r in payload['history']:
        cid=mapped.get(r['code'])
        if cid is None:continue
        items=r['items']
        if r['number'] and r['amount']>0:
            old=list(c.execute("SELECT items FROM orders WHERE client_id=? AND number=? AND total=? AND shopify_id IS NOT NULL",(cid,r['number'],r['amount'])))
            if len(old)==1:items=json.loads(old[0]['items'])
        c.execute('INSERT INTO purchase_history VALUES(?,?,?,?,?,?,?,?,?,?)',(r['key'],cid,r['number'],r['date'],r['period'],r['amount'],r['kind'],r['detail'],json.dumps(items,ensure_ascii=False),json.dumps(r['sources'],ensure_ascii=False)));historical+=1
    for r in payload['snapshots']:
        cid=mapped.get(r['code'])
        if cid is not None:c.execute('INSERT INTO cxc_snapshots VALUES(?,?,?,?,?,?,?)',(digest(r),cid,r['period'],r['opening'],r['movement'],r['balance'],json.dumps(r['source'],ensure_ascii=False)))
    for r in payload['payments']:
        cid=mapped.get(r['code'])
        if cid is not None:c.execute('INSERT INTO cxc_payment_history VALUES(?,?,?,?,?,?,?)',(r['key'],cid,r['date'],r['amount'],r['kind'],json.dumps(r['sources'],ensure_ascii=False),int(r['current'])))
    for r in payload['ambiguous']:
        c.execute('INSERT INTO historical_ambiguities VALUES(?,?,?)',(digest(r),mapped.get(r['code']),json.dumps(r,ensure_ascii=False)))
    # Archive, never delete. The backup and all prior payment links remain available.
    for oid in check['replace_ids']:c.execute("UPDATE orders SET status='restructured',updated=? WHERE id=?",(now(),oid))
    created=0
    for r in payload['snapshots']:
        if r['period']!=payload['summary']['period']:continue
        cid=mapped[r['code']];oid=None
        if r['balance']>0 or r['payment']:
            if r['movement']>0 or r['opening']<0 or r['opening']-r['payment']!=r['balance'] or r['balance']<0:
                raise ValueError('El corte vigente tiene un movimiento que requiere conciliación manual: COD '+r['code'])
            # Month precision is deliberate: this is a debt cut, not a dated purchase.
            number='CXC-'+r['period']+'-'+r['code']
            oid=c.execute("INSERT INTO orders(client_id,number,purchased,total,base_paid,items,source,updated) VALUES(?,?,?,?,0,?,'cxc',?)",(cid,number,r['period'],r['opening'],json.dumps([{'title':'Saldo del corte CXC '+r['period']+' · productos y pedido no indicados en este archivo','quantity':1}],ensure_ascii=False),now())).lastrowid
            if r['payment']:
                if not r['payment_date']:raise ValueError('El abono vigente no tiene fecha: COD '+r['code'])
                pay(c,{'order_id':oid,'amount':r['payment'],'date':r['payment_date'],'method':'otro','note':'Abono registrado en CXC '+r['period']+'; sin medio ni pedido informado.','operation':'cxc-v2-'+digest([r['code'],r['period']])[:45]})
            if balance(c,oid)!=r['balance']:raise ValueError('No se pudo conciliar el saldo del código '+r['code'])
            created+=1
        c.execute('INSERT INTO cxc_accounts VALUES(?,?,?,?)',(cid,r['period'],oid,max(0,-r['balance'])))
    result={'clients':len(mapped),'created_clients':new,'historical_records':historical,'archived_orders':len(check['replace_ids']),
            'current_accounts':created,'receivable':payload['summary']['receivable'],'credit':payload['summary']['credit'],
            'net_balance':payload['summary']['net_balance'],'period':payload['summary']['period']}
    c.execute('INSERT INTO cindy_batches VALUES(?,?,?)',(payload['digest'],now(),json.dumps(result)))
    return result

def enrich_history(c,o,items,total,remote_phone,remote_email,sid):
    number=str(o.get('name','')).strip();normalized=number.lstrip('#').strip()
    candidates=[dict(r) for r in c.execute("SELECT h.*,c.phone,c.email,c.shopify_id FROM purchase_history h JOIN clients c ON c.id=h.client_id WHERE trim(ltrim(trim(h.number),'#'))=? AND h.kind='purchase'",(normalized,))]
    if len(candidates)!=1:return False
    h=candidates[0]
    if h['amount']!=total or o.get('cancelledAt'):return False
    if sid and h['shopify_id'] and sid!=h['shopify_id']:return False
    if h['phone'] and remote_phone and h['phone']!=remote_phone:return False
    if not ((sid and sid==h['shopify_id']) or (remote_phone and remote_phone==h['phone']) or (remote_email and remote_email==str(h['email']).lower())):return False
    c.execute('UPDATE purchase_history SET items=? WHERE key=?',(json.dumps(items,ensure_ascii=False),h['key']))
    return True
