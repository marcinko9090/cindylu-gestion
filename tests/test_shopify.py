import copy
import io
import json
import os
import unittest
import urllib.error
from unittest.mock import patch
import test_app as base
import app as a
import shopify_auth as auth

class ShopifyAuthTests(unittest.TestCase):
    def setUp(self):
        auth._cache.clear()
        self.env=patch.dict(os.environ, {'SHOPIFY_CLIENT_ID':'client-test', 'SHOPIFY_CLIENT_SECRET':'secret-test', 'SHOPIFY_DOMAIN':'cindylu.myshopify.com'})
        self.env.start();self.addCleanup(self.env.stop)
    def response(self, token='token-test', expiry=86399):
        return io.BytesIO(json.dumps({'access_token':token,'expires_in':expiry}).encode())
    def test_exchange_cache_and_expiry(self):
        with patch.object(auth.urllib.request,'urlopen',side_effect=[self.response(),self.response('renewed')]) as net,patch.object(auth.time,'monotonic',return_value=100) as clock:
            self.assertEqual(auth.access_token({}),'token-test')
            self.assertEqual(auth.access_token({}),'token-test');self.assertEqual(net.call_count,1)
            req=net.call_args.args[0]
            self.assertEqual(req.full_url,'https://cindylu.myshopify.com/admin/oauth/access_token')
            self.assertIn(b'grant_type=client_credentials',req.data)
            self.assertIn(b'client_secret=secret-test',req.data)
            clock.return_value=86500
            self.assertEqual(auth.access_token({}),'renewed');self.assertEqual(net.call_count,2)
    def test_domain_validation_before_network(self):
        with patch.dict(os.environ,{'SHOPIFY_DOMAIN':'evil.example/path'}),patch.object(auth.urllib.request,'urlopen') as net:
            with self.assertRaises(ValueError):auth.access_token({})
            net.assert_not_called()
    def test_secret_rotation_invalidates_cache(self):
        with patch.object(auth.urllib.request,'urlopen',side_effect=[self.response(),self.response('rotated')]) as net:
            auth.access_token({})
            with patch.dict(os.environ,{'SHOPIFY_CLIENT_SECRET':'new-secret'}):
                self.assertEqual(auth.access_token({}),'rotated')
            self.assertEqual(net.call_count,2)
    def test_errors_do_not_expose_secrets(self):
        error=urllib.error.HTTPError('https://cindylu.myshopify.com',401,'secret-test',{},None)
        with patch.object(auth.urllib.request,'urlopen',side_effect=error):
            with self.assertRaises(ValueError) as raised:auth.access_token({})
            self.assertNotIn('secret-test',str(raised.exception))
    def test_missing_secret_does_not_fall_back(self):
        with patch.dict(os.environ,{'SHOPIFY_CLIENT_SECRET':''}),patch.object(auth.urllib.request,'urlopen') as net:
            with self.assertRaises(ValueError):auth.access_token({'shopify_token':'old-token'})
            net.assert_not_called()
    def test_legacy_token_supported(self):
        with patch.dict(os.environ,{'SHOPIFY_CLIENT_ID':'','SHOPIFY_CLIENT_SECRET':'','SHOPIFY_ACCESS_TOKEN':''}):
            self.assertEqual(auth.access_token({'shopify_token':'legacy'}),'legacy')

