"""Importación inicial de la copia transferida, sin sustituir usuarios ni sesiones.
Solo admite la copia verificada de este despliegue y una base destino sin negocio.
No importa credenciales, ajustes de integraciones ni auditoría antigua.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import sqlite3

SOURCE_SHA256 = '49ea824d5699f9b79bf51011601af66c1900abb6d77cd8e92c838cdcf889f3dd'
TABLES = ('clients', 'orders', 'installments', 'receipts', 'payments',
          'allocations', 'messages', 'reminders', 'payment_notices', 'statement_sends')


def migrate(source, target):
    source, target = Path(source).resolve(), Path(target).resolve()
    if source == target or not source.is_file() or not target.is_file():
        raise ValueError('No se encontraron dos bases distintas. No se modificó nada.')
    if hashlib.sha256(source.read_bytes()).hexdigest() != SOURCE_SHA256:
        raise ValueError('La copia no coincide con la verificada. No se modificó nada.')
    backup = target.with_name('antes-importacion-' + dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + os.urandom(4).hex() + '.sqlite3')
    c = sqlite3.connect(target.as_uri() + '?mode=rw', uri=True, timeout=30)
    try:
        c.execute('PRAGMA foreign_keys=ON')
        c.execute('ATTACH DATABASE ? AS origen', (source.as_uri() + '?mode=ro',))
        for schema in ('main', 'origen'):
            if c.execute('PRAGMA ' + schema + '.quick_check').fetchone()[0] != 'ok':
                raise ValueError('Una base no pasó la comprobación de integridad.')
            if c.execute('PRAGMA ' + schema + '.foreign_key_check').fetchone():
                raise ValueError('Una base contiene referencias inválidas.')
        counts = {t: c.execute('SELECT COUNT(*) FROM origen.' + t).fetchone()[0] for t in TABLES}
        if [counts[t] for t in ('clients', 'orders', 'payments')] != [203, 283, 274]:
            raise ValueError('Las cantidades de origen no son las verificadas.')
        if c.execute("SELECT COUNT(*) FROM origen.receipts WHERE COALESCE(path,'')!=''").fetchone()[0] or c.execute("SELECT COUNT(*) FROM origen.statement_sends WHERE COALESCE(path,'')!=''").fetchone()[0]:
            raise ValueError('Esta copia requiere transferir archivos adjuntos antes de importar.')
        for table in TABLES:
            cols = lambda schema: [tuple(r) for r in c.execute('PRAGMA ' + schema + '.table_info(' + table + ')')]
            if cols('main') != cols('origen'):
                raise ValueError('El esquema de ' + table + ' cambió; se requiere revisión.')
        with sqlite3.connect(backup) as b:
            c.backup(b)
        backup.chmod(0o600)
        c.execute('BEGIN IMMEDIATE')
        # El bloqueo se mantiene hasta COMMIT: lectores ven la versión anterior
        # y cualquier escritor debe esperar. Una segunda ejecución se rechaza.
        if any(c.execute('SELECT COUNT(*) FROM main.' + t).fetchone()[0] for t in TABLES):
            raise ValueError('El destino ya contiene registros: no se sobrescribe ni duplica nada.')
        users = c.execute('SELECT * FROM main.users ORDER BY id').fetchall()
        if not users:
            raise ValueError('Primero crea tu usuario administrador.')
        cfg = dict(c.execute('SELECT key,value FROM main.settings'))
        if cfg.get('shopify_token') and json.loads(cfg['shopify_token']):
            raise ValueError('Desconecta Shopify antes de realizar la carga inicial.')
        if os.getenv('SHOPIFY_ACCESS_TOKEN') or os.getenv('WA_ACCESS_TOKEN'):
            raise ValueError('Retira temporalmente las claves de integraciones antes de importar.')
        for t in TABLES:
            c.execute('INSERT INTO main.' + t + ' SELECT * FROM origen.' + t)
            if c.execute('SELECT COUNT(*) FROM main.' + t).fetchone()[0] != counts[t]:
                raise ValueError('Las cantidades importadas no coinciden.')
        # Conserva el historial pero cancela trabajos externos aún pendientes.
        for t in ('reminders', 'payment_notices', 'statement_sends'):
            c.execute("UPDATE main." + t + " SET status='cancelled' WHERE status IN ('pending','sending')")
        for key in ('sending', 'auto_reply', 'payment_notify'):
            c.execute('INSERT OR REPLACE INTO main.settings(key,value) VALUES(?,?)', (key, 'false'))
        if c.execute('PRAGMA main.foreign_key_check').fetchone():
            raise ValueError('La comprobación de referencias falló; se revierte la importación.')
        if c.execute('SELECT * FROM main.users ORDER BY id').fetchall() != users:
            raise ValueError('El acceso cambió; se revierte la importación.')
        c.execute('INSERT INTO main.audit(event,data,created) VALUES(?,?,?)',
                  ('initial_migration', json.dumps({'counts': counts, 'sha256': SOURCE_SHA256}), dt.datetime.now(dt.timezone.utc).isoformat()))
        c.commit()
        return counts, backup
    except BaseException:
        c.rollback()
        raise
    finally:
        c.close()


if __name__ == '__main__':
    p = argparse.ArgumentParser(description='Migrar copia verificada conservando el acceso actual')
    p.add_argument('--source', default='/var/data/importacion.sqlite3')
    p.add_argument('--target', default=str(Path(os.getenv('CINDY_DATA', '/var/data')) / 'cindy.sqlite3'))
    args = p.parse_args()
    try:
        counts, backup = migrate(args.source, args.target)
    except (ValueError, sqlite3.Error, OSError) as e:
        raise SystemExit('IMPORTACIÓN DETENIDA: ' + str(e))
    print('IMPORTACIÓN COMPLETADA: 203 clientas, 283 compras y 274 abonos.')
    print('Tu usuario y clave de sesión se conservaron. Envíos automáticos desactivados.')
    print('Respaldo previo:', backup)
    print('Actualiza la página y compara los saldos antes de registrar operaciones.')
