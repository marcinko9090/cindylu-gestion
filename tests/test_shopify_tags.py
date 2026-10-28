import unittest
from unittest.mock import patch
import test_app as base
import app as a
import shopify_tags as tags

class CustomerTagsTests(unittest.TestCase):
    def setUp(self):
        base.FinanceTests.setUp(self)
        self.customer={'id':'gid://shopify/Customer/50','displayName':'Javiera González','phone':'+56 9 0000 0001','email':None,'tags':['HCUCH','Turno día']}
    def classify(self,customers,pending=()):
        with a.db() as c:return tags.classify(c,customers,a.phone,pending)
    def test_tags_are_separate_from_excel_workplace_and_finances(self):
        with a.db(True) as c:c.execute("UPDATE clients SET notes='COD 19 · Hospital del Excel' WHERE id=?",(self.cid,))
        result=self.classify([self.customer]);self.assertEqual(result[str(self.cid)]['tags'],['HCUCH','Turno día'])
        with a.db() as c:
            self.assertEqual(c.execute('SELECT notes FROM clients WHERE id=?',(self.cid,)).fetchone()[0],'COD 19 · Hospital del Excel')
            self.assertEqual(a.balance(c,self.oid),100001)
    def test_no_match_on_name_and_no_arbitrary_shared_phone_or_customer(self):
        self.assertEqual(self.classify([{**self.customer,'phone':None}]),{})
        self.assertEqual(self.classify([self.customer,{**self.customer,'id':'other-customer'}]),{})
        with a.db(True) as c:c.execute("INSERT INTO clients(name,phone) VALUES('Otra clienta','56900000001')")
        self.assertEqual(self.classify([self.customer]),{})
    def test_id_match_and_explicit_link_and_empty_tags(self):
        with a.db(True) as c:c.execute('UPDATE clients SET shopify_id=? WHERE id=?',(self.customer['id'],self.cid))
        empty={**self.customer,'phone':None,'tags':[]}
        self.assertEqual(self.classify([empty])[str(self.cid)]['tags'],[])
        with a.db(True) as c:c.execute('UPDATE clients SET shopify_id=NULL,phone=? WHERE id=?',('',self.cid))
        manual=[{'customer_id':self.customer['id'],'client_id':self.cid,'match':'manual'}]
        self.assertEqual(self.classify([self.customer],manual)[str(self.cid)]['tags'],self.customer['tags'])
    def test_all_pages_and_throttling(self):
        def page(nodes,next_cursor=None):return {'data':{'customers':{'nodes':nodes,'pageInfo':{'hasNextPage':bool(next_cursor),'endCursor':next_cursor}}}}
        with patch.object(tags.time,'sleep'):
            responses=[{'errors':[{'extensions':{'code':'THROTTLED'}}]},page([self.customer],'page-2'),page([{**self.customer,'id':'2'}])]
            calls=[]
            def request(query,variables):calls.append(variables['cursor']);return responses.pop(0)
            self.assertEqual(len(tags.fetch_customers(request)),2);self.assertEqual(calls,[None,None,'page-2'])
        with self.assertRaises(ValueError):tags.fetch_customers(lambda *_:{'errors':[{'message':'No scope'}]})
    def test_sync_replaces_complete_tags_only_and_preserves_on_failure(self):
        with a.db(True) as c:a.setval(c,'shopify_client_tags',{'old':{'tags':['Old']}})
        def response(_url,data,_headers):
            if 'CustomerTags' in data['query']:return {'data':{'customers':{'nodes':[self.customer],'pageInfo':{'hasNextPage':False}}}}
            return {'data':{'orders':{'nodes':[],'pageInfo':{'hasNextPage':False}}}}
        with patch.object(a.shopify_auth,'access_token',return_value='fake'),patch.object(a,'httpjson',side_effect=response):a.sync_shop()
        with a.db() as c:snapshot=a.settings(c)['shopify_client_tags'];self.assertEqual(snapshot[str(self.cid)]['tags'],['HCUCH','Turno día'])
        with patch.object(a.shopify_auth,'access_token',return_value='fake'),patch.object(a,'httpjson',return_value={'data':{'orders':{'nodes':[],'pageInfo':{'hasNextPage':False}}}}):a.sync_shop()
        with a.db() as c:
            self.assertEqual(a.settings(c)['shopify_client_tags'],snapshot);self.assertTrue(a.settings(c)['shopify_tags_error'])

if __name__=='__main__':unittest.main()
