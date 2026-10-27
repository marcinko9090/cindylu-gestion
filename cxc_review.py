"""Lectura, conciliación e importación del formato real de Cindy Lú (CLUB CINDYLÚ + DATOS CLIENTAS + CXC 2026)."""
import io, zipfile, unicodedata, datetime as dt, re, calendar
from collections import Counter
from decimal import Decimal, InvalidOperation
from openpyxl import load_workbook

def norm(v):
    return ''.join(c for c in unicodedata.normalize('NFD', str(v or '').strip().lower()) if unicodedata.category(c) != 'Mn')

def cod(v):
    try:
        d = Decimal(str(v))
        return str(int(d)) if d.is_finite() and d == int(d) and d > 0 else None
    except (InvalidOperation, TypeError, ValueError):
        return None

def clean_amount(v):
    if v is None or v == '' or isinstance(v, bool):
        return 0
    if isinstance(v, (int, float)):
        return int(round(float(v)))
    s = re.sub(r'[^0-9-]', '', str(v))
    try:
        return int(s) if s and s != '-' else 0
    except ValueError:
        return 0

def clean_phone(v):
    if v is None or isinstance(v, bool):
        return ''
    s = str(v).strip()
    if s.endswith('.0'):
        s = s[:-2]
    digits = ''.join(x for x in s if x.isdigit())
    if len(digits) == 9 and digits.startswith('9'):
        return '56' + digits
    if len(digits) == 8:
        return '569' + digits
    if 8 <= len(digits) <= 14 and not digits.startswith('0'):
        return digits
    return ''

def clean_date(v, fallback):
    if isinstance(v, dt.datetime):
        d = v.date()
        return d.isoformat() if d.year >= 2020 else fallback
    if isinstance(v, dt.date):
        return v.isoformat() if v.year >= 2020 else fallback
    s = str(v or '').strip()[:10]
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', s):
        return s if s >= '2020-01-01' else fallback
    m = re.fullmatch(r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})', s)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            res = dt.date(y, mo, d).isoformat()
            return res if res >= '2020-01-01' else fallback
        except ValueError:
            pass
    return fallback

def infer_installments_count(total, payments, default_n=3):
    for p in payments:
        for candidate in (p.get('full_payment', 0), p.get('amount', 0)):
            if candidate and candidate > 0:
                ratio = total / candidate
                for k in (2, 3, 4, 5, 6):
                    if abs(ratio - k) <= 0.12:
                        return k
    return default_n if default_n > 0 else 3

def add_one_month(iso_date):
    try:
        d = dt.date.fromisoformat(str(iso_date)[:10])
    except ValueError:
        d = dt.date.today()
    m = d.year * 12 + d.month
    y, mo = divmod(m, 12)
    mo += 1
    return dt.date(y, mo, min(d.day, calendar.monthrange(y, mo)[1])).isoformat()

