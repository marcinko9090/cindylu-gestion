import unittest
import concurrent.futures
import test_app as base
import app as a
from shopify_review import shopify_items

class SimpleBalanceTests(unittest.TestCase):
    setUp=base.FinanceTests.setUp
    def login(self):
        with self.http.session_transaction() as s:s['user']=1;s['csrf']='test'
    def payment(self,value,op='simple-balance-test-0001'):
        with a.db(True) as c:return a.pay(c,{'order_id':self.oid,'amount':value,'date':'2026-10-27','method':'efectivo','operation':op})
    def test_free_abono_without_plan_and_full_payoff(self):
        pid=self.payment(20000)
        self.assertEqual(self.payment(20000),pid)
        with a.db() as c:
            self.assertEqual(a.balance(c,self.oid),80001)
            p=a.one(c,'SELECT * FROM payments WHERE id=?',(pid,))
            self.assertEqual(p['date'],'2026-10-27');self.assertEqual(p['method'],'efectivo')
            self.assertEqual(c.execute('SELECT COUNT(*) FROM installments').fetchone()[0],0)
        self.payment(80001,'simple-balance-payoff-02')
        with a.db() as c:self.assertEqual(a.balance(c,self.oid),0)
        with self.assertRaises(ValueError):self.payment(1,'simple-balance-extra-03')
    def test_legacy_plan_never_blocks_free_abono_after_total_adjustment(self):
        with a.db(True) as c:
            a.make_plan(c,{'order_id':self.oid,'count':3,'first':'2026-11-01'})
            c.execute('UPDATE orders SET total=150001 WHERE id=?',(self.oid,))
        self.payment(120000)
        with a.db() as c:self.assertEqual(a.balance(c,self.oid),30001)
    def test_unplanned_concurrent_abonos_cannot_overpay(self):
        def pay(i):
            try:self.payment(70000,'simple-concurrent-'+str(i));return True
            except ValueError:return False
        with concurrent.futures.ThreadPoolExecutor(2) as pool:results=list(pool.map(pay,[1,2]))
        self.assertEqual(sum(results),1)
        with a.db() as c:self.assertEqual(a.balance(c,self.oid),30001)
    def test_reverse_free_abono_restores_balance(self):
        pid=self.payment(20000);self.login()
        r=self.http.post('/api/payments/'+str(pid)+'/reverse',json={'reason':'Ingreso duplicado'},headers={'X-CSRF-Token':'test'})
        self.assertEqual(r.status_code,200)
        with a.db() as c:self.assertEqual(a.balance(c,self.oid),100001)
    def test_shopify_products_use_current_quantities(self):
        items=shopify_items({'lineItems':{'nodes':[{'title':'Conservado','quantity':2,'currentQuantity':1},
                                                  {'title':'Eliminado','quantity':1,'currentQuantity':0}]}})
        self.assertEqual(items,[{'title':'Conservado','quantity':1}])
    def test_no_scheduled_collection_dates_can_be_added(self):
        self.login()
        r=self.http.post('/api/reminders',json={'client_id':self.cid,'at':'2099-01-01T00:00:00Z','body':'Cobro'},headers={'X-CSRF-Token':'test'})
        self.assertEqual(r.status_code,400)
