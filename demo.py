"""Demostración aislada. Nunca se conecta a Shopify ni a Meta."""
import os,sys,datetime as dt,json
from pathlib import Path
os.environ['CINDY_DATA']=str(Path(__file__).resolve().parent/'demo-data')
os.environ['CINDY_DEMO']='1'
from app import app,db,make_plan,pay,now,init,DATA
from werkzeug.security import generate_password_hash

def seed():
    with db(True) as c:
        if c.execute('SELECT 1 FROM clients').fetchone():return
        c.execute('INSERT INTO users(email,password) VALUES(?,?)',('demo@cindylu.local',generate_password_hash('CindyLu-Demo-2026')))
        for name,p in [('Javiera González','56900000001'),('Jacqueline Soto','56900000002'),('María Pérez','56900000003'),('Javiera Morales','56900000004'),('Camila Rojas','56900000005')]:c.execute('INSERT INTO clients(name,phone,email,notes) VALUES(?,?,?,?)',(name,p,'','Ficha de demostración. Datos ficticios.'))
        day=dt.date.today();first=(day.replace(day=1)+dt.timedelta(days=32)).replace(day=5)
        for cid,num,total,base,items,count in [(1,'#1048',150000,30000,[{'title':'Perfume Rose · 100 ml','quantity':1},{'title':'Labial Velvet · Rosa nude','quantity':2}],3),(1,'#1092',48000,0,[{'title':'Set de cuidado facial','quantity':1}],2),(2,'#1086',90000,0,[{'title':'Paleta de sombras Nude','quantity':1}],3),(3,'#1072',80000,20000,[{'title':'Perfume de mujer','quantity':1}],2),(4,'#1095',60000,0,[{'title':'Crema hidratante','quantity':2}],3)]:
            oid=c.execute('INSERT INTO orders(client_id,number,purchased,total,base_paid,items,source,updated) VALUES(?,?,?,?,?,?,?,?)',(cid,num,(day-dt.timedelta(days=15)).isoformat(),total,base,json.dumps(items),'demo',now())).lastrowid
            make_plan(c,{'order_id':oid,'count':count,'first':first.isoformat(),'frequency':'monthly'})
        pay(c,{'order_id':1,'amount':40000,'date':day.isoformat(),'method':'transferencia','operation':'demo-payment-000001'})
        t=now()
        c.execute('INSERT INTO messages(client_id,direction,body,status,created) VALUES(?,?,?,?,?)',(1,'out','Hola, Javiera. Tu próxima cuota es de $40.000. Gracias por elegir Cindy Lú ✨','demo',t))
        c.execute('INSERT INTO messages(client_id,direction,body,status,created) VALUES(?,?,?,?,?)',(1,'in','Hola! Te envié un abono de $20.000. Adjunto el comprobante.','demo',t))
        # Neutral sample document, deliberately not a fabricated bank receipt.
        from shutil import copyfile
        copyfile(Path(__file__).parent/'static'/'demo-comprobante.png',DATA/'media'/'demo.png')
        rid=c.execute('INSERT INTO receipts(client_id,filename,mime,path,created) VALUES(?,?,?,?,?)',(1,'Ejemplo-comprobante.png','image/png','demo.png',t)).lastrowid
        c.execute('INSERT INTO messages(client_id,direction,body,receipt_id,status,created) VALUES(?,?,?,?,?,?)',(1,'in','Archivo de prueba · No es una transferencia real',rid,'demo',t))
seed()
if __name__=='__main__':
    import webbrowser,threading
    port=int(os.getenv('PORT','8766'))
    if '--no-browser' not in sys.argv:threading.Timer(1,lambda:webbrowser.open('http://localhost:'+str(port))).start()
    print('Demo: http://localhost:'+str(port)+' · demo@cindylu.local · CindyLu-Demo-2026',flush=True)
    from waitress import serve
    serve(app,host=os.getenv('CINDY_HOST','127.0.0.1'),port=port,threads=8)
