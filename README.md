# Cindy Lú · plataforma privada

Python, Flask y SQLite. El código se publica en un repositorio privado; la base de datos y los comprobantes se guardan únicamente en un volumen del servidor.

## Railway

1. Conectar este repositorio desde New Project > Deploy from GitHub repo.
2. Mantener UNA instancia. Se incluye Dockerfile y railway.json.
3. Agregar un volumen persistente montado en `/data` ANTES de operar.
4. Configurar las siguientes variables en Railway:

| Variable | Valor |
| --- | --- |
| CINDY_DATA | /data |
| CINDY_HOST | 0.0.0.0 |
| PORT | 8765 |
| CINDY_HTTPS | 1 |
| CINDY_TRUST_PROXY | 1 |
| RAILWAY_RUN_UID | 0 |
| CINDY_DEMO | 0 |

RAILWAY_RUN_UID permite escribir en el volumen montado como root. La confianza en el proxy está prevista para el acceso HTTPS a través del proxy de Railway; no exponer directamente el puerto del contenedor por otras vías.

5. Crear el acceso desde una consola DENTRO del contenedor: `python administrar.py`. Elegir correo y contraseña privada de al menos 12 caracteres. Reiniciar el servicio después. `railway run` ejecuta localmente y NO sirve para administrar el volumen remoto; usar una sesión remota, por ejemplo `railway ssh` con el servicio seleccionado.
6. En Settings > Networking, generar el dominio HTTPS, puerto 8765.
7. Acceder y comprobar que se exige iniciar sesión. Todavía no operar con datos reales si la migración no está completada.
8. Activar los respaldos del volumen y conservar además copias fuera del proveedor usando Configuración > Descargar respaldo completo.
9. Activar Wait for CI para que las actualizaciones esperen las pruebas de GitHub Actions. No activar Serverless mientras se requieran recordatorios y sincronización en segundo plano.

## Migración de datos

La base real NO está en este repositorio ni en la imagen Docker. El paquete de entrega incluye un ZIP privado separado. No subirlo a GitHub ni descomprimirlo dentro del código.

Transferir la base y media al volumen `/data` con el servicio detenido, antes de empezar a usarlo. No sobrescribir una base mientras la aplicación está activa. Si ya se registraron operaciones nuevas, detenerse y conciliar las versiones; no reemplazarlas a ciegas. Mantener una copia intacta antes de migrar.

Crear o restablecer el acceso con administrar.py después de la migración. Se generará una nueva clave de sesión; no es necesario transportar la anterior.

## Actualizaciones

Crear una rama, hacer los cambios, ejecutar `python -m unittest discover -s tests -v` y revisar la diferencia. Para probar la interfaz, usar datos ficticios separados. Integrar a main después de revisar; Railway despliega esa rama si el autodespliegue está habilitado.

Antes de modificar el esquema o los cálculos, hacer un respaldo y preparar la migración correspondiente. Retroceder el código no revierte una migración de datos.

Shopify y WhatsApp requieren credenciales del servidor. No incluirlas en archivos del repositorio, capturas ni mensajes. Mantener envíos reales desactivados hasta validar la migración e integraciones.

Documentación oficial consultada:
- https://docs.railway.com/volumes
- https://docs.railway.com/deployments/github-autodeploys
- https://docs.railway.com/config-as-code/reference
