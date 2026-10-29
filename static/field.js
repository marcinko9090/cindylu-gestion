/* Field collection uses the existing per-purchase API; no automatic distribution. */
(function(){
 'use strict';
 const storageKey='cindyFieldPending';
 const initial=()=>({place:'',placeQuery:'',clientId:null,clientQuery:'',orderId:null,amount:'',date:'',method:'efectivo',notify:false,noticeTemplate:null,lastNotice:null,paymentId:null,pending:null,busy:false,notice:'',error:'',needsRefresh:false,restored:false});
 let state=initial();
 const key=value=>norm(value).replace(/\s+/g,' ').trim();
 function places(){
  const grouped=new Map();
  for(const client of S.clients){const label=clientWorkplace(client),k=key(label);if(!grouped.has(k))grouped.set(k,{key:k,label,count:0});grouped.get(k).count++;}
  return [...grouped.values()].sort((a,b)=>a.label.localeCompare(b.label,'es'));
 }
 function clients(){return S.clients.filter(c=>(!state.place||key(clientWorkplace(c))===state.place)&&(!key(state.clientQuery)||key(c.name+' '+c.phone).includes(key(state.clientQuery)))).sort((a,b)=>balance(b.id)-balance(a.id)||a.name.localeCompare(b.name,'es'));}
 function purchases(cid){return active(cid).slice().sort((a,b)=>String(b.purchased).localeCompare(String(a.purchased))||b.id-a.id);}
 const eligible=o=>o&&o.status==='active'&&!o.review&&o.balance>0;
 function persist(){try{if(state.pending)sessionStorage.setItem(storageKey,JSON.stringify(state.pending));else sessionStorage.removeItem(storageKey);}catch{}}
 function restore(){
  if(state.restored)return;state.restored=true;
  try{
   const p=JSON.parse(sessionStorage.getItem(storageKey)||'null');if(!p)return;
   const order=S.orders.find(o=>o.id===p.order_id),client=S.clients.find(c=>c.id===p.client_id);
   if((p.notify!==undefined&&typeof p.notify!=='boolean')||(p.notice_template!==undefined&&typeof p.notice_template!=='string')||!client||!order||order.client_id!==client.id||!Number.isSafeInteger(p.amount)||p.amount<=0||!/^\w{40}$/.test(p.operation)||!['efectivo','transferencia','otro'].includes(p.method)||!/^\d{4}-\d{2}-\d{2}$/.test(p.date)){sessionStorage.removeItem(storageKey);return;}
   Object.assign(state,{place:key(clientWorkplace(client)),placeQuery:clientWorkplace(client),clientId:client.id,clientQuery:client.name,orderId:order.id,amount:String(p.amount),date:p.date,method:p.method,notify:!!p.notify,noticeTemplate:p.notice_template||CindyNotices.template(S.settings),pending:p,error:'Hay un abono pendiente de confirmación. Reintenta el mismo abono para comprobarlo sin duplicarlo.'});
  }catch{}
 }
 function clearClient(){Object.assign(state,{clientId:null,clientQuery:'',orderId:null,amount:'',notify:false,noticeTemplate:null,lastNotice:null,paymentId:null,notice:'',error:''});}
 function selectedClient(){return S.clients.find(c=>c.id===state.clientId&&key(clientWorkplace(c))===state.place);}
 function selectedOrder(){return purchases(state.clientId).find(o=>o.id===state.orderId);}
 function preview(){if(state.pending)return 'Por confirmar';const o=selectedOrder(),a=Number(state.amount);return eligible(o)&&state.amount!==''&&Number.isSafeInteger(a)&&a>0&&a<=o.balance?money(o.balance-a):'—';}
 function noticeValues(){return CindyNotices.values(selectedClient(),selectedOrder(),state.amount,state.date,balance(state.clientId));}
 function renderView(){
  restore();if(!state.date)state.date=S.today;if(state.noticeTemplate===null)state.noticeTemplate=CindyNotices.template(S.settings);
  const locked=state.busy||!!state.pending||state.needsRefresh,disabled=locked?'disabled':'',cl=selectedClient(),os=cl?purchases(cl.id):[],order=cl?selectedOrder():null;
  const ps=places().filter(p=>!key(state.placeQuery)||key(p.label).includes(key(state.placeQuery))),cs=!cl&&(state.place||key(state.clientQuery))?clients():[];
  return `<section class="card field-collection"><div class="card-head"><div><h2>Cobro en terreno</h2><p>Busca una clienta por nombre o filtra primero por lugar de cobro.</p></div></div>
   <fieldset id="field-flow" class="field-flow" ${state.busy?'disabled':''}>
     <label for="field-client">Buscar clienta</label><input id="field-client" type="search" autocomplete="off" placeholder="Nombre o teléfono de la clienta…" value="${esc(state.clientQuery)}" role="combobox" aria-expanded="${!cl}" aria-controls="field-client-results" ${disabled}>
     <div id="field-client-results" class="field-results" role="listbox" aria-label="Resultados de clientas">${!cl?cs.slice(0,15).map(c=>`<button type="button" role="option" data-field-client="${c.id}" ${disabled}><span><strong>${esc(c.name)}</strong><small>${esc(clientWorkplace(c))} · ${c.phone?'+'+esc(c.phone):'Sin teléfono'}</small></span><b>${money(balance(c.id))}</b></button>`).join('')||(state.place||key(state.clientQuery)?'<p>No hay clientas que coincidan con la búsqueda.</p>':'<p>Escribe un nombre para buscar en todas las clientas.</p>'):''}${!cl&&cs.length>15?'<p>Escribe más del nombre para acotar los resultados.</p>':''}</div>
    <label for="field-place">Lugar de cobro</label><input id="field-place" type="search" autocomplete="off" placeholder="Busca el lugar de cobro…" value="${esc(state.placeQuery)}" role="combobox" aria-expanded="${!state.place}" aria-controls="field-place-results" ${disabled}>
    <div id="field-place-results" class="field-results" role="listbox" aria-label="Lugares de cobro">${!state.place?ps.slice(0,12).map(p=>`<button type="button" role="option" data-field-place="${esc(p.key)}" ${disabled}><strong>${esc(p.label)}</strong><small>${p.count} ${p.count===1?'clienta':'clientas'}</small></button>`).join('')||'<p>Sin lugares que coincidan.</p>':''}${!state.place&&ps.length>12?'<p>Escribe el lugar para acotar los resultados.</p>':''}</div>
    ${state.place?`<div class="field-selection"><span>Lugar activo: <strong>${esc(state.placeQuery)}</strong></span><button type="button" id="field-change-place" class="text-button" ${disabled}>Cambiar lugar</button></div>`:''}
    ${cl?`<div class="field-client-summary"><div><strong>${esc(cl.name)}</strong><small>Saldo total de la clienta</small></div><b>${money(balance(cl.id))}</b><button type="button" id="field-change-client" class="text-button" ${disabled}>Otra clienta</button></div>
     <form id="field-payment-form">
      <label for="field-order">Compra a la que se aplica el abono</label><select id="field-order" name="order_id" required ${disabled}><option value="">Selecciona una compra</option>${os.map(o=>`<option value="${o.id}" ${o.id===state.orderId?'selected':''} ${!eligible(o)?'disabled':''}>${esc(o.number)} · ${day(o.purchased)} · ${o.review?'Por revisar':o.balance>0?'Saldo '+money(o.balance):'Pagada'}</option>`).join('')}</select>
      ${order?`<div class="field-purchase"><strong>${esc(order.number)}</strong><p>${(order.items||[]).map(i=>esc(i.quantity+' × '+i.title)).join(' · ')||'Productos sin detalle'}</p><span>Total: ${money(order.total)} · Abonado: ${money(order.total-order.balance)} · Saldo: <b>${money(order.balance)}</b></span></div>`:''}
      ${!os.some(eligible)?'<p class="info-box">No hay compras disponibles para abonar. Las compras pagadas o pendientes de revisión no admiten abonos.</p>':''}
      <label for="field-amount">Ingresar abono (pesos chilenos)</label><input id="field-amount" name="amount" type="number" inputmode="numeric" min="1" step="1" ${order?'max="'+order.balance+'"':''} value="${esc(state.amount)}" placeholder="Ej. 20000" required ${locked||!eligible(order)?'disabled':''}>
      <div class="field-after"><span>Saldo de esta compra después del abono</span><strong id="field-after-balance">${preview()}</strong></div>
      <div class="field-payment-details"><label>Fecha del abono<input id="field-date" name="date" type="date" value="${esc(state.date)}" required ${disabled}></label><label>Medio de pago<select id="field-method" name="method" ${disabled}>${[['efectivo','Efectivo'],['transferencia','Transferencia'],['otro','Otro']].map(([v,l])=>`<option value="${v}" ${state.method===v?'selected':''}>${l}</option>`).join('')}</select></label></div>
      ${CindyNotices.editor('field',state.notify,state.noticeTemplate,state.pending?'El mensaje se confirmará junto con el abono; reintenta la confirmación pendiente.':CindyNotices.format(state.noticeTemplate,noticeValues()),locked,CindyNotices.hint(cl,S.settings,S.integrations,S.demo))}
      <p class="subtle field-help">Confirma solo un pago recibido. Se descontará únicamente de la compra seleccionada.</p>
      <button type="submit" id="field-confirm" class="primary field-confirm" ${state.busy||state.needsRefresh||(!state.pending&&!eligible(order))?'disabled':''}>${state.busy?'Guardando abono…':state.pending?'Reintentar el mismo abono':'✓ Confirmar abono'}</button>
     </form>`:''}
   </fieldset>
   <div class="field-feedback" role="status" aria-live="polite">${state.notice?`<p class="field-success">${esc(state.notice)}</p>`:''}${state.error?`<p class="danger">${esc(state.error)}</p>`:''}${CindyNotices.status((S.payment_notices||[]).find(n=>n.payment_id===state.paymentId)||state.lastNotice)}${state.needsRefresh?'<button type="button" id="field-refresh" class="outline">Actualizar saldos</button>':''}</div>
  </section>`;
 }
 function redraw(id){const old=id?$('#'+id):null,pos=old?.selectionStart;render();const next=id?$('#'+id):null;if(next){next.focus();if(pos!=null&&next.setSelectionRange&&next.type!=='number')next.setSelectionRange(pos,pos);}}
 function bind(){
  const place=$('#field-place');if(!place)return;
  place.oninput=()=>{state.place='';state.placeQuery=place.value;clearClient();redraw('field-place');};
  $$('#field-place-results [data-field-place]').forEach(b=>b.onclick=()=>{if(state.pending||state.busy)return;const p=places().find(p=>p.key===b.dataset.fieldPlace);if(!p)return;state.place=p.key;state.placeQuery=p.label;clearClient();redraw('field-client');});
  const changePlace=$('#field-change-place');if(changePlace)changePlace.onclick=()=>{state.place='';state.placeQuery='';clearClient();redraw('field-place');};
  const input=$('#field-client');if(input)input.oninput=()=>{clearClient();state.clientQuery=input.value;redraw('field-client');};
  $$('#field-client-results [data-field-client]').forEach(b=>b.onclick=()=>{if(state.pending||state.busy)return;const cl=clients().find(c=>c.id===Number(b.dataset.fieldClient));if(!cl)return;clearClient();state.place=key(clientWorkplace(cl));state.placeQuery=clientWorkplace(cl);state.clientId=cl.id;state.clientQuery=cl.name;redraw('field-order');});
  const changeClient=$('#field-change-client');if(changeClient)changeClient.onclick=()=>{clearClient();redraw('field-client');};
  const order=$('#field-order');if(order)order.onchange=()=>{state.orderId=Number(order.value)||null;state.amount='';state.notice='';state.error='';state.lastNotice=null;state.paymentId=null;redraw('field-amount');};
  const updateNotice=CindyNotices.bind('field',()=>state,draft=>Object.assign(state,draft),noticeValues);
  const amount=$('#field-amount');if(amount)amount.oninput=()=>{state.amount=amount.value;$('#field-after-balance').textContent=preview();if(!state.pending)updateNotice();};
  const date=$('#field-date');if(date)date.onchange=()=>{state.date=date.value;if(!state.pending)updateNotice();};
  const method=$('#field-method');if(method)method.onchange=()=>state.method=method.value;
  const form=$('#field-payment-form');if(form)form.onsubmit=submit;
  const retry=$('#field-refresh');if(retry)retry.onclick=async()=>{retry.disabled=true;try{await refresh(false);state.needsRefresh=false;state.error='';render();}catch{state.error='No se pudo actualizar. El abono ya está registrado; vuelve a intentar actualizar los saldos.';render();}};
 }
 async function submit(event){
  event.preventDefault();if(state.busy||state.needsRefresh)return;
  const cl=selectedClient(),order=selectedOrder(),a=Number(state.amount);
  if(!state.pending){
   if(!cl||!eligible(order)||!Number.isSafeInteger(a)||a<=0||a>order.balance){state.error='Selecciona una compra e ingresa un abono mayor a cero que no supere su saldo.';render();return;}
   if(!/^\d{4}-\d{2}-\d{2}$/.test(state.date)){state.error='Indica la fecha del abono.';render();return;}
   if(state.notify&&(!state.noticeTemplate.trim()||state.noticeTemplate.length>1000)){state.error='Escribe el mensaje o desmarca el envío por WhatsApp.';render();return;}
   state.pending={client_id:cl.id,order_id:order.id,amount:a,date:state.date,method:state.method,operation:op(),notify:state.notify,notice_template:state.noticeTemplate,note:'Cobro en terreno · '+state.placeQuery};persist();
  }
  const pending={...state.pending};state.busy=true;state.error='';render();
  try{
   const result=await api('payments',pending);
   state.paymentId=result.id;state.lastNotice=result.notice||result.share||null;state.notify=false;state.noticeTemplate=CindyNotices.template(S.settings);
   state.pending=null;persist();state.amount='';state.notice='Abono de '+money(pending.amount)+' registrado en '+(order?.number||'la compra seleccionada')+'.';
   // A successful write remains successful even if the follow-up refresh loses connection.
   try{await refresh(false);state.notice+=' Saldo de la compra: '+money(S.orders.find(o=>o.id===pending.order_id)?.balance||0)+'. Saldo total de la clienta: '+money(balance(pending.client_id))+'.';}
   catch{state.needsRefresh=true;state.error='El abono ya fue registrado. Actualiza los saldos antes de ingresar otro.';}
  }catch(error){
   if(error.status&&error.status<500){state.pending=null;persist();state.error=error.message;}
   else{state.error='No se pudo confirmar la respuesta. Reintenta el mismo abono; no se descontará dos veces.';}
  }finally{state.busy=false;render();}
 }
 function reset(){state=initial();try{sessionStorage.removeItem(storageKey);}catch{}}
 window.CindyField={view:renderView,bind,reset,hasDraft:()=>!!(state.busy||state.pending||state.amount||state.needsRefresh)};
})();
