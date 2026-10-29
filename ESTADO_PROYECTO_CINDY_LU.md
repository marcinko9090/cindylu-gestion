# ESTADO MAESTRO DEL PROYECTO — TIENDA CINDY LÚ

**Versión de esta ficha:** 2026-10-29 (punto de partida para nuevos chats de Work)  
**Objetivo:** Reanudar el desarrollo sin depender del historial de conversaciones extensas.  
**ADVERTENCIA:** Este documento recopila acuerdos y datos comunicados en conversaciones. **No sustituye una inspección del código, una prueba de la base de datos ni una revisión del despliegue.** Las tareas solicitadas no se consideran implementadas hasta verificarlas.

## 1. Identidad del proyecto y entorno

- Proyecto: plataforma privada de gestión y cobranza de clientas, deudas, compras, abonos, estados de cuenta, Shopify y WhatsApp para Tienda Cindy Lú.
- Tienda pública: `https://cindylu.cl/`; Shopify: `cindylu.myshopify.com`.
- Sitio de gestión comunicado como desplegado en Render: `https://cindylu-gestion.onrender.com` (disponibilidad actual no comprobada en esta ficha).
- Base de datos: SQLite; entorno Render con disco persistente informado en `/var/data` (capacidad indicada de 1 GB). Evitar sustituir la base de producción con archivos vacíos o datos históricos por error.
- Uso previsto en navegador desde Mac, iPad y otros dispositivos. Prototipos locales previos para Windows/Mac; no asumir que los ZIP antiguos son el código de producción vigente.
- Diseño general: beige y dorado, minimalista, con detalles de brillo y animaciones discretas.
- **No guardar contraseñas, tokens de Shopify, credenciales Meta, datos bancarios ni teléfonos completos de clientas en esta ficha.**

## 2. Fuente de verdad: datos y contabilidad

### 2.1 Excel maestro del Club Cindy Lú
- Es la nómina histórica de clientas: nombre, teléfono, código, etiquetas/lugar de trabajo y volumen de compras por mes/año.
- Las compras y saldos históricos ya pagados **NO deben reabrirse como deuda actual**.
- Conservar métricas históricas: comprado por año y acumulado, separadas de la cobranza vigente.
- Crear clientas sin deuda para las personas que no figuren en CXC, evitando duplicados.

### 2.2 Excel `CXC 2026`
- Es la fuente de la deuda vigente y de los abonos detallados con su fecha, código de compra, productos/descripción y saldo.
- El objetivo principal es **saldo pendiente único por clienta**, sin planes de cuotas fijas. Los abonos son libres, fechados, y disminuyen el saldo **una sola vez**.
- Mostrar cada compra con fecha, código, productos y su valor cuando la fuente los contenga; mostrar abonos con fecha.
- Normalizar teléfonos con cautela; vincular registros sólo con coincidencias verificadas, nunca fusionar clientas automáticamente sólo por nombres parecidos.
- Aplicar importaciones en modo previsualización/validación, con respaldo SQLite antes de cambios masivos; preservar auditoría de cada operación.

### 2.3 Cifras históricas reportadas (requieren comprobar alcance en producción)
- Importación confirmada en Render el **27-10-2026**: 203 clientas, 283 compras y 274 abonos. Se informó respaldo: `/var/data/antes-importacion-20261027T145246-2fe90a81.sqlite3`.
- Revisión de planillas del **28-10-2026**: 2.545 clientas, 4.851 compras históricas, 3.443 resúmenes mensuales; 1.799 abonos conservados.
- Corte octubre 2026 calculado sobre los datos revisados: deuda por cobrar **$26.398.082 CLP**, saldo a favor **$40**, saldo neto **$26.398.042**. Los abonos del corte de **$1.301.836** ya estaban descontados del saldo; **no descontarlos de nuevo**.
- Pendientes de depuración señalados: 10 filas históricas ambiguas con código `A`/`PEDIDO`, 620 teléfonos originales para revisar y 1 registro sin clienta asociado a **$12.990**.
- **Estado de importación total al servidor:** sin validación concluyente en este documento. No declarar que las 2.545 clientas están cargadas en producción por el solo hecho de que fueron analizadas en Excel.

## 3. Shopify: reglas funcionales acordadas

