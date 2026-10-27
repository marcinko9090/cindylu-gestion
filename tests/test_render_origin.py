import os
import unittest
from unittest.mock import patch
from test_app import a

class RenderOriginTests(unittest.TestCase):
    def setUp(self):
        p = patch.dict(os.environ, {'RENDER_EXTERNAL_URL': 'https://cindylu-gestion.onrender.com', 'CINDY_PUBLIC_URL': ''})
        p.start(); self.addCleanup(p.stop)
        a.failures.clear()
        self.http = a.app.test_client()
    def login(self, origin, host='internal.render:10000'):
        return self.http.post('/api/login', json={'email':'missing@example.invalid','password':'invalid'}, headers={'Origin':origin,'Host':host})
    def test_https_public_origin_behind_http_proxy(self):
        self.assertEqual(self.login('https://cindylu-gestion.onrender.com').status_code,401)
    def test_attacker_origin_and_matching_host(self):
        self.assertEqual(self.login('https://attacker.example','attacker.example').status_code,403)
    def test_http_suffix_null_rejected(self):
        for origin in ['http://cindylu-gestion.onrender.com','https://cindylu-gestion.onrender.com.attacker.example','null']:
            with self.subTest(origin=origin):self.assertEqual(self.login(origin).status_code,403)
    def test_custom_domain_override(self):
        with patch.dict(os.environ, {'CINDY_PUBLIC_URL':'https://gestion.example.com/'}):
            self.assertEqual(self.login('https://gestion.example.com').status_code,401)
            self.assertEqual(self.login('https://cindylu-gestion.onrender.com').status_code,403)
    def test_local_fallback(self):
        with patch.dict(os.environ, {'RENDER_EXTERNAL_URL':'','CINDY_PUBLIC_URL':''}):
            self.assertEqual(self.login('http://localhost:8765','localhost:8765').status_code,401)
            self.assertEqual(self.login('http://attacker.example','localhost:8765').status_code,403)