def reconstruct_client_open_orders(k, ledger_rows, oct_extra=None, default_ins=3):
    """Rebuilds exact open orders and FIFO allocated payments from CLUB CINDYLÚ + monthly abono."""
    orders = []
    payments = []
    for m in ledger_rows:
        amt = m['monto']
        if amt > 0:
            raw_c = m['codigo']
            c_int = cod(raw_c)
            num = ('#' + c_int) if c_int else ('#CL-' + str(k) + '-' + str(m['row']))
            det = m['detalle'] or 'Pedido Cindy Lú'
            if det.upper() == 'PEDIDO' and c_int:
                title = f'Pedido #{c_int}'
            else:
                title = f'{det} ({num})'
            # Merge consecutive/same-order lines for the same client
            if orders and orders[-1]['number'] == num and not c_int is None:
                orders[-1]['total'] += amt
                orders[-1]['item'] = (orders[-1]['item'] + ' + ' + title)[:240]
            else:
                orders.append({
                    'number': num,
                    'date': m['date'],
                    'total': amt,
                    'paid': 0,
                    'payments': [],
                    'item': title
                })
        elif amt < 0:
            payments.append({
                'amount': abs(amt),
                'date': m['date'],
                'source': 'CLUB CINDYLÚ',
                'row': m['row']
            })
    if oct_extra and oct_extra.get('month_abono', 0) < 0:
        ab_amt = abs(oct_extra['month_abono'])
        ab_dt = oct_extra.get('month_date') or dt.date.today().isoformat()
        # Check if an identical payment on the same date is already at the tail of CLUB CINDYLÚ
        already = any(p['amount'] == ab_amt and p['date'] == ab_dt for p in payments[-3:])
        if not already:
            payments.append({
                'amount': ab_amt,
                'date': ab_dt,
                'source': 'Corte ' + oct_extra.get('sheet', 'OCTUBRE'),
                'row': 999999
            })
    o_idx = 0
    for p in payments:
        rem = p['amount']
        prev_orders = []
        while rem > 0 and o_idx < len(orders):
            o = orders[o_idx]
            need = o['total'] - o['paid']
            if need <= 0:
                o_idx += 1
                continue
            take = min(rem, need)
            o['paid'] += take
            note_parts = [f"Abono {p['source']} ({p['date']})"]
            if take < p['amount']:
                if prev_orders:
                    prev_txt = ', '.join(f"{po[0]} (${po[1]:,})".replace(',', '.') for po in prev_orders)
                    note_parts.append(f"de un abono total de ${p['amount']:,} (cerró {prev_txt} y aplicó ${take:,} a {o['number']})".replace(',', '.'))
                else:
                    note_parts.append(f"parte de abono total de ${p['amount']:,}".replace(',', '.'))
            o['payments'].append({
                'amount': take,
                'date': p['date'],
                'full_payment': p['amount'],
                'note': ' · '.join(note_parts),
                'op_seed': f"cindy-{k}-{o['number']}-{p['row']}-{take}"
            })
            prev_orders.append((o['number'], take))
            rem -= take
            if o['paid'] >= o['total']:
                o_idx += 1
    open_orders = []
    for o in orders:
        bal = o['total'] - o['paid']
        if bal > 0:
            o['balance'] = bal
            o['installments'] = infer_installments_count(o['total'], o['payments'], default_ins)
            o['first_due'] = add_one_month(o['date'])
            open_orders.append(o)
    return open_orders