1. Mostrar pedidos Shopify **«Pago pendiente»** con fecha, número de pedido, importe y detalle real de productos cuando estén disponibles.
2. En **Revisión de compras Shopify**, incluir la acción **«Agregar esta compra a la deuda»**.
3. Al activar esa acción: asociar o crear clienta correctamente; sumar el importe **una sola vez**; generar registro trazable; retirar el pedido de «pendientes por revisar» y mostrarlo en la ficha normal de la clienta.
4. La importación de clientas nuevas desde Shopify **no puede impedir ingresar abonos**. Comprobar cliente sin deuda previa y creación de primera compra.
5. Revisar retroactivamente los pedidos ya marcados «agregar a la deuda»: deben figurar en clientas normales, no seguir en revisión como pendientes. Sin duplicar saldos ante reintentos/sincronizaciones.
6. Shopify sirve para enriquecer con productos y fechas; no duplicar la deuda ya reconocida desde CXC. La equivalencia entre pedidos históricos y nuevos debe verificarse.
7. Revisar pedidos con montos negativos en sección separada; no sumar importes anómalos sin revisión.

**Estado de realización:** estas son funcionalidades solicitadas, varias reiteradas el 29-10-2026; **no se ha verificado su funcionamiento en el código más reciente ni en producción**.

## 4. Estados de cuenta, PDF y WhatsApp

- En la ficha: datos de clienta, lista de compras con fecha/código/productos/total/estado, abonos con fechas y saldo real.
- PDF legible con identidad visual de tienda que incluya **detalle de artículos** donde esos datos existan, fechas, compras, abonos y saldo.
- La edición de un mensaje de WhatsApp debe aplicarse como **plantilla global a todas las clientas**; el nombre, teléfono y saldos siguen siendo personalizados.
- Objetivo de interfaz: **una sola opción** desde la clienta que facilite enviar mensaje y PDF al WhatsApp correcto, sin pasos redundantes.
- **Límite técnico a comprobar:** abrir un enlace `wa.me` con texto prellenado **no adjunta un PDF automáticamente**. Para envío verdaderamente automático de texto+PDF al número correcto puede requerirse WhatsApp Business Platform/Cloud API o un flujo compatible con dispositivo/permisos; no prometerlo como completo con un enlace simple. Dar alternativa segura y clara si Meta no está conectada.
- La conexión automatizada a WhatsApp Business **no estaba operativa/validada** según conversaciones recientes.
- Validar siempre el número de destino en formato internacional antes de abrir WhatsApp.

## 5. Navegación, clientas, estética

- Buscador flexible por nombre y filtros por **etiquetas** (lugares de trabajo). Crear etiquetas faltantes de forma controlada; ejemplo: `CLC = Clínica Las Condes`.
- Vistas **«Clientas con deuda»** y **«Clientas sin deuda»**, con lista vertical; ordenar por deuda de mayor a menor cuando corresponda.
- Ingreso de abonos directo desde ficha o cobro en terreno, registrando fecha y sin obligar cuotas fijas. Opción de compartir confirmación por WhatsApp.
- Comparativo histórico por año: total comprado, total abonado, saldo si corresponde, sin confundir histórico pagado con deuda CXC.
- Etiquetas y textos: título **«Total comprado por año · TIENDA CINDY LÚ»**; quitar menciones técnicas a `CXC` en botones o mensajes visibles donde no aporten valor.
- Portada/video de introducción y logo; sesión recordada con bienvenida breve, estética beige/dorado; festividades (Halloween, Navidad, Día de la Madre, cumpleaños 8 de febrero), activadas 10 días antes; frases breves en bienvenida y tras actividad prolongada, con efectos fluidos.
- Priorizar exactitud contable y experiencia estable frente a efectos decorativos.

## 6. Lista priorizada de trabajo para el PRÓXIMO Work

### P0 — Integridad de datos y sincronización
- [ ] Identificar el **repositorio, ZIP o archivos exactos que corresponden al despliegue actual**. No editar copias obsoletas por error.
- [ ] Verificar con respaldo la base de producción, migraciones y última importación real; preservar datos existentes.
- [ ] Validar que las clientas nuevas de Shopify permitan **registrar abonos**.
- [ ] Verificar que «Agregar esta compra a la deuda» sea idempotente (no doble suma), retire los pedidos del área de pendientes y cree/actualice correctamente la ficha de clienta.
- [ ] Auditar pedidos ya marcados con esa acción y corregir los que permanezcan incorrectamente en revisión.
- [ ] Verificar consistencia entre CXC, abonos y saldos; no recobrar compras históricas pagadas.

