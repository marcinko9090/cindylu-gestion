"""Server-only Shopify client credentials, with an expiring in-memory cache."""
import hashlib
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

_lock = threading.Lock()
_cache = {}

def domain(cfg):
    value = (os.getenv('SHOPIFY_DOMAIN') or cfg.get('shopify_domain') or 'cindylu.myshopify.com').strip().lower()
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]*\.myshopify\.com', value):
        raise ValueError('Dominio Shopify inválido (usa tutienda.myshopify.com).')
    return value

def configured(cfg):
    return bool((os.getenv('SHOPIFY_CLIENT_ID') and os.getenv('SHOPIFY_CLIENT_SECRET'))
                or os.getenv('SHOPIFY_ACCESS_TOKEN') or cfg.get('shopify_token'))

def access_token(cfg):
    shop = domain(cfg)
    client_id = os.getenv('SHOPIFY_CLIENT_ID', '').strip()
    client_secret = os.getenv('SHOPIFY_CLIENT_SECRET', '').strip()
    if client_id or client_secret:
        if not client_id or not client_secret:
            raise ValueError('Completa SHOPIFY_CLIENT_ID y SHOPIFY_CLIENT_SECRET en Render > Environment.')
        key = hashlib.sha256((shop+'\0'+client_id+'\0'+client_secret).encode()).hexdigest()
        with _lock:
            cached = _cache.get(key)
            if cached and time.monotonic() < cached[1]:
                return cached[0]
            body = urllib.parse.urlencode({'grant_type':'client_credentials', 'client_id':client_id, 'client_secret':client_secret}).encode()
            req = urllib.request.Request('https://'+shop+'/admin/oauth/access_token', data=body,
                                         headers={'Content-Type':'application/x-www-form-urlencoded'})
            try:
                with urllib.request.urlopen(req, timeout=25) as response:
                    result = json.load(response)
            except urllib.error.HTTPError as error:
                raise ValueError('Shopify rechazó el acceso (HTTP '+str(error.code)+'). Verifica las credenciales, la instalación y que la app y la tienda pertenezcan a la misma organización.') from None
            except (urllib.error.URLError, TimeoutError):
                raise ValueError('No se pudo contactar a Shopify. Intenta nuevamente.') from None
            try:
                token = result['access_token']
                lifetime = int(result['expires_in'])
                if not isinstance(token, str) or not token or lifetime <= 0:
                    raise ValueError()
            except (KeyError, TypeError, ValueError):
                raise ValueError('Shopify no devolvió un acceso válido.') from None
            _cache.clear()
            _cache[key] = (token, time.monotonic()+max(0, lifetime-300))
            return token
    token = os.getenv('SHOPIFY_ACCESS_TOKEN') or cfg.get('shopify_token')
    if not token:
        raise ValueError('Agrega las credenciales de Shopify en Render > Environment.')
    return token
