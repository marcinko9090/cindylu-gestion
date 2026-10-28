"""Two distinct sources: settled purchase history and CXC monthly debt snapshots.

No FIFO, installment inference, fabricated purchase dates or product attributes.
This module only reads files. Private payloads must never be committed to Git.
"""
import datetime as dt
import hashlib
import io
import json
import re
import unicodedata
import zipfile
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from openpyxl import load_workbook

MONTHS = dict(zip(('enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre').split(), range(1,13)))

def norm(v):
    return ' '.join(''.join(c for c in unicodedata.normalize('NFD',str(v or '').strip().lower()) if unicodedata.category(c)!='Mn').split())

def code(v):
    try:
        n=Decimal(str(v))
        return str(int(n)) if n.is_finite() and n==int(n) and n>0 else ''
    except (InvalidOperation,ValueError,TypeError):return ''

def integer(v):
    if v in (None,'') or isinstance(v,bool):return None
    try:
        n=Decimal(str(v))
        if n.is_finite() and n==int(n) and abs(n)<=10**11:return int(n)
    except (InvalidOperation,ValueError,TypeError):pass
    return None

def iso(v):
    if isinstance(v,dt.datetime):v=v.date()
    if isinstance(v,dt.date):return v.isoformat() if v.year>=2000 else ''
    text=str(v or '').strip()
    for fmt in ('%Y-%m-%d','%d/%m/%Y','%d-%m-%Y'):
        try:
            d=dt.datetime.strptime(text[:10],fmt).date()
            return d.isoformat() if d.year>=2000 else ''
        except ValueError:pass
    return ''

def phone(v):
    text=str(v or '').strip().removesuffix('.0')
    digits=re.sub(r'\D','',text)
    if len(digits)==9 and digits.startswith('9'):digits='56'+digits
    # An 8 digit entry cannot establish a country/mobile prefix reliably.
    return digits if re.fullmatch(r'[1-9]\d{9,14}',digits) else ''

def text(v):return str(v or '').strip()

