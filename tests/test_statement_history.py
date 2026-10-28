import json
import unittest
import test_app as base
import app as a
from statements import snapshot,pdf

class StatementHistoryTests(unittest.TestCase):
    def setUp(self):
        with a.db(True) as c:
            for table in ('cxc_payment_history','cxc_accounts','cxc_snapshots','client_codes','purchase_history','historical_ambiguities','cindy_batches'):
                c.execute('DELETE FROM '+table)
        base.FinanceTests.setUp(self)
        with a.db(True) as c:
            c.execute("UPDATE orders SET source='cxc',number='CXC-2026-10-1',purchased='2026-10',total=100000,base_paid=0 WHERE id=?",(self.oid,))
            a.pay(c,{'order_id':self.oid,'amount':10000,'date':'2026-10-27','operation':'statement-history-actual-0001'})
            for key,date,amount,kind,current in [('old','2026-09-15',5000,'movement',0),('ref','2026-08-15',7000,'last_payment_reference',0),('current','2026-10-27',10000,'movement',1)]:
                c.execute('INSERT INTO cxc_payment_history VALUES(?,?,?,?,?,?,?)',(key,self.cid,date,amount,kind,'[]',current))
            a.setval(c,'shopify_pending_orders',[{'shopify_id':'gid/shop/6441','number':'#6441','client_id':self.cid,'purchased':'2026-10-26T16:28:00Z','total':98490,'financial_status':'PENDING','items':[{'title':'Perfume marca de prueba 100 ml','quantity':1},{'title':'Base tono Rosa','quantity':2}]}])
    def tearDown(self):
        with a.db(True) as c:c.execute('DELETE FROM cxc_payment_history')
    def test_remote_products_and_excel_history_never_change_debt(self):
        with a.db() as c:
            data=snapshot(c,self.cid,a.balance,'28/10/2026 13:50')
            self.assertEqual(data['balance'],90000)
            self.assertEqual(data['shopify_orders'][0]['total'],98490)
            self.assertEqual([p['amount'] for p in data['payment_history']],[7000,5000,10000])
            self.assertEqual(len(data['orders']),1)
        self.assertTrue(pdf(data).getvalue().startswith(b'%PDF'))
    def test_paid_active_order_abonos_retained_and_archived_excluded(self):
        with a.db(True) as c:
            paid=c.execute("INSERT INTO orders(client_id,number,purchased,total,items,updated) VALUES(?,'#paid','2026-07-01',12345,'[]',?)",(self.cid,a.now())).lastrowid
            a.pay(c,{'order_id':paid,'amount':12345,'date':'2026-07-02','operation':'statement-history-closed-0001'})
            c.execute("INSERT INTO orders(client_id,number,purchased,total,base_paid,items,status,updated) VALUES(?,'#archived','2026-06-01',99999,99999,'[]','restructured',?)",(self.cid,a.now()))
            data=snapshot(c,self.cid,a.balance,'now')
            self.assertEqual(data['balance'],90000)
            self.assertIn(12345,[p['amount'] for p in data['payment_history']])
            self.assertNotIn(99999,[p['amount'] for p in data['payment_history']])
    def test_digest_changes_when_excel_history_or_linked_products_change(self):
        with a.db(True) as c:
            _,before=a.statement_preview_data(c,self.cid)
            c.execute("UPDATE cxc_payment_history SET amount=5001 WHERE key='old'")
            _,after=a.statement_preview_data(c,self.cid)
            self.assertNotEqual(before['digest'],after['digest'])
            self.assertEqual(before['balance'],after['balance'])

if __name__=='__main__':unittest.main()