def inspect_files(files):
    summaries = []
    sources = []
    contacts = {}
    movements = Counter()
    ledger_by_cod = {}
    ambiguities = 0
    invalid_phones = 0
    flexible_sheets = []
    today_iso = dt.date.today().isoformat()

    for filename, content in files:
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            if sum(i.file_size for i in z.infolist()) > 100 * 1024 * 1024:
                raise ValueError('Libro demasiado grande para esta revisión.')
        w = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        try:
            for sheet in w:
                stream = iter(sheet.values)
                head = next(stream, ())
                h = [norm(x) for x in head]
                n = 0
                codes = set()
                source = {}
                bad = 0
                abonos = 0
                sales = 0
                other = 0
                flex_rows = []
                is_club_ledger = (norm(sheet.title) == 'club cindylu')
                is_datos_clientas = (norm(sheet.title) == 'datos clientas')

                col_name = next((i for i, col in enumerate(h) if col in ('nombre', 'clienta', 'cliente', 'nombre clienta', 'nombre completo')), None)
                col_work = next((i for i, col in enumerate(h) if col in ('lugar de trabajo', 'trabajo', 'empresa', 'institucion')), None)
                col_phone = next((i for i, col in enumerate(h) if col in ('telefono', 'celular', 'whatsapp', 'fono', 'tel')), None)
                col_debt = next((i for i, col in enumerate(h) if col in ('saldo', 'saldo vigente', 'deuda', 'pendiente', 'saldo pendiente', 'por pagar')), None)
                col_total = next((i for i, col in enumerate(h) if col in ('total', 'monto', 'venta', 'valor', 'total compra', 'monto compra')), None)
                col_paid = next((i for i, col in enumerate(h) if col in ('abonado', 'pagado', 'abono', 'abonos', 'pie', 'pagos previos')), None)
                col_item = next((i for i, col in enumerate(h) if col in ('articulo', 'articulos', 'producto', 'detalle', 'descripcion', 'prenda')), None)
                col_ins = next((i for i, col in enumerate(h) if col in ('cuotas', 'n cuotas', 'cantidad cuotas', 'numero cuotas')), None)
                col_date = next((i for i, col in enumerate(h) if col in ('fecha', 'fecha compra', 'vencimiento', 'primer vencimiento')), None)

                for r_idx, r in enumerate(stream, start=2):
                    if not any(v is not None for v in r):
                        continue
                    n += 1
                    if n > 100000:
                        raise ValueError('La hoja supera 100.000 registros.')
                    k = cod(r[0] if r else None)
                    if k:
                        codes.add(k)
                    if is_datos_clientas and k:
                        if len(r) > 3:
                            name = str(r[1] or '').strip()
                            work = str(r[2] or '').strip()
                            p = str(r[3] or '').strip()
                            if 'sin registrar' in norm(name):
                                continue
                            if p.endswith('.0'):
                                p = p[:-2]
                            cleaned_p = clean_phone(p)
                            if p and norm(p) not in ('sin codigo', '') and not cleaned_p:
                                invalid_phones += 1
                            if k in contacts and norm(contacts[k]['name']) != norm(name):
                                ambiguities += 1
                            contacts[k] = {'code': k, 'name': name, 'work': work if norm(work) != 'sin codigo' else '', 'phone': cleaned_p, 'raw_phone': p}
                    elif is_club_ledger and len(r) > 5 and k:
                        typ = norm(r[3])
                        detail = str(r[4] or '').strip()
                        detail_norm = norm(detail)
                        value = r[5]
                        if isinstance(value, (int, float)) and not isinstance(value, bool):
                            amt_int = int(round(float(value)))
                        else:
                            amt_int = 0
                        if amt_int < 0 or typ == 'a' or detail_norm == 'abono':
                            abonos += 1
                        elif amt_int > 0:
                            sales += 1
                        else:
                            other += 1
                        movements[k] += 1
                        if amt_int != 0:
                            ledger_by_cod.setdefault(k, []).append({
                                'row': r_idx,
                                'date': clean_date(r[2] if len(r) > 2 else None, '2026-01-01'),
                                'codigo': r[3],
                                'detalle': detail,
                                'monto': amt_int
                            })
                    elif 'saldo vigente' in h and k:
                        idx_sv = h.index('saldo vigente')
                        sv_val = r[idx_sv] if idx_sv < len(r) else None
                        if not isinstance(sv_val, (int, float)) or isinstance(sv_val, bool):
                            bad += 1
                            continue
                        sv_int = int(round(float(sv_val)))
                        # Check monthly payment column (MONTO in Col G and FECHA in Col H, SALDO in Col I)
                        m_abono = 0
                        m_date = today_iso
                        if 'monto' in h:
                            idx_m = h.index('monto')
                            if idx_m < len(r) and isinstance(r[idx_m], (int, float)) and not isinstance(r[idx_m], bool):
                                m_abono = int(round(float(r[idx_m])))
                            if idx_m + 1 < len(r) and r[idx_m + 1] is not None:
                                m_date = clean_date(r[idx_m + 1], today_iso)
                        eff_val = sv_int + m_abono
                        if 'saldo' in h:
                            idx_s = h.index('saldo')
                            if idx_s < len(r) and isinstance(r[idx_s], (int, float)) and not isinstance(r[idx_s], bool):
                                eff_val = int(round(float(r[idx_s])))
                        if k in source:
                            bad += 1
                        w_val = str(r[col_work] or '').strip() if col_work is not None and col_work < len(r) else ''
                        source[k] = {
                            'balance': eff_val,
                            'saldo_vigente': sv_int,
                            'month_abono': m_abono,
                            'month_date': m_date,
                            'name': str(r[1] or '').strip(),
                            'work': w_val
                        }
                    elif col_name is not None and (col_debt is not None or col_total is not None):
                        nm = str(r[col_name] if col_name < len(r) and r[col_name] is not None else '').strip()
                        if nm and 'sin registrar' not in norm(nm) and norm(nm) not in ('total', 'totales', 'suma', 'error'):
                            ph = clean_phone(r[col_phone]) if col_phone is not None and col_phone < len(r) else ''
                            tot = clean_amount(r[col_total]) if col_total is not None and col_total < len(r) else 0
                            pd_amt = clean_amount(r[col_paid]) if col_paid is not None and col_paid < len(r) else 0
                            dbt = clean_amount(r[col_debt]) if col_debt is not None and col_debt < len(r) else max(0, tot - pd_amt)
                            if tot <= 0 and dbt > 0:
                                tot = dbt + pd_amt
                            itm = str(r[col_item] if col_item is not None and col_item < len(r) and r[col_item] is not None else 'Saldo / Compra importada de Excel').strip()
                            ins_cnt = clean_amount(r[col_ins]) if col_ins is not None and col_ins < len(r) else 0
                            dt_val = clean_date(r[col_date] if col_date is not None and col_date < len(r) else None, today_iso)
                            if dbt > 0 or tot > 0 or ph:
                                flex_rows.append({'code': k or '', 'name': nm, 'phone': ph, 'total': max(tot, dbt), 'paid': max(0, max(tot, dbt) - dbt), 'balance': max(0, dbt), 'item': itm[:250], 'installments': min(max(ins_cnt, 0), 60), 'date': dt_val})

                summaries.append({'file': filename, 'sheet': sheet.title, 'rows': n, 'codes': len(codes), 'payments': abonos, 'other_entries': sales + other, 'invalid_balances': bad})
                if 'saldo vigente' in h and source:
                    sources.append({'file': filename, 'sheet': sheet.title, 'balances': source, 'invalid': bad})
                elif flex_rows:
                    flexible_sheets.append({'file': filename, 'sheet': sheet.title, 'rows': flex_rows})
        finally:
            w.close()

    result = []
    importable = []

    # 1. If CLUB CINDYLÚ ledger is present, build the master reconciled portfolio with exact open #PEDIDO orders and payments
    oct_source = next((s for s in sources if norm(s['sheet']) == 'octubre'), None)
    cxc_source = next((s for s in sources if norm(s['sheet']) == 'cxc'), None)
    if ledger_by_cod:
        reconciled_records = []
        active_cods = sorted(
            (set(oct_source['balances'].keys()) if oct_source else set()) |
            {k for k, ms in ledger_by_cod.items() if sum(m['monto'] for m in ms) > 0},
            key=lambda x: int(x)
        )
        for k in active_cods:
            ct = contacts.get(k, {})
            oct_entry = oct_source['balances'].get(k) if oct_source else None
            cxc_entry = cxc_source['balances'].get(k) if cxc_source else None
            nm = ct.get('name') or (oct_entry or {}).get('name') or (cxc_entry or {}).get('name') or f'Clienta COD {k}'
            if 'incobrable' in norm(nm) and not oct_entry:
                continue
            ph = ct.get('phone') or ''
            work = ct.get('work') or (oct_entry or {}).get('work') or (cxc_entry or {}).get('work') or ''
            oct_extra = {'month_abono': oct_entry['month_abono'], 'month_date': oct_entry['month_date'], 'sheet': 'OCTUBRE'} if oct_entry else None
            open_orders = reconstruct_client_open_orders(k, ledger_by_cod.get(k, []), oct_extra=oct_extra, default_ins=3)
            for o in open_orders:
                reconciled_records.append({
                    'code': k,
                    'name': nm,
                    'phone': ph,
                    'work': work,
                    'order_number': o['number'],
                    'total': o['total'],
                    'paid': o['paid'],
                    'balance': o['balance'],
                    'item': o['item'],
                    'installments': o['installments'],
                    'date': o['date'],
                    'first_due': o['first_due'],
                    'payments': o['payments']
                })
        if reconciled_records:
            tot_rec = sum(r['balance'] for r in reconciled_records)
            uniq_cl = len({r['code'] for r in reconciled_records})
            importable.append({
                'id': 'reconciled::cindy_master',
                'label': f'★ Cartera Activa Conciliada (Pedidos # + Abonos + Octubre) · {uniq_cl} clientas · {len(reconciled_records)} pedidos abiertos · $' + format(tot_rec, ',').replace(',', '.'),
                'records': reconciled_records
            })

    # 2. Build importable datasets for each balance cut sheet (enriched with DATOS CLIENTAS and CLUB CINDYLÚ when available)
    for src in sources:
        items_list = []
        for k, val in src['balances'].items():
            ct = contacts.get(k, {})
            nm = ct.get('name') or val.get('name') or ('Clienta COD ' + str(k))
            ph = ct.get('phone') or ''
            work = ct.get('work') or val.get('work') or ''
            bal = int(round(val['balance']))
            sv = int(round(val.get('saldo_vigente', bal)))
            m_ab = int(round(val.get('month_abono', 0)))
            m_dt = val.get('month_date') or today_iso
            if bal > 0:
                if ledger_by_cod and k in ledger_by_cod and norm(src['sheet']) in ('octubre', 'cxc'):
                    oct_extra = {'month_abono': m_ab, 'month_date': m_dt, 'sheet': src['sheet']} if m_ab < 0 else None
                    open_o = reconstruct_client_open_orders(k, ledger_by_cod[k], oct_extra=oct_extra, default_ins=3)
                    if open_o and sum(o['balance'] for o in open_o) == bal:
                        for o in open_o:
                            items_list.append({
                                'code': k, 'name': nm, 'phone': ph, 'work': work,
                                'order_number': o['number'], 'total': o['total'], 'paid': o['paid'],
                                'balance': o['balance'], 'item': o['item'], 'installments': o['installments'],
                                'date': o['date'], 'first_due': o['first_due'], 'payments': o['payments']
                            })
                        continue
                tot_order = max(sv, bal)
                paid_order = max(0, tot_order - bal)
                pay_list = [{'amount': paid_order, 'date': m_dt, 'full_payment': paid_order, 'note': f"Abono registrado en {src['sheet']} ({m_dt})", 'op_seed': f"sheet-{src['sheet']}-{k}-{paid_order}"}] if paid_order > 0 else []
                items_list.append({
                    'code': k, 'name': nm, 'phone': ph, 'work': work,
                    'total': tot_order, 'paid': paid_order, 'balance': bal,
                    'item': 'Saldo corte ' + src['sheet'] + ' (' + src['file'] + ')',
                    'installments': infer_installments_count(tot_order, pay_list, 3) if pay_list else 0,
                    'date': today_iso, 'payments': pay_list
                })
        result.append({
            'file': src['file'],
            'sheet': src['sheet'],
            'clients': len(src['balances']),
            'total': sum(x['balance'] for x in src['balances'].values() if x['balance'] > 0),
            'saldo_vigente_total': sum(x.get('saldo_vigente', x['balance']) for x in src['balances'].values()),
            'month_collected': sum(abs(x.get('month_abono', 0)) for x in src['balances'].values() if x.get('month_abono', 0) < 0),
            'negative': sum(x['balance'] < 0 for x in src['balances'].values()),
            'missing_contacts': sum(k not in contacts for k in src['balances']) if contacts else None
        })
        importable.append({
            'id': src['file'] + '::' + src['sheet'],
            'label': src['sheet'] + ' (' + src['file'] + ') · ' + str(len({x['code'] or x['name'] for x in items_list})) + ' clientas · $' + format(sum(x['balance'] for x in items_list), ',').replace(',', '.'),
            'records': items_list
        })

    for flex in flexible_sheets:
        recs = flex['rows']
        for r in recs:
            if r['code'] and r['code'] in contacts:
                if not r['phone']:
                    r['phone'] = contacts[r['code']].get('phone', '')
                if not r.get('work'):
                    r['work'] = contacts[r['code']].get('work', '')
        importable.append({
            'id': flex['file'] + '::' + flex['sheet'],
            'label': flex['sheet'] + ' (' + flex['file'] + ') · ' + str(len(recs)) + ' registros · $' + format(sum(x['balance'] for x in recs), ',').replace(',', '.'),
            'records': recs
        })

    if contacts and not importable:
        recs = [{'code': k, 'name': c['name'], 'phone': c['phone'], 'work': c['work'], 'total': 0, 'paid': 0, 'balance': 0, 'item': 'Contacto DATOS CLIENTAS', 'installments': 0, 'date': today_iso} for k, c in contacts.items()]
        importable.append({'id': 'contacts::datos_clientas', 'label': 'Directorio DATOS CLIENTAS · ' + str(len(recs)) + ' clientas', 'records': recs})

    comparisons = []
    if len(sources) > 1:
        left = next((s for s in sources if norm(s['sheet']) == 'octubre'), None)
        right = next((s for s in sources if norm(s['sheet']) == 'cxc'), None)
        if left and right:
            shared = left['balances'].keys() & right['balances'].keys()
            diff = [k for k in shared if left['balances'][k]['saldo_vigente'] != right['balances'][k]['saldo_vigente']]
            comparisons.append({
                'left': left['file'] + ' / ' + left['sheet'],
                'right': right['file'] + ' / ' + right['sheet'],
                'shared': len(shared),
                'different': len(diff),
                'only_left': len(left['balances'].keys() - right['balances'].keys()),
                'only_right': len([k for k in (right['balances'].keys() - left['balances'].keys()) if right['balances'][k]['balance'] > 0])
            })

    return {
        'sheets': summaries,
        'balance_sources': result,
        'importable_sources': importable,
        'contacts': len(contacts),
        'invalid_phones': invalid_phones,
        'code_conflicts': ambiguities,
        'comparisons': comparisons,
        'notes': [
            'Opción recomendada: "★ Cartera Activa Conciliada" importa cada pedido abierto (#Pedido) con sus abonos reales e imputación por cuota.',
            'En la hoja OCTUBRE se detectan y descuentan automáticamente los 24 abonos ($1.301.836) de la columna MONTO aunque la columna SALDO esté en blanco.',
            'Se cruza automáticamente por COD con DATOS CLIENTAS (nombre, lugar de trabajo y celular +569) y con CLUB CINDYLÚ.',
            'Puedes asignar o ajustar las cuotas de cualquier pedido en cualquier momento desde la ficha de la clienta.'
        ]
    }
