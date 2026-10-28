"""Field UI and its existing per-purchase API contract, using an isolated database."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]

class FieldCollectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        spec=importlib.util.spec_from_file_location('cindy_field_test_app',ROOT/'app.py')
        cls.a=importlib.util.module_from_spec(spec)
        with patch.dict(os.environ,{'CINDY_DATA':cls.temp.name,'CINDY_DEMO':'1'}):
            spec.loader.exec_module(cls.a)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def setUp(self):
        a=self.a
        with a.db(True) as c:
            for table in ['statement_sends','payment_notices','allocations','payments','installments','messages','receipts','orders','clients','audit']:
                c.execute('DELETE FROM '+table)
            self.cid=c.execute("INSERT INTO clients(name,notes) VALUES('Ana Norte','Trabajo: Hospital')").lastrowid
            self.other=c.execute("INSERT INTO clients(name,notes) VALUES('Bea Sur','Trabajo: Colegio')").lastrowid
            self.orders=[]
            for cid,number,total in [(self.cid,'#11',20000),(self.cid,'#12',10000),(self.other,'#21',7000)]:
                self.orders.append(c.execute("INSERT INTO orders(client_id,number,purchased,total,items,updated) VALUES(?,?,'2026-10-01',?,'[]',?)",(cid,number,total,a.now())).lastrowid)
        self.http=a.app.test_client()
        with self.http.session_transaction() as s:s['user']=1;s['csrf']='field-test'
    def post(self,**overrides):
        payload={'client_id':self.cid,'order_id':self.orders[1],'amount':5000,'date':'2026-10-28','method':'efectivo','operation':'field-contract-00000001','note':'Cobro en terreno · Hospital','notify':False}
        payload.update(overrides)
        return self.http.post('/api/payments',json=payload,headers={'X-CSRF-Token':'field-test'})
    def balances(self):
        with self.a.db() as c:return [self.a.balance(c,oid) for oid in self.orders]
    def test_selected_purchase_only_and_repeat_is_idempotent(self):
        first=self.post();second=self.post()
        self.assertEqual(first.status_code,200);self.assertEqual(second.json['id'],first.json['id'])
        self.assertEqual(self.balances(),[20000,5000,7000])
        with self.a.db() as c:
            self.assertEqual(c.execute('SELECT COUNT(*) FROM payments').fetchone()[0],1)
            p=self.a.one(c,'SELECT * FROM payments')
            self.assertEqual(p['order_id'],self.orders[1]);self.assertEqual(p['date'],'2026-10-28');self.assertEqual(p['method'],'efectivo')
            self.assertIn('Hospital',p['note'])
            self.assertEqual(c.execute('SELECT COUNT(*) FROM payment_notices').fetchone()[0],0)
        state=self.http.get('/api/state').json
        total=sum(o['balance'] for o in state['orders'] if o['client_id']==self.cid and o['status']=='active')
        self.assertEqual(total,25000)
    def test_cannot_exceed_selected_balance_or_pay_blocked_purchase(self):
        self.assertEqual(self.post(amount=15000).status_code,400)
        for amount in [0,-1,1.5]:self.assertEqual(self.post(amount=amount).status_code,400)
        with self.a.db(True) as c:c.execute("UPDATE orders SET review='Revisar Shopify' WHERE id=?",(self.orders[1],))
        self.assertEqual(self.post().status_code,400)
        self.assertEqual(self.balances(),[20000,10000,7000])
    def test_payment_still_requires_session_and_csrf(self):
        self.assertEqual(self.http.post('/api/payments',json={}).status_code,403)
        with self.http.session_transaction() as s:s.clear()
        self.assertEqual(self.post().status_code,401)
        self.assertEqual(self.balances(),[20000,10000,7000])
    @unittest.skipUnless(shutil.which('node'),'Node is required for the field UI test')
    def test_field_ui_workflow(self):
        result=subprocess.run(['node',str(ROOT/'tests/test_field.cjs')],capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)