def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def inspect_files(files):
    contacts={};history=[];snapshots=[];warnings=[];sheets=[];ambiguous=[];cut_periods=[]
    for filename,content in files:
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            if sum(i.file_size for i in z.infolist())>100*1024*1024:raise ValueError('El libro descomprimido supera 100 MB.')
        book=load_workbook(io.BytesIO(content),read_only=True,data_only=True)
        try:
            for sh in book:
                stream=iter(sh.values);head=next(stream,());h=[norm(v) for v in head]
                title=norm(sh.title);count=0;sheet_period=''
                if title in MONTHS and 'saldo vigente' in h:
                    year_match=re.search(r'(?<!\d)(20\d{2})(?!\d)',filename)
                    if not year_match:raise ValueError('El nombre del libro CXC debe indicar el año de sus hojas mensuales.')
                    sheet_period=f'{int(year_match[1]):04d}-{MONTHS[title]:02d}'
                    cut_periods.append(sheet_period)
                for rownum,row in enumerate(stream,2):
                    if not any(v is not None for v in row):continue
                    count+=1
                    if count>100000:raise ValueError('La hoja supera 100.000 filas.')
                    r=list(row)+[None]*max(0,18-len(row));k=code(r[0]);name=text(r[1])
                    src={'file':filename,'sheet':sh.title,'row':rownum}
                    if title=='datos clientas' and k and name and 'sin registrar' not in norm(name):
                        contact={'code':k,'name':name,'work':text(r[2]) if norm(r[2])!='sin codigo' else '',
                                 'phone':phone(r[3]),'raw_phone':text(r[3]) if norm(r[3])!='sin codigo' else '',
                                 'email':'','source':src}
                        if k in contacts and norm(contacts[k]['name'])!=norm(name):
                            warnings.append({'kind':'contact_conflict','code':k,**src})
                        else:contacts[k]=contact
                    elif title=='club cindylu' and k and integer(r[5]) is not None:
                        amt=integer(r[5]);kind=norm(r[3]);detail=text(r[4]);d=iso(r[2]);ref=code(r[3])
                        # Payment markers may have a positive MONTO. They are never sales.
                        is_payment=kind in ('a','abono') or norm(detail)=='abono' or norm(detail).startswith('pago con tarjeta')
                        if is_payment:
                            if kind=='a' and norm(detail)=='pedido':ambiguous.append({'code':k,'name':name,'amount':amt,'date':d,'detail':detail,**src})
                            continue
                        if not amt:continue
                        if not d:
                            y=integer(r[11]);m=integer(r[10])
                            period=f'{y:04d}-{m:02d}' if y and m and 2000<=y<=2100 and 1<=m<=12 else ''
                        else:period=d[:7]
                        history.append({'code':k,'name':name,'date':d,'period':period,'number':'#'+ref if ref else '',
                                        'category_code':'' if ref else text(r[3]),'detail':detail,'amount':amt,
                                        'kind':'discount' if norm(detail)=='descuento' or kind=='dcto' else 'purchase' if amt>0 else 'adjustment',
                                        'items':[],'source':src})
                    elif title in MONTHS and 'saldo vigente' in h and k:
                        # Only monthly CXC sheets carry live debt. Never use the CXC tab in CLUB.
                        period=sheet_period
                        start=integer(r[5]);delta=integer(r[6]);end=integer(r[8])
                        if start is None:
                            warnings.append({'kind':'missing_balance','code':k,**src});continue
                        computed=start+(delta or 0)
                        final=computed if end is None else end
                        if end is not None and end!=computed:warnings.append({'kind':'balance_difference','code':k,'computed':computed,'stated':end,**src})
                        snapshots.append({'code':k,'name':name,'work':text(r[2]),'period':period,'opening':start,
                                          'payment':abs(delta) if delta is not None and delta<0 else 0,
                                          'movement':delta or 0,'payment_date':iso(r[7]),'balance':final,
                                          'last_payment':abs(integer(r[3]) or 0),'last_payment_date':iso(r[4]),'source':src})
                sheets.append({'file':filename,'sheet':sh.title,'rows':count})
        finally:book.close()
    if not contacts and not history:raise ValueError('Falta el libro histórico con DATOS CLIENTAS / CLUB CINDYLÚ.')
    if not snapshots:raise ValueError('Falta CXC con hojas mensuales y SALDO VIGENTE.')
    # Preserve valid client codes found only in movements or CXC, even without phone/work.
    for entry in history+snapshots:
        k=entry['code'];name=entry['name']
        if k not in contacts and name and norm(name) not in ('error','clienta sin registrar'):
            contacts[k]={'code':k,'name':name,'phone':'','raw_phone':'','work':entry.get('work',''),'email':'','source':entry['source']}
    latest=max(cut_periods)
    latest_rows=[s for s in snapshots if s['period']==latest]
    if not latest_rows:raise ValueError('La última hoja mensual no tiene saldos válidos. Revisa el corte '+latest+'.')
    counts=Counter(s['code'] for s in latest_rows)
    for k,n in counts.items():
        if n>1:warnings.append({'kind':'duplicate_current_code','code':k,'count':n,'period':latest})
    # One historical order can span several lines; aggregate only an exact client/order/date key.
    groups={};ungrouped=[]
    for row in history:
        if row['number'] and row['kind']=='purchase':
            key=(row['code'],row['number'],row['date'],row['period'])
            if key not in groups:groups[key]={**row,'sources':[],'details':[],'amount':0}
            g=groups[key];g['amount']+=row['amount'];g['sources'].append(row['source']);g['details'].append(row['detail'])
        else:ungrouped.append({**row,'sources':[row['source']],'details':[row['detail']]})
    history=list(groups.values())+ungrouped
    for r in history:
        r['key']=digest([r['code'],r['number'],r['date'],r['sources']])
        r['detail']=' · '.join(dict.fromkeys(r['details']))
        r['settled']=True
    history.sort(key=lambda r:(r['date'] or r['period'],int(r['code']),r['number'],r['key']))
    # MONTO entries are actual movements. ULTIMO ABONO is a reference, not a second payment.
    movements=defaultdict(list);references=defaultdict(list)
    for r in snapshots:
        if r['payment']:
            key=(r['code'],r['payment_date'],r['payment'])
            movements[key].append({'period':r['period'],**r['source']})
        if r['last_payment']:
            key=(r['code'],r['last_payment_date'],r['last_payment'])
            references[key].append({'period':r['period'],**r['source']})
    payments=[]
    for key in movements.keys()|references.keys():
        k,d,amt=key;refs=movements.get(key,[])
        # Same-day equal payments in multiple MONTO cells are ambiguous, never silently dropped.
        if len(refs)>1:warnings.append({'kind':'repeated_payment','code':k,'date':d,'amount':amt,'sources':refs})
        payments.append({'key':digest(key),'code':k,'date':d,'amount':amt,
                         'kind':'movement' if refs else 'last_payment_reference','number':'',
                         'sources':refs+references.get(key,[]),'current':any(s['period']==latest for s in refs)})
    payments.sort(key=lambda p:(p['date'] or '9999',int(p['code']),p['amount']))
    monthly=defaultdict(lambda:{'purchases':0,'discounts_adjustments':0,'total':0})
    for r in history:
        m=monthly[(r['code'],r['period'])];m['total']+=r['amount']
        if r['kind']=='purchase':m['purchases']+=r['amount']
        else:m['discounts_adjustments']+=r['amount']
    monthly=[{'code':k,'period':period,**v} for (k,period),v in sorted(monthly.items())]
    missing=set(s['code'] for s in latest_rows)-contacts.keys()
    for k in sorted(missing):warnings.append({'kind':'missing_current_contact','code':k})
    summary={'contacts':len(contacts),'historical_purchases':sum(r['kind']=='purchase' for r in history),
             'historical_months':len(monthly),'historical_total':sum(r['amount'] for r in history),
             'period':latest,'current_clients':len(counts),'opening':sum(s['opening'] for s in latest_rows),
             'current_payments':sum(s['payment'] for s in latest_rows),
             'receivable':sum(max(0,s['balance']) for s in latest_rows),
             'credit':sum(max(0,-s['balance']) for s in latest_rows),
             'net_balance':sum(s['balance'] for s in latest_rows),'payment_entries':len(payments),
             'ambiguous_historical_rows':len(ambiguous),'invalid_phones':sum(bool(c['raw_phone']) and not c['phone'] for c in contacts.values())}
    payload={'format':'cindylu-sources-v2','contacts':sorted(contacts.values(),key=lambda c:int(c['code'])),
             'history':history,'monthly':monthly,'snapshots':snapshots,'payments':payments,
             'ambiguous':ambiguous,'warnings':warnings,'sheets':sheets,'summary':summary}
    payload['digest']=digest(payload)
    return payload