### P1 — Estado de cuenta y comunicaciones
- [ ] Corregir fichas/PDF donde no aparecen productos cuando sí existen en Shopify o en CXC.
- [ ] Implementar y probar edición única de plantilla de mensaje para todas las clientas.
- [ ] Revisar el flujo de un solo botón de WhatsApp + mensaje + PDF, documentar claramente límite técnico y habilitar solución realmente compatible.

### P2 — Gestión y experiencia
- [ ] Completar «Clientas sin deuda», filtros por etiquetas, normalización `CLC` y orden de deuda.
- [ ] Revisar montos Shopify negativos y registros ambiguos sin modificar automáticamente el saldo.
- [ ] Pulir textos, presentación y efectos sin afectar rendimiento.

### Pruebas mínimas obligatorias
1. Clienta histórica sin CXC → perfil sin deuda, con compras históricas informativas.
2. Clienta CXC con abonos → saldo correcto, sin doble descuento.
3. Shopify nuevo → agregar compra → queda en clientas → acepta abono → saldo cambia.
4. Sincronización repetida de Shopify → no duplica compra, deuda ni abono.
5. Pedido ya marcado «Agregar esta compra a la deuda» → no sigue en pendientes.
6. PDF de clienta con productos → muestra detalle; si fuente no tiene productos, explicitar falta de datos sin inventarlos.
7. WhatsApp → verificar número, plantilla personalizada y tratamiento real del PDF.
8. Base de datos/servicio se reinician → datos y abonos persisten.

## 7. Protocolo para retomar en otro chat de Work

1. Abrir **conversación nueva** de Work para reducir contexto acumulado. No intentar borrar mensajes individuales de una sesión larga.
2. Adjuntar o abrir este archivo y el código/ZIP de la **última versión real** (o indicar el repositorio adecuado). Cuando haya acceso a la misma carpeta de proyecto, leer este documento primero.
3. Leer la última petición del usuario y **comprobar el código antes de modificarlo**. Distinguir «solicitado», «implementado» y «probado en producción».
4. Crear copia de seguridad antes de operaciones de datos. Nunca sobrescribir `/var/data` ni usar los Excel históricos como nueva deuda.
5. Al terminar, **actualizar esta ficha**: fecha, versión/commit/ZIP, cambios efectivamente realizados, pruebas, despliegue confirmado o pendiente y siguiente prioridad. Guardar la nueva versión también en Biblioteca/Proyecto para el siguiente Work.
6. Sólo archivar o eliminar los chats antiguos **después** de asegurar documentos, respaldos y código. Archivar no reduce el historial que arrastra una conversación abierta; para eso se usa una conversación nueva.

## 8. Registro de entregas (rellenar por cada Work)

| Fecha | Versión/archivo/commit | Cambio comprobado | Prueba realizada | Desplegado | Pendiente |
|---|---|---|---|---|---|
| 2026-10-29 | Estado de continuidad inicial | Recopilación de requisitos y antecedentes; no cambia el producto | No se ejecutaron pruebas sobre producción | No | Validar código vivo y resolver P0 |

## 9. Criterios para no perder trabajo

- Conservar **código fuente vigente + versión/commit**, **respaldo de base de datos**, **este registro de continuidad**, **credenciales sólo en lugar seguro** (no en el resumen).
- En cada entrega, informar qué archivo fue cambiado y proporcionar un artefacto verificable (ZIP, diff, commit u otra evidencia).
- Una petición del usuario y una respuesta de la IA **no prueban** que una función haya quedado implementada en la versión en ejecución.

## Sesión 29-10-2026 · navegación y resolución de revisiones

