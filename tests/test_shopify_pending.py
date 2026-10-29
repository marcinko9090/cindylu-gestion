import copy
import unittest
from unittest.mock import patch
import test_app as base
import app as a
from shopify_pending import pending_record

class PendingShopifyTests(unittest.TestCase):
    def setUp(self):
        base.FinanceTests.setUp(self)
        self.order={'id':'gid://shopify/Order/6437','name':'#6437','createdAt':'2026-10-26T16:28:00Z',
                    'displayFinancialStatus':'PENDING','cancelledAt':None,
                    'customer':{'id':'gid://shopify/Customer/5','displayName':'Javiera González','phone':'+56 9 0000 0001'},
                    'currentTotalPriceSet':{'shopMoney':{'amount':'201950.00','currencyCode':'CLP'}},
                    'totalOutstandingSet':{'shopMoney':{'amount':'201950.00','currencyCode':'CLP'}},
                    'lineItems':{'pageInfo':{'hasNextPage':False},'nodes':[{'title':'212 Sexy Carolina Herrera','variantTitle':'100 ml','quantity':1,'currentQuantity':1}]}}
        with a.db(True) as c:
            a.setval(c,'shopify_pending_orders',[]);a.setval(c,'shopify_pending_links',{})
        with self.http.session_transaction() as s:s['user']=1;s['csrf']='test'
    def sync(self,orders):
        page={'data':{'orders':{'nodes':orders,'pageInfo':{'hasNextPage':False}}}}
        with patch.object(a.shopify_auth,'access_token',return_value='fake'),patch.object(a,'httpjson',return_value=page):return a.sync_shop()
    def records(self):
        with a.db() as c:return a.settings(c)['shopify_pending_orders']
    def test_snapshot_products_and_contact_without_new_debt_or_payments(self):
        with a.db() as c:before={t:a.rows(c,'SELECT * FROM '+t) for t in ('clients','orders','payments','allocations','installments')}
        self.sync([self.order]);r=self.records()[0]
        self.assertEqual(r['client_id'],self.cid);self.assertEqual(r['items'],[{'title':'212 Sexy Carolina Herrera · 100 ml','quantity':1}])
        self.assertEqual(r['outstanding'],201950)
        with a.db() as c:
            for t in before:self.assertEqual(a.rows(c,'SELECT * FROM '+t),before[t])
    def test_excludes_invalid_cancelled_paid_and_refunds(self):
        invalid=[]
        for status,total,outstanding,cancelled in [('PAID','100','100',None),('PENDING','100','-1',None),('PENDING','100','100.5',None),('PENDING','100','101',None),('PENDING','100','0',None),('PENDING','100','100','2026-10-28')]:
            o=copy.deepcopy(self.order);o.update(displayFinancialStatus=status,cancelledAt=cancelled);o['currentTotalPriceSet']['shopMoney']['amount']=total;o['totalOutstandingSet']['shopMoney']['amount']=outstanding;invalid.append(o)
        with a.db() as c:
            for o in invalid:self.assertIsNone(pending_record(c,o,a.phone,a.now(),{}))
        partial=copy.deepcopy(self.order);partial['displayFinancialStatus']='PARTIALLY_PAID';partial['totalOutstandingSet']['shopMoney']['amount']='100'
        self.sync([partial]);self.assertEqual(self.records()[0]['outstanding'],100)
        with a.db() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM payments').fetchone()[0],0)
    def test_unique_full_name_fallback_and_shared_phone_conflicts(self):
        o=copy.deepcopy(self.order);o['customer'].pop('phone')
        with a.db() as c:
            r=pending_record(c,o,a.phone,a.now(),{})
            self.assertEqual(r['client_id'],self.cid);self.assertEqual(r['match'],'name')
        with a.db(True) as c:
            c.execute("INSERT INTO clients(name,phone) VALUES('Otra persona','56900000001')")
            self.assertIsNone(pending_record(c,self.order,a.phone,a.now(),{})['client_id'])
    def test_name_fallback_normalizes_accents_case_and_spacing_without_financial_changes(self):
        o=copy.deepcopy(self.order);o['customer']={'id':'gid/customer/new','displayName':'  JAVIERA   GONZALEZ  '}
        with a.db() as c:
            before={t:a.rows(c,'SELECT * FROM '+t) for t in ('clients','orders','payments')}
            r=pending_record(c,o,a.phone,a.now(),{})
            self.assertEqual(r['client_id'],self.cid);self.assertEqual(r['match'],'name')
            for t in before:self.assertEqual(a.rows(c,'SELECT * FROM '+t),before[t])
        self.sync([o]);self.assertEqual(self.records()[0]['client_id'],self.cid)
    def test_duplicate_partial_names_and_conflicting_shopify_ids_are_not_linked(self):
        o=copy.deepcopy(self.order);o['customer'].pop('phone')
        with a.db(True) as c:
            c.execute("INSERT INTO clients(name) VALUES('JAVIERA GONZALEZ')")
            self.assertIsNone(pending_record(c,o,a.phone,a.now(),{})['client_id'])
            c.execute("DELETE FROM clients WHERE id!=?",(self.cid,))
            o['customer']['displayName']='Javiera'
            self.assertIsNone(pending_record(c,o,a.phone,a.now(),{})['client_id'])
            o['customer']['displayName']='Javiera Gonzalez'
            c.execute("UPDATE clients SET shopify_id='gid/customer/different' WHERE id=?",(self.cid,))
            self.assertIsNone(pending_record(c,o,a.phone,a.now(),{})['client_id'])
    def test_explicit_link_requires_csrf_and_fresh_snapshot_and_survives_sync(self):
        self.order['customer'].pop('phone');self.sync([self.order]);r=self.records()[0]
        body={'shopify_id':r['shopify_id'],'fingerprint':r['fingerprint'],'client_id':self.cid}
        self.assertEqual(self.http.post('/api/shopify/pending/link',json=body).status_code,403)
        self.assertEqual(self.http.post('/api/shopify/pending/link',json={**body,'fingerprint':'old'},headers={'X-CSRF-Token':'test'}).status_code,400)
        self.assertEqual(self.http.post('/api/shopify/pending/link',json=body,headers={'X-CSRF-Token':'test'}).status_code,200)
        self.sync([self.order]);self.assertEqual(self.records()[0]['match'],'manual')
        self.assertEqual(self.records()[0]['client_id'],self.cid)
        changed=copy.deepcopy(self.order);changed['customer']['id']='gid://shopify/Customer/other';self.sync([changed])
        self.assertIsNone(self.records()[0]['client_id'])
    def test_complete_sync_removes_paid_orders_failed_sync_keeps_last_snapshot(self):
        self.sync([self.order]);before=self.records()
        with patch.object(a.shopify_auth,'access_token',return_value='fake'),patch.object(a,'httpjson',side_effect=ValueError('No connection')):
            with self.assertRaises(ValueError):a.sync_shop()
        self.assertEqual(self.records(),before)
        paid=copy.deepcopy(self.order);paid['displayFinancialStatus']='PAID';paid['totalOutstandingSet']['shopMoney']['amount']='0'
        self.sync([paid]);self.assertEqual(self.records(),[])



    def test_existing_order_number_links_despite_different_name(self):
        with a.db(True) as c:
            c.execute("UPDATE orders SET number='#6437' WHERE id=?",(self.oid,))
            remote=copy.deepcopy(self.order)
            remote['customer']={'displayName':'Otro nombre en Shopify'}
            result=pending_record(c,remote,a.phone,a.now(),{})
            self.assertEqual(result['client_id'],self.cid)
            self.assertEqual(result['match'],'order_number')

    def test_duplicate_order_number_across_clients_stays_unlinked(self):
        with a.db(True) as c:
            c.execute("UPDATE orders SET number='#6437' WHERE id=?",(self.oid,))
            cid=c.execute("INSERT INTO clients(name,phone,email) VALUES('Otra persona','','')").lastrowid
            c.execute("INSERT INTO orders(client_id,number,purchased,total,items,updated) VALUES(?,'#6437','2026-10-26',1,'[]',?)",(cid,a.now()))
            result=pending_record(c,self.order,a.phone,a.now(),{})
            self.assertIsNone(result['client_id'])

if __name__=='__main__':unittest.main()
