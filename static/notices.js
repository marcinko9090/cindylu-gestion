/* Payment confirmations are ordinary client messages, never seasonally decorated. */
(function(){
 'use strict';
 const fallback='Hola, {nombre}. Confirmamos tu abono de {monto} para la compra {compra}. Saldo de esta compra: {saldo_compra}. Tu saldo total pendiente es {saldo_total}. ¡Gracias por comprar en Cindy Lú!';
 function template(settings){return settings?.payment_text||fallback;}
 function format(text,values){return String(text).replace(/\{(nombre|monto|compra|saldo_compra|saldo_total|fecha)\}/g,(_,key)=>String(values[key]??'—'));}
 function values(client,order,amount,date,total){
  const valid=order&&Number.isSafeInteger(Number(amount))&&Number(amount)>0&&Number(amount)<=order.balance;
  return {nombre:client?.name||'—',compra:order?.number||'—',monto:valid?money(Number(amount)):'—',fecha:date||'—',saldo_compra:valid?money(order.balance-Number(amount)):'—',saldo_total:valid?money(total-Number(amount)):'—'};
 }
 function hint(client,settings,integrations,demo){
  if(demo)return 'Demostración: el aviso será simulado y no se enviará.';
  if(!client?.phone)return 'Esta clienta no tiene teléfono. Completa su ficha para poder enviar el aviso.';
  if(!client.consent)return 'Falta la autorización de la clienta para recibir mensajes por WhatsApp.';
  if(!integrations?.whatsapp||!settings?.sending)return 'Si WhatsApp no está conectado o los envíos están desactivados, el aviso quedará pendiente. El abono sí se registra.';
  return 'El aviso se envía después de registrar el abono. Fuera de una conversación reciente se necesita la plantilla de WhatsApp configurada.';
 }
 function editor(prefix,enabled,text,preview,disabled=false,help=''){
  return `<div class="payment-notice-editor"><label class="check-label"><input id="${prefix}-notify" name="notify" type="checkbox" ${enabled?'checked':''} ${disabled?'disabled':''}> Enviar confirmación por WhatsApp</label>
   <div id="${prefix}-notice-options" class="payment-notice-options ${enabled?'':'hidden'}"><p class="subtle">${esc(help)}</p><label for="${prefix}-notice-preview">Vista previa del mensaje</label><pre id="${prefix}-notice-preview" class="payment-notice-preview">${esc(preview)}</pre>
    <details><summary>Personalizar mensaje de este abono</summary><label for="${prefix}-notice-template">Texto personalizable<textarea id="${prefix}-notice-template" name="notice_template" rows="4" maxlength="1000" ${disabled?'disabled':''}>${esc(text)}</textarea></label><p class="chat-help">Puedes cambiar el texto. {nombre}, {monto}, {compra}, {saldo_compra}, {saldo_total} y {fecha} se completan al confirmar el pago. La plantilla habitual se cambia en Configuración.</p></details>
   </div></div>`;
 }
 function bind(prefix,getDraft,setDraft,getValues){
  const check=$('#'+prefix+'-notify'),input=$('#'+prefix+'-notice-template'),box=$('#'+prefix+'-notice-options');
  if(!check||!input)return ()=>{};
  const update=()=>{const draft=getDraft();const preview=$('#'+prefix+'-notice-preview');if(preview)preview.textContent=format(draft.noticeTemplate,getValues());};
  check.onchange=()=>{setDraft({notify:check.checked});box?.classList.toggle('hidden',!check.checked);update();};
  input.oninput=()=>{setDraft({noticeTemplate:input.value});update();};
  return update;
 }
 function status(notice){
  if(!notice)return '';
  const labels={pending:'Pendiente de envío',sending:'Enviando por WhatsApp',sent:'Enviado a WhatsApp',review:'Revisar envío',cancelled:'Aviso cancelado',demo:'Demostración · No enviado'};
  return `<section class="payment-notice-result"><strong>Confirmación por WhatsApp · ${esc(labels[notice.status]||notice.status)}</strong><pre class="payment-notice-preview">${esc(notice.body)}</pre>${notice.error?`<p class="danger">${esc(notice.error)}</p>`:''}</section>`;
 }
 window.CindyNotices={template,format,values,hint,editor,bind,status};
})();
