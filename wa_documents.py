"""Sube PDF a Meta como media privado; no publica enlaces al estado de cuenta."""
import json,os,secrets,urllib.request,urllib.error

def upload_pdf(data,filename):
    if os.getenv('CINDY_DEMO')=='1':raise ValueError('Los envíos reales están desactivados en demostración.')
    token=os.getenv('WA_ACCESS_TOKEN');number=os.getenv('WA_PHONE_NUMBER_ID')
    if not token or not number:raise ValueError('WhatsApp aún no está vinculado.')
    if not data.startswith(b'%PDF') or len(data)>8*1024*1024:raise ValueError('PDF no válido o mayor a 8 MB.')
    boundary='cindy-'+secrets.token_hex(24)
    payload=(f'--{boundary}\r\nContent-Disposition: form-data; name="messaging_product"\r\n\r\nwhatsapp\r\n'
             f'--{boundary}\r\nContent-Disposition: form-data; name="type"\r\n\r\napplication/pdf\r\n'
             f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\nContent-Type: application/pdf\r\n\r\n').encode()+data+f'\r\n--{boundary}--\r\n'.encode()
    req=urllib.request.Request('https://graph.facebook.com/'+os.getenv('WA_API_VERSION','v23.0')+'/'+number+'/media',data=payload,headers={'Authorization':'Bearer '+token,'Content-Type':'multipart/form-data; boundary='+boundary})
    try:
        with urllib.request.urlopen(req,timeout=25) as r:result=json.load(r)
    except urllib.error.HTTPError as e:raise ValueError('Meta rechazó la carga del PDF (HTTP '+str(e.code)+').') from None
    except (urllib.error.URLError,TimeoutError):raise ValueError('No se pudo cargar el PDF en WhatsApp.') from None
    if not result.get('id'):raise ValueError('Meta no confirmó la carga del PDF.')
    return str(result['id'])
