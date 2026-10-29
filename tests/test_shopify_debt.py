import unittest
import test_app as base
import app as a
class ShopifyDebtTests(unittest.TestCase):
    def setUp(self):
        base.FinanceTests.setUp(self)
        with self.http.session_transaction() as s:s['user']='test';s['csrf']='test'
        self.record={'shopify_id':'gid/Order/new-debt','number':'#new-debt','fingerprint':'current','client_id':self.cid,'purchased':'2026-10-29','total':40000,'outstanding':30000,'financial_status':'PARTIALLY_PAID','items':[{'title':'Producto de prueba','quantity':1}]}
        with a.db(True) as c:a.setval(c,'shopify_pending_orders',[self.record])
        self.payload={'shopify_id':self.record['shopify_id'],'fingerprint':'current','client_id':self.cid,'outstanding':30000,'confirm_not_in_balance':True}
    def post(self):
        return self.http.post('/api/shopify/pending/add-debt',json=self.payload,headers={'X-CSRF-Token':'test'})
    def test_partial_and_retry_only_add_pending_once(self):
        response=self.post();self.assertEqual(response.status_code,200)
        oid=response.json['order_id']
        self.assertEqual(self.post().json['order_id'],oid)
        with a.db() as c:
            self.assertEqual(a.balance(c,oid),30000)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM payments WHERE order_id=?',(oid,)).fetchone()[0],0)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM orders WHERE shopify_id=?',(self.record['shopify_id'],)).fetchone()[0],1)
    def test_stale_confirmation_and_wrong_client_are_blocked(self):
        for field,value in [('fingerprint','stale'),('client_id',self.cid+999),('outstanding',40000),('confirm_not_in_balance',False)]:
            old=self.payload[field];self.payload[field]=value
            self.assertEqual(self.post().status_code,400)
            self.payload[field]=old
    def test_existing_number_is_not_added(self):
        with a.db(True) as c:c.execute('UPDATE orders SET number=? WHERE id=?',(self.record['number'],self.oid))
        self.assertEqual(self.post().status_code,400)
    def test_invalid_pending_is_blocked(self):
        with a.db(True) as c:
            self.record['outstanding']=-1
            a.setval(c,'shopify_pending_orders',[self.record])
        self.assertEqual(self.post().status_code,400)
