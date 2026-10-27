"""Crea/restablece el único acceso de administración desde el servidor."""
import getpass
from app import db,secret,audit
from werkzeug.security import generate_password_hash
import secrets
if __name__=='__main__':
    print('Administración local de Cindy Lú. No compartas la contraseña.')
    email=input('Correo del acceso: ').strip().lower()
    p=getpass.getpass('Contraseña (mínimo 12 caracteres): ')
    q=getpass.getpass('Repite la contraseña: ')
    if '@' not in email or len(p)<12 or p!=q:raise SystemExit('Correo o contraseña inválidos. No se cambió nada.')
    with db(True) as c:
        old=c.execute('SELECT id FROM users LIMIT 1').fetchone()
        if old:c.execute('UPDATE users SET email=?,password=? WHERE id=?',(email,generate_password_hash(p),old[0]))
        else:c.execute('INSERT INTO users(email,password) VALUES(?,?)',(email,generate_password_hash(p)))
        audit(c,'admin_password_reset',{})
    secret.write_text(secrets.token_hex(48));secret.chmod(0o600)
    print('Acceso guardado. Reinicia el servidor para invalidar las sesiones anteriores.')
