import unittest
import test_app as base
import app as a
from shopify_clients import create_missing
class ShopifyClientFilesTests(unittest.TestCase):
    def tearDown(self):
        with a.db(True) as c:c.execute('DELETE FROM client_codes')
    def setUp(self):
        with a.db(True) as c:c.execute('DELETE FROM client_codes')
        base.FinanceTests.setUp(self)
        with a.db(True) as c:
            c.execute('DELETE FROM client_codes')
            c.execute('INSERT INTO client_codes VALUES(?,?,?,?)',('9000',self.cid,'',''))
        self.records=[{'shopify_id':'gid/order/newfile','customer_id':'gid/customer/newfile','phone':'56999999999','email':'','client_name':'Persona Nueva Prueba','number':'#newfile','purchased':'2026-10-29','financial_status':'PENDING','total':189980,'outstanding':189980,'items':[{'title':'Perfume prueba','quantity':2}],'tags':[]}]
    def test_new_file_code_and_payment_without_duplicates(self):
        with a.db(True) as c:
            result=create_missing(c,self.records,a.phone,a.amount,a.now())
            self.assertEqual(result,{'clients_created':1,'purchases_added':1})
            cid=self.records[0]['client_id']
            self.assertEqual(c.execute('SELECT code FROM client_codes WHERE client_id=?',(cid,)).fetchone()[0],'9001')
            oid=c.execute('SELECT id FROM orders WHERE client_id=?',(cid,)).fetchone()[0]
            a.pay(c,{'order_id':oid,'amount':10000,'date':'2026-10-29','operation':'new-client-payment-operation'})
            self.assertEqual(a.balance(c,oid),179980)
            self.records[0]['client_id']=None
            self.assertEqual(create_missing(c,self.records,a.phone,a.amount,a.now()),{'clients_created':0,'purchases_added':0})
    def test_name_collision_is_not_duplicated_or_assigned(self):
        self.records[0]['client_name']='Javiera González'
        with a.db(True) as c:
            result=create_missing(c,self.records,a.phone,a.amount,a.now())
            self.assertEqual(result['clients_created'],0)
            self.assertIsNone(self.records[0].get('client_id'))
