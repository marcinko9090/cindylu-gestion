# Publicar Cindy Lú en Render

Esta es la configuración para Render. El README original describe Railway; para este proveedor seguir este documento.

1. Acceder a https://dashboard.render.com con GitHub.
2. Seleccionar New > Blueprint y autorizar solo el repositorio privado marcinko9090/cindylu-gestion.
3. Elegir main y render.yaml. Revisar el resumen de cobro antes de crear los recursos.
4. La configuración crea UNA instancia Python de 512 MB y un disco de 1 GB en /var/data. Referencia de precios consultada: US$7 + US$0,25 mensuales, antes de impuestos y consumos adicionales. No crea PostgreSQL.
5. Esperar que termine el despliegue. El servidor usa Waitress mediante python app.py --no-browser, conservando el planificador existente.
6. Desde la Shell REMOTA del servicio ejecutar python administrar.py para elegir correo y contraseña de al menos 12 caracteres. No compartir esas credenciales. Reiniciar el servicio después.
7. Verificar que el enlace HTTPS exige iniciar sesión y que no se puede acceder a los datos sin una sesión.
8. El primer despliegue tiene una base vacía. Los registros privados NO se incluyeron en GitHub. Completar una migración privada antes de operar.
9. Antes de migrar, conservar un respaldo actualizado de la aplicación local. La copia adjuntada anteriormente contiene 203 clientas, 283 compras y 274 abonos; si hubo cambios posteriores, usar una copia más reciente.
10. Transferir base y media a /var/data mediante un canal privado, con la aplicación detenida. No sobrescribir SQLite mientras el servidor está activo. Crear/restablecer el acceso después de migrar y comprobar cantidades y saldos.
11. Configuración > Descargar respaldo completo permite crear una copia consistente de SQLite con sus comprobantes. Guardar copias fuera de Render; los snapshots del disco no sustituyen estos respaldos.
12. Shopify y WhatsApp requieren autorización y secretos en Environment del servicio. Mantener envíos deshabilitados hasta validar cuentas e integración.

## Actualizaciones

El repositorio conserva el código; /var/data conserva los datos. El autodespliegue espera los checks de GitHub. Crear una rama para cada cambio, probarla y revisar antes de integrarla en main. Los cambios de esquema requieren respaldo y migración explícita.

No se ha contratado ni desplegado un servicio de Render mediante este archivo. El usuario debe conectar su propia cuenta y revisar la contratación.

Fuentes oficiales:
- https://render.com/docs/blueprint-spec
- https://render.com/docs/disks
- https://render.com/pricing

## Conectar Shopify desde Dev Dashboard

Instalar la app en la tienda real con read_orders y read_customers. En Render > servicio > Environment agregar SHOPIFY_DOMAIN (dominio exacto myshopify.com), SHOPIFY_CLIENT_ID y SHOPIFY_CLIENT_SECRET. No pegarlos en el chat, código, capturas ni repositorio. Guardar y volver a desplegar. El servidor solicita acceso mediante client_credentials y lo renueva antes de sus 24 horas de vigencia; el token solo queda en memoria.

En Configuración > Shopify pulsar Probar conexión. Esta prueba consulta la tienda y el acceso a pedidos sin importar datos. Después pulsar Actualizar productos de Shopify. La primera sincronización exitosa activa la consulta automática cada cinco minutos.

En esta etapa la sincronización NO incorpora ventas nuevas ni genera deuda. Vincula únicamente una compra Excel con número único, total y contacto coincidentes, y completa sus artículos; conserva importe, abonos, fechas locales, cuotas y asignaciones. Una coincidencia ambigua queda sin vincular y se cuenta para revisión. Los cambios de total o anulaciones de compras ya vinculadas requieren revisión. Consultar las cantidades en el resumen de Configuración. Las ventas nuevas permanecen en Shopify y deben incorporarse mediante un flujo posterior de revisión explícita. El permiso read_orders limita el acceso a los últimos 60 días; no prometer historial completo sin habilitar read_all_orders.

Documentación: https://shopify.dev/docs/apps/build/authentication-authorization/client-credentials-grant