class ShopifyReconciliationTests(unittest.TestCase):
    setUp=base.FinanceTests.setUp
    def order(self):
        return {'id':'gid://shopify/Order/1','name':'#1','createdAt':a.now(),'cancelledAt':None,
                'customer':{'id':'gid://shopify/Customer/1','displayName':'Javiera González','phone':'+56 9 0000 0001'},
                'currentTotalPriceSet':{'shopMoney':{'amount':'100001','currencyCode':'CLP'}},
                'totalOutstandingSet':{'shopMoney':{'amount':'0','currencyCode':'CLP'}},
                'lineItems':{'nodes':[{'title':'Labial','quantity':2}],'pageInfo':{'hasNextPage':False}}}
    def excel(self):
        with a.db(True) as c:
            c.execute("UPDATE orders SET source='excel',base_paid=1000 WHERE id=?",(self.oid,))
            a.make_plan(c,{'order_id':self.oid,'count':3,'first':'2027-01-01'})
            a.pay(c,{'order_id':self.oid,'amount':20000,'operation':'shopify-test-payment'})
            c.execute("UPDATE clients SET notes='COD 19 · HCUCH' WHERE id=?",(self.cid,))
    def test_link_preserves_ledger_and_is_idempotent(self):
        self.excel();order=self.order()
        with a.db() as c:
            before={t:a.rows(c,'SELECT * FROM '+t) for t in ['payments','allocations','installments','clients']}
            initial=a.balance(c,self.oid)
        with a.db(True) as c:
            self.assertEqual(a.import_shop_order(c,order,allow_new=False),'linked')
            self.assertEqual(a.import_shop_order(c,order,allow_new=False),'updated')
        with a.db() as c:
            self.assertEqual(c.execute('SELECT COUNT(*) FROM orders').fetchone()[0],1)
            self.assertEqual(a.balance(c,self.oid),initial)
            for t in before:self.assertEqual(a.rows(c,'SELECT * FROM '+t),before[t])
            o=a.one(c,'SELECT * FROM orders WHERE id=?',(self.oid,))
            self.assertEqual(json.loads(o['items'])[0]['title'],'Labial');self.assertEqual(o['base_paid'],1000)
    def test_collisions_do_not_create_new_debt(self):
        self.excel()
        for change in ['phone','total','cancelled','number-duplicate']:
            with self.subTest(change=change),a.db(True) as c:
                order=self.order()
                if change=='phone':order['customer']['phone']='56911112222'
                if change=='total':order['currentTotalPriceSet']['shopMoney']['amount']='200000'
                if change=='cancelled':order['cancelledAt']=a.now()
                if change=='number-duplicate':
                    c.execute("INSERT INTO orders(client_id,number,purchased,total,items,updated) VALUES(?,'#1','2026-01-01',5,'[]',?)",(self.cid,a.now()))
                n=c.execute('SELECT COUNT(*) FROM orders').fetchone()[0]
                self.assertEqual(a.import_shop_order(c,order,allow_new=False),'conflict')
                self.assertEqual(c.execute('SELECT COUNT(*) FROM orders').fetchone()[0],n)
                self.assertFalse(c.execute('SELECT shopify_id FROM orders WHERE id=?',(self.oid,)).fetchone()[0])
    def test_unknown_order_not_imported_even_if_marked_paid(self):
        order=self.order();order['name']='#NEW'
        with a.db(True) as c:
            self.assertEqual(a.import_shop_order(c,order,allow_new=False),'pending')
            self.assertEqual(c.execute('SELECT COUNT(*) FROM orders').fetchone()[0],1)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM clients').fetchone()[0],1)
    def test_sync_reports_pending_and_links(self):
        self.excel();order=self.order();other=copy.deepcopy(order);other['name']='#NEW';other['id']='gid://shopify/Order/2'
        page={'data':{'orders':{'nodes':[order,other],'pageInfo':{'hasNextPage':False}}}}
        with patch.object(a.shopify_auth,'access_token',return_value='fake'),patch.object(a,'httpjson',return_value=page):
            result=a.sync_shop()
        self.assertEqual(result,{'count':2,'linked':1,'updated':0,'pending':1,'conflict':0})
    def test_test_endpoint_does_not_import(self):
        with self.http.session_transaction() as s:s['user']=1;s['csrf']='test'
        with patch.object(a.shopify_auth,'access_token',return_value='fake'),patch.object(a,'httpjson',return_value={'data':{'shop':{'name':'Cindy Lú'},'orders':{'nodes':[]}}}):
            result=self.http.post('/api/shopify/test',json={},headers={'X-CSRF-Token':'test'})
        self.assertEqual(result.json,{'ok':True,'shop':'Cindy Lú'})
        with a.db() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM orders').fetchone()[0],1)
