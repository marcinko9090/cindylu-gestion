import unittest
import test_app as base
import app as a

class StatementLinkTests(unittest.TestCase):
    def setUp(self):
        base.FinanceTests.setUp(self)
        with a.db(True) as c:c.execute('DELETE FROM statement_links')
    def test_private_creation_public_snapshot_and_expiry(self):
        route='/api/clients/'+str(self.cid)+'/statement-link'
        self.assertEqual(self.http.post(route,json={}).status_code,401)
        with self.http.session_transaction() as s:s['user']='test';s['csrf']='test-csrf'
        self.assertEqual(self.http.post(route,json={}).status_code,403)
        result=self.http.post(route,json={},headers={'X-CSRF-Token':'test-csrf'})
        self.assertEqual(result.status_code,200)
        path=result.json['path']
        public=a.app.test_client()
        response=public.get(path)
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.data.startswith(b'%PDF'))
        self.assertEqual(response.headers['Cache-Control'],'no-store')
        self.assertEqual(response.headers['Referrer-Policy'],'no-referrer')
        self.assertIn('noindex',response.headers['X-Robots-Tag'])
        original=response.data
        with a.db(True) as c:c.execute('UPDATE orders SET total=999 WHERE id=?',(self.oid,))
        self.assertEqual(public.get(path).data,original)
        self.assertEqual(public.get('/estado/'+'x'*43+'.pdf').status_code,404)
        self.assertEqual(public.get('/api/state').status_code,401)
        with a.db(True) as c:c.execute('UPDATE statement_links SET expires=0')
        self.assertEqual(public.get(path).status_code,404)