- Código base verificado: repositorio marcinko9090/cindylu-gestion, rama main, commit 225bde19b6c3433faa990fac42a1231a9b7ddfda.
- Logo superior izquierdo: vuelve a Clientas con deuda, sin ficha seleccionada, filtros reiniciados y página al comienzo.
- Ventana de revisión: dos decisiones, Al contado y Agregar al saldo. Se elimina la observación obligatoria.
- Al contado conserva la compra local y sus abonos en historial, retirando la compra de la deuda activa; no genera pagos ficticios.
- Agregar al saldo incorpora el pendiente válido en CLP una vez, conserva productos y fechas y permite abonos. Bloquea montos negativos, vínculo ausente, historial duplicado y discrepancias de una compra existente.
- Decisiones persistentes y auditadas: reintentos no duplican; sincronización no reincorpora decisiones resueltas. Cambiar una decisión ya confirmada requiere revisión de la ficha.
- Archivos: app.py, static/app.js, templates/index.html, tests/test_review_decisions.py y esta ficha.
- Validación local: 122 pruebas Python satisfactorias; pruebas Node de resumen anual satisfactorias; sintaxis de static/app.js comprobada.
- No se accedió ni modificó la base de producción. Las pruebas usan una base temporal; no se generó respaldo de producción.
- Despliegue en Render: pendiente de comprobar. No afirmar que el cambio está visible hasta verificar la publicación.
- Otras tareas P0/P1 de esta ficha siguen pendientes de validación independiente.


## Sesión 29-10-2026 · error al abrir revisión

- La captura del usuario mostró `remoteMoney is not defined`. La función estaba limitada al listado y no disponible para el modal.
- Corregido en static/app.js compartiendo el formateador; commit 8ad9baed6513f3ca274970ce44c97e8576285d5e.
- Prueba de regresión tests/test_review_modal.cjs: apertura, monto CLP y envío de ambas decisiones con fingerprint; commit f2fe084370e2f4f876892c41ebb4d3d4481fcf54.
- Validación: 122 pruebas Python, pruebas Node de resumen anual, prueba de modal y sintaxis JavaScript satisfactorias.
- Sin cambios ni acceso a base de producción; no se requirió respaldo de datos. Publicación efectiva en Render pendiente de verificar.


## Sesión 29-10-2026 · mensajes de calma y esfuerzo

- Intervalo cambiado a cinco minutos de actividad visible; se conservan exclusión de inactividad, ventanas abiertas, pantalla de acceso y cierre de sesión.
- 868 mensajes completos distintos, con índice persistente local en el navegador. No se reinicia al agotar el catálogo: se dejan de mostrar antes que repetir. Borrar datos del navegador o cambiar dispositivo reinicia ese historial; no hay sincronización entre dispositivos.
- Cinco segundos de lectura y dos de vuelo ascendente con doce brillos dorados que acompañan la salida. Movimiento reducido elimina el vuelo y partículas. No modifica PDFs, mensajes a clientas ni datos contables.
- Pruebas: 122 Python, resumen anual Node, sintaxis JS y tests de calma (intervalo, exclusiones, persistencia y catálogo completo sin repeticiones) satisfactorios.
- Vista visual automatizada no disponible: falta ejecutable Chromium en el entorno. Despliegue Render y apariencia en dispositivo real pendientes de comprobar.


## Sesión 29-10-2026 · confirmación de abono con enlace de tienda

- Plantilla predeterminada adaptada a la captura: monto, saldo total en negrita WhatsApp, agradecimiento, https://cindylu.cl/ y frase promocional hasta en 3 cuotas. No modifica reglas de abonos ni crea cuotas fijas. Migra únicamente plantillas predeterminadas antiguas; conserva personalizaciones.
- Tras confirmar un abono sin envío automático, ficha, cobro en terreno y modal ofrecen mensaje listo y enlace a WhatsApp con teléfono validado. No envía mensajes ni afirma entrega. Avisos ya encolados conservan su estado sin botón manual duplicado.
- Nueva tabla payment_shares conserva texto y teléfono de la confirmación para reintentos estables. Creación aditiva al iniciar; no se accedió a datos de producción.
- Pruebas: 123 Python satisfactorias; Node de abonos inline, terreno, resumen anual y nuevo test_payment_share.cjs satisfactorios; sintaxis JS comprobada. El test nuevo comprueba valores, vínculo, teléfono, ausencia de envío automático y estabilidad ante otro abono y reintento.
- Publicación en Render y apariencia en dispositivos pendientes de comprobar; la vista previa/logo de la tienda la decide WhatsApp.
