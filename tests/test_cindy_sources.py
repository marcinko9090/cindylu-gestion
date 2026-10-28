import copy
import datetime as dt
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import cindy_sources as source
import cindy_import as importer

class Sheet:
    def __init__(self,title,values):self.title=title;self.values=values
class Book(list):
    def close(self):pass

def fixture():
    history=Book([
        Sheet('DATOS CLIENTAS',[
            ['COD','CLIENTA','LUGAR DE TRABAJO','CELULAR'],
            [1,'Ana','Hospital',912345678],[2,'Bea','Colegio','telefono incompleto']]),
        Sheet('CLUB CINDYLÚ',[
            ['COD','CLIENTA','FECHA','CODIGO','DETALLE','MONTO'],
            [1,'Ana',dt.date(2024,1,2),100,'Labial marca X 5 ml',4000],
            [1,'Ana',dt.date(2024,1,3),'A','ABONO',4000],
            [1,'Ana',dt.date(2024,1,4),'DCTO','DESCUENTO',-50],
            [1,'Ana',dt.date(2024,1,5),'A','PEDIDO',100],
            [2,'Bea',dt.date(2024,1,6),101,'PEDIDO',5000]])])
    head=['COD','clienta','LUGAR DE TRABAJO','ULTIMO ABONO','FECHA','SALDO VIGENTE','MONTO','FECHA','SALDO']
    cxc=Book([
        Sheet('ENERO',[head,[1,'Ana','Hospital',500,dt.date(2025,12,1),4000,-1000,dt.date(2026,1,10),3000]]),
        Sheet('FEBRERO',[head,[1,'Ana','Hospital',1000,dt.date(2026,1,10),3000,-1000,dt.date(2026,2,10),2000]]),
        Sheet('OCTUBRE',[head,[1,'Ana','Hospital',1000,dt.date(2026,2,10),2000,-500,dt.date(2026,10,10),1500],
                        [2,'Bea','Colegio',0,None,-40,None,None,None]])])
    b=io.BytesIO()
    with zipfile.ZipFile(b,'w') as z:z.writestr('fixture','')
    with patch.object(source,'load_workbook',side_effect=[history,cxc]):
        return source.inspect_files([('CLUB.xlsx',b.getvalue()),('CXC 2026.xlsx',b.getvalue())])

class SourceRulesTests(unittest.TestCase):
    def test_history_paid_payments_not_sales_and_no_fifo(self):
        p=fixture()
        self.assertEqual(p['summary']['historical_total'],8950)
        self.assertEqual(p['summary']['ambiguous_historical_rows'],1)
        self.assertTrue(all(h['settled'] for h in p['history']))
        self.assertEqual(p['summary']['receivable'],1500)
        self.assertEqual(p['summary']['credit'],40)
        self.assertEqual(p['summary']['net_balance'],1460)
        self.assertEqual(p['summary']['opening'],1960)
        self.assertEqual(p['summary']['current_payments'],500)
        self.assertEqual(len(p['payments']),4) # three movements + one older reference
        self.assertTrue(all(not r['number'] for r in p['payments']))
        self.assertTrue(all(not h['items'] for h in p['history']))
        self.assertEqual(p['contacts'][1]['raw_phone'],'telefono incompleto')
    def test_dates_are_not_invented(self):
        self.assertEqual(source.iso(None),'');self.assertEqual(source.iso(dt.time(0,0)),'')
        self.assertEqual(source.iso('31/02/2026'),'')
        self.assertEqual(source.phone('12345678'),'')
        self.assertEqual(source.phone('912345678'),'56912345678')

class StagedImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        root=Path(__file__).resolve().parents[1]
        spec=importlib.util.spec_from_file_location('cindy_sources_test_app',root/'app.py')
        cls.a=importlib.util.module_from_spec(spec)
        with patch.dict(os.environ,{'CINDY_DATA':cls.tmp.name,'CINDY_DEMO':'0'}):spec.loader.exec_module(cls.a)
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def setUp(self):
        with self.a.db(True) as c:
            for t in ['cindy_batches','historical_ambiguities','cxc_payment_history','cxc_snapshots','cxc_accounts','purchase_history','client_codes',
                      'statement_sends','payment_notices','allocations','payments','installments','messages','receipts','orders','clients','audit']:
                c.execute('DELETE FROM '+t)
        self.p=fixture();self.http=self.a.app.test_client()
        with self.http.session_transaction() as s:s['user']=1;s['csrf']='sources-test'
    def review(self):
        with patch.object(source,'inspect_files',return_value=self.p):
            r=self.http.post('/api/import/cindy-review',data={'files':[(io.BytesIO(b'a'),'CLUB.xlsx'),(io.BytesIO(b'b'),'CXC 2026.xlsx')]},headers={'X-CSRF-Token':'sources-test'})
        self.assertEqual(r.status_code,200,r.json);return r.json
    def confirm(self,token):
        return self.http.post('/api/import/cindy-confirm',json={'token':token},headers={'X-CSRF-Token':'sources-test'})
    def test_exact_cut_history_and_idempotency_no_messages(self):
        r=self.review();out=self.confirm(r['token'])
        self.assertEqual(out.status_code,200,out.json)
        self.assertEqual(self.confirm(r['token']).json,out.json)
        with self.a.db() as c:
            self.assertEqual(c.execute('SELECT COUNT(*) FROM clients').fetchone()[0],2)
            self.assertEqual(c.execute('SELECT SUM(amount) FROM purchase_history').fetchone()[0],8950)
            o=dict(c.execute('SELECT * FROM orders').fetchone())
            self.assertEqual(o['source'],'cxc');self.assertEqual(o['purchased'],'2026-10')
            self.assertEqual(self.a.balance(c,o['id']),1500)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM payments').fetchone()[0],1)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM cxc_payment_history').fetchone()[0],4)
            self.assertEqual(c.execute('SELECT SUM(credit) FROM cxc_accounts').fetchone()[0],40)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM payment_notices').fetchone()[0],0)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM messages').fetchone()[0],0)
        self.assertTrue(list((Path(self.tmp.name)/'backups').glob('*.sqlite3')))
    def test_stale_preview_rolls_back_and_new_payments_are_preserved(self):
        r=self.review()
        with self.a.db(True) as c:c.execute("INSERT INTO clients(name) VALUES('Cambio concurrente')")
        self.assertEqual(self.confirm(r['token']).status_code,400)
        with self.a.db() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM purchase_history').fetchone()[0],0)
    def test_historical_record_without_identity_is_preserved_unassigned(self):
        row=copy.deepcopy(self.p['history'][0]);row.update(code='999',name='ERROR',key='unassigned-purchase')
        self.p['history'].append(row)
        r=self.review();self.assertEqual(self.confirm(r['token']).status_code,200)
        with self.a.db() as c:
            unknown=[json.loads(x[0]) for x in c.execute('SELECT data FROM historical_ambiguities WHERE client_id IS NULL')]
            self.assertEqual(len(unknown),1);self.assertEqual(unknown[0]['code'],'999')
            self.assertEqual(unknown[0]['reason'],'unidentified_historical_client')
            self.assertFalse(c.execute("SELECT 1 FROM clients WHERE name='ERROR'").fetchone())
    def test_archives_only_known_excel_and_preserves_exact_shopify_products(self):
        with self.a.db(True) as c:
            cid=c.execute("INSERT INTO clients(name,notes) VALUES('Ana','COD 1 · Hospital')").lastrowid
            c.execute("INSERT INTO orders(client_id,shopify_id,number,purchased,total,items,source,updated) VALUES(?,'gid/100','#100','2024-01-02',4000,?,'excel',?)",(cid,json.dumps([{'title':'Labial X tono Rosa 5 ml','quantity':2}]),self.a.now()))
        r=self.review();self.assertEqual(r['review']['archive_count'],1)
        self.assertEqual(self.confirm(r['token']).status_code,200)
        with self.a.db() as c:
            self.assertEqual(c.execute("SELECT status FROM orders WHERE number='#100'").fetchone()[0],'restructured')
            self.assertIn('tono Rosa',c.execute("SELECT items FROM purchase_history WHERE number='#100'").fetchone()[0])
            self.assertEqual(c.execute('SELECT COUNT(*) FROM orders').fetchone()[0],2)
    def test_real_platform_payment_blocks_overwrite(self):
        with self.a.db(True) as c:
            cid=c.execute("INSERT INTO clients(name,notes) VALUES('Ana','COD 1 · Hospital')").lastrowid
            oid=c.execute("INSERT INTO orders(client_id,number,purchased,total,items,source,updated) VALUES(?,'#old','2026-01-02',4000,'[]','excel',?)",(cid,self.a.now())).lastrowid
            self.a.pay(c,{'order_id':oid,'amount':100,'date':'2026-10-28','operation':'real-platform-payment-123456'})
        r=self.review();self.assertTrue(r['review']['blocked'])
        self.assertEqual(self.confirm(r['token']).status_code,400)
        with self.a.db() as c:self.assertEqual(self.a.balance(c,oid),3900)
    def test_unknown_token_and_legacy_import_cannot_write(self):
        self.assertEqual(self.confirm('a'*48).status_code,400)
        self.assertEqual(self.http.post('/api/import/cindy-confirm',json={'records':[{'name':'fake'}]},headers={'X-CSRF-Token':'sources-test'}).status_code,400)
        self.assertEqual(self.http.post('/api/import/cindy-confirm',json={}).status_code,403)

if __name__=='__main__':unittest.main()
