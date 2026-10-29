import unittest
import test_app as base
import app as a

class DecisionTests(unittest.TestCase):
    def setUp(self):
        base.FinanceTests.setUp(self)
        self.row=dict(shopify_id='decision-order',fingerprint='snapshot-1',number='#DECISION',purchased='2026-10-29',client_id=self.cid,client_name='Prueba',items=[{'quantity':1,'title':'Producto'}],total='5000',outstanding='3000',currency='CLP',kind='new',status='pending',financial_status='PARTIALLY_PAID')
        with a.db(True) as c:
            a.setval(c,'shopify_order_decisions',{})
            a.setval(c,'shopify_review_orders',[self.row])
            a.setval(c,'shopify_pending_orders',[self.row])
        with self.http.session_transaction() as s:s['user']=1;s['csrf']='test'
    def resolve(self,decision,**extra):
        return self.http.post('/api/shopify/review',json={'shopify_id':self.row['shopify_id'],'fingerprint':self.row['fingerprint'],'decision':decision,**extra},headers={'X-CSRF-Token':'test'})
    def test_debt_once_and_accepts_payment(self):
        self.assertEqual(self.resolve('debt').status_code,200)
        self.assertEqual(self.resolve('debt').status_code,200)
        with a.db(True) as c:
            orders=a.rows(c,'SELECT * FROM orders WHERE shopify_id=?',(self.row['shopify_id'],))
            self.assertEqual(len(orders),1)
            oid=orders[0]['id'];self.assertEqual(a.balance(c,oid),3000)
            a.pay(c,{'order_id':oid,'amount':1000,'operation':'review-decision-payment-001','date':'2026-10-29'})
            self.assertEqual(a.balance(c,oid),2000)
            self.assertEqual(a.settings(c)['shopify_pending_orders'],[])
    def test_cash_stays_out_after_sync_helpers(self):
        self.assertEqual(self.resolve('cash').status_code,200)
        with a.db(True) as c:
            a.setval(c,'shopify_pending_orders',[self.row])
            a.create_shopify_client_files(c)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM orders').fetchone()[0],1)
            self.assertEqual(a.settings(c)['shopify_pending_orders'],[])
            self.assertEqual(a.settings(c)['shopify_review_orders'][0]['status'],'reviewed')
        self.assertEqual(self.resolve('debt').status_code,400)
    def test_cash_existing_preserves_history(self):
        with a.db(True) as c:c.execute('UPDATE orders SET shopify_id=? WHERE id=?',(self.row['shopify_id'],self.oid))
        self.assertEqual(self.resolve('cash').status_code,200)
        with a.db() as c:
            self.assertEqual(c.execute('SELECT status FROM orders WHERE id=?',(self.oid,)).fetchone()[0],'cancelled')
            self.assertEqual(c.execute('SELECT COUNT(*) FROM orders').fetchone()[0],1)
    def test_stale_negative_and_unlinked_are_rejected(self):
        self.assertEqual(self.resolve('debt',fingerprint='old').status_code,400)
        for change in ({'outstanding':'-1'},{'client_id':None}):
            with a.db(True) as c:
                row={**self.row,**change};a.setval(c,'shopify_review_orders',[row]);a.setval(c,'shopify_pending_orders',[row])
            self.assertEqual(self.resolve('debt').status_code,400)
