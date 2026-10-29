import json
import unittest
import test_app as base
import app as a
from statements import snapshot,pdf,purchase_records

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
            self.assertEqual([p['amount'] for p in data['payment_history']],[10000])
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
    def test_hidden_history_does_not_change_display_digest_but_visible_history_does(self):
        with a.db(True) as c:
            _,before=a.statement_preview_data(c,self.cid)
            c.execute("UPDATE cxc_payment_history SET amount=5001 WHERE key='old'")
            _,after=a.statement_preview_data(c,self.cid)
            self.assertEqual(before['digest'],after['digest'])
            self.assertEqual(before['balance'],after['balance'])
            c.execute("UPDATE cxc_payment_history SET date='2026-10-26' WHERE key='old'")
            _,visible=a.statement_preview_data(c,self.cid)
            self.assertNotEqual(before['digest'],visible['digest'])
            self.assertEqual(before['balance'],visible['balance'])
    def test_same_purchase_cards_include_closed_and_reference_products_only_once(self):
        with a.db(True) as c:
            items=json.dumps([{'title':'Sombra de prueba','quantity':2}])
            oid=c.execute("INSERT INTO orders(client_id,number,purchased,total,base_paid,items,status,source,shopify_id,updated) VALUES(?,'#6441','2026-10-26',98490,0,?,'restructured','excel','gid/shop/6441',?)",(self.cid,items,a.now())).lastrowid
            cfg=a.settings(c)['shopify_pending_orders'];cfg[0]['items']=[]
            a.setval(c,'shopify_pending_orders',cfg)
            paid=c.execute("INSERT INTO orders(client_id,number,purchased,total,base_paid,items,updated) VALUES(?,'#paid-detail','2026-10-01',10000,10000,?,?)",(self.cid,items,a.now())).lastrowid
            c.execute("INSERT INTO orders(client_id,number,purchased,total,items,status,updated) VALUES(?,'#cancelled','2026-10-28',9999,?,'cancelled',?)",(self.cid,items,a.now()))
            data=snapshot(c,self.cid,a.balance,'28/10/2026')
            self.assertEqual([o['number'] for o in data['purchases']],['#6441','#paid-detail'])
            self.assertEqual(data['purchases'][0]['items'][0]['title'],'Sombra de prueba')
            self.assertEqual(data['balance'],90000)
            _,before=a.statement_preview_data(c,self.cid)
            c.execute('UPDATE orders SET items=? WHERE id=?',(json.dumps([{'title':'Sombra corregida','quantity':2}]),oid))
            _,after=a.statement_preview_data(c,self.cid)
            self.assertNotEqual(before['digest'],after['digest'])
    def test_reference_cards_do_not_supply_other_order_or_cancelled_products(self):
        local=[{'shopify_id':'gid/one','number':'#1','total':2000,'purchased':'2026-10-01','status':'restructured','source':'excel','items':[{'title':'Producto de prueba','quantity':1}]},
               {'shopify_id':'gid/two','number':'#2','total':3000,'purchased':'2026-10-02','status':'cancelled','source':'shopify','items':[{'title':'Anulado','quantity':1}]}]
        remote=[{'shopify_id':'gid/other','number':'#1','total':2000,'purchased':'2026-10-01','items':[]}]
        cards=purchase_records(local,remote)
        self.assertEqual(len(cards),2)
        self.assertEqual(cards[0]['items'],[])
        self.assertTrue(cards[1]['previous'])
        self.assertNotIn('Anulado',str(cards))


    def test_enriched_historical_products_appear_without_new_debt(self):
        with a.db(True) as c:
            c.execute("INSERT INTO purchase_history VALUES(?,?,?,?,?,?,?,?,?,?,?)",('test-historical',self.cid,'#5701','2026-04-27','2026-04',119990,'purchase','PEDIDO',json.dumps([{'title':'Producto histórico de prueba','quantity':1}]),'excel'))
            data=snapshot(c,self.cid,a.balance,'now')
            self.assertIn('#5701',[p['number'] for p in data['purchases']])
            self.assertEqual(data['balance'],90000)
            self.assertTrue(pdf(data).getvalue().startswith(b'%PDF'))

if __name__=='__main__':unittest.main()

