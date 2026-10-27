import copy
import unittest
from unittest.mock import patch
import test_app as base
import app as a
from shopify_review import review_record,merge_review_records

class OrderReviewTests(unittest.TestCase):
    def setUp(self):
        base.FinanceTests.setUp(self)
        with a.db(True) as c:
            a.setval(c,'shopify_review_orders',[])
        self.order={'id':'gid://shopify/Order/6406','name':'#6406','createdAt':'2026-10-22T10:55:00Z','cancelledAt':None,
                    'customer':{'displayName':'Clienta prueba'},'currentTotalPriceSet':{'shopMoney':{'amount':'48390.00','currencyCode':'CLP'}},
                    'totalOutstandingSet':{'shopMoney':{'amount':'-12990.00','currencyCode':'CLP'}},
                    'lineItems':{'nodes':[{'title':'Producto de prueba','quantity':1}],'pageInfo':{'hasNextPage':False}}}
    def sync(self,orders=None):
        page={'data':{'orders':{'nodes':orders or [self.order],'pageInfo':{'hasNextPage':False}}}}
        with patch.object(a.shopify_auth,'access_token',return_value='fake'),patch.object(a,'httpjson',return_value=page):return a.sync_shop()
    def queue(self):
        with a.db() as c:return a.settings(c)['shopify_review_orders']
    def login(self):
        with self.http.session_transaction() as s:s['user']=1;s['csrf']='test'
    def save(self,item,**kwargs):
        return self.http.post('/api/shopify/review',json={'shopify_id':item['shopify_id'],'fingerprint':item['fingerprint'],'status':'reviewed','note':'Revisado: falta comprobar los pagos.',**kwargs},headers={'X-CSRF-Token':'test'})
    def test_negative_snapshot_preserves_date_value_and_does_not_import(self):
        self.sync();item=self.queue()[0]
        self.assertEqual(item['kind'],'negative');self.assertEqual(item['outstanding'],'-12990.00')
        self.assertEqual(item['purchased'],'2026-10-22T10:55:00Z');self.assertEqual(item['number'],'#6406')
        self.assertEqual(item['client_name'],'Clienta prueba');self.assertEqual(item['shopify_numeric_id'],'6406')
        with a.db() as c:
            self.assertEqual(c.execute('SELECT COUNT(*) FROM orders').fetchone()[0],1)
            self.assertEqual(a.balance(c,self.oid),100001)
    def test_classifies_other_causes_separately(self):
        conflict=copy.deepcopy(self.order);conflict['id']='gid://shopify/Order/1';conflict['name']='#1';conflict['totalOutstandingSet']['shopMoney']['amount']='0'
        new=copy.deepcopy(conflict);new['id']='gid://shopify/Order/2';new['name']='#NEW'
        decimal=copy.deepcopy(new);decimal['id']='gid://shopify/Order/3';decimal['currentTotalPriceSet']['shopMoney']['amount']='48390.25'
        self.sync([self.order,conflict,new,decimal])
        self.assertEqual([r['kind'] for r in self.queue()],['negative','difference','new','amount'])
        self.assertIn('diferentes',self.queue()[1]['reason'])
    def test_review_requires_authentication_csrf_and_observation(self):
        self.sync();item=self.queue()[0]
        self.assertEqual(self.save(item).status_code,401)
        self.login()
        self.assertEqual(self.http.post('/api/shopify/review',json={}).status_code,403)
        self.assertEqual(self.save(item,note='').status_code,400)
        self.assertEqual(self.save(item,status='paid').status_code,400)
        self.assertEqual(self.save(item).status_code,200)
        self.assertEqual(self.queue()[0]['status'],'reviewed')
    def test_note_survives_sync_but_remote_change_requires_review_again(self):
        self.sync();self.login();item=self.queue()[0];self.assertEqual(self.save(item).status_code,200)
        self.sync();self.assertEqual(self.queue()[0]['status'],'reviewed')
        self.order['totalOutstandingSet']['shopMoney']['amount']='-10000.00';self.sync()
        changed=self.queue()[0];self.assertEqual(changed['status'],'pending');self.assertIn('comprobar',changed['previous_note'])
        self.assertEqual(self.save(item).status_code,400)
    def test_review_annotation_does_not_modify_financial_tables(self):
        with a.db() as c:before={t:a.rows(c,'SELECT * FROM '+t) for t in ('clients','orders','payments','installments','allocations')}
        self.sync();self.login();self.save(self.queue()[0])
        with a.db() as c:
            for t in before:self.assertEqual(a.rows(c,'SELECT * FROM '+t),before[t])
    def test_resolved_orders_removed_unseen_orders_retained(self):
        self.sync();old=self.queue()[0]
        self.assertEqual(merge_review_records([old],[],set()),[old])
        self.assertEqual(merge_review_records([old],[],{old['shopify_id']}),[])
