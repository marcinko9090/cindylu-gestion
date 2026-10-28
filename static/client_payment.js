/* Inline abonos use the same validated, idempotent payment endpoint as the modal. */
(function(){
 'use strict';
 const drafts=new Map(),storageKey='cindy-client-pending-v1';let current=null,restored=false;
 function save(){try{sessionStorage.setItem(storageKey,JSON.stringify([...drafts].filter(([,d])=>d.pending).map(([id,d])=>[id,d.pending])));}catch{}}
 function draft(cid){
  if(!drafts.has(cid))drafts.set(cid,{orderId:null,amount:'',date:S.today,method:'transferencia',note:'',verified:false,notify:!!S.settings.payment_notify,noticeTemplate:CindyNotices.template(S.settings),pending:null,busy:false,error:'',success:'',needsRefresh:false,notice:null});
  return drafts.get(cid);
 }
 function restore(){
  if(restored)return;restored=true;
  try{const saved=JSON.parse(sessionStorage.getItem(storageKey)||'[]');
   for(const [cid,p] of saved){
    const order=S.orders.find(o=>o.id===p.order_id&&o.client_id===cid);
    if(!order||!Number.isSafeInteger(p.amount)||p.amount<=0||!/^\w{40}$/.test(p.operation)||!/^\d{4}-\d{2}-\d{2}$/.test(p.date))continue;
    Object.assign(draft(cid),{pending:p,orderId:p.order_id,amount:String(p.amount),date:p.date,method:p.method,note:p.note||'',verified:true,notify:!!p.notify,noticeTemplate:p.notice_template||CindyNotices.template(S.settings),error:'Hay un abono pendiente de confirmación. Reintenta el mismo abono para comprobarlo sin duplicarlo.'});
   }
  }catch{}
 }
 function view(cid){
  restore();current=cid;const d=draft(cid),client=S.clients.find(c=>c.id===cid);
  const eligible=active(cid).filter(o=>o.balance>0&&!o.review);
  if(d.pending&&!eligible.some(o=>o.id===d.pending.order_id)){const old=S.orders.find(o=>o.id===d.pending.order_id);if(old)eligible.push(old);}
  if(!d.orderId&&eligible.length===1)d.orderId=eligible[0].id;
  const locked=!!(d.pending||d.busy||d.needsRefresh),disabled=locked?'disabled':'';
  const order=eligible.find(o=>o.id===d.orderId);
  return `<aside class="card client-payment-panel" id="client-payment-panel"><h3>Ingresar nuevo abono</h3><p class="subtle">Saldo vigente: <strong>${money(balance(cid))}</strong></p>${!eligible.length&&!d.pending?'<p class="subtle">Esta ficha no tiene un saldo confirmado disponible para registrar abonos.</p>':`<form id="client-payment-form"><label>Aplicar a<select name="order_id" id="client-payment-order" required ${disabled}><option value="">Selecciona una compra o cuenta</option>${eligible.map(o=>`<option value="${o.id}" ${o.id===d.orderId?'selected':''}>${esc(o.source==='cxc'?'Saldo de la cuenta':o.number)} · ${money(o.balance)}</option>`).join('')}</select></label><label>Monto del abono<input id="client-payment-amount" name="amount" type="number" min="1" step="1" value="${esc(d.amount)}" required ${disabled}></label><div class="client-payment-fields"><label>Fecha del abono<input id="client-payment-date" name="date" type="date" value="${esc(d.date)}" required ${disabled}></label><label>Medio de pago<select id="client-payment-method" name="method" ${disabled}>${[['transferencia','Transferencia'],['efectivo','Efectivo'],['otro','Otro']].map(([v,l])=>`<option value="${v}" ${d.method===v?'selected':''}>${l}</option>`).join('')}</select></label></div><label>Nota opcional<input id="client-payment-note" name="note" maxlength="1000" value="${esc(d.note)}" ${disabled}></label><label class="check-label"><input id="client-payment-verified" type="checkbox" required ${d.verified?'checked':''} ${disabled}> Verifiqué que el pago fue recibido</label>${CindyNotices.editor('client-inline',d.notify,d.noticeTemplate,CindyNotices.format(d.noticeTemplate,CindyNotices.values(client,order,d.amount,d.date,balance(cid))),locked,CindyNotices.hint(client,S.settings,S.integrations,S.demo))}<button type="submit" class="primary client-payment-confirm" ${d.busy||d.needsRefresh?'disabled':''}>${d.busy?'Guardando…':d.pending?'Reintentar el mismo abono':'Confirmar abono'}</button></form>`}<div role="status" aria-live="polite">${d.success?`<p class="client-payment-success">${esc(d.success)}</p>`:''}${d.error?`<p class="danger">${esc(d.error)}</p>`:''}${CindyNotices.status(d.notice)}${d.needsRefresh?'<button id="client-payment-refresh" class="outline">Actualizar saldos</button>':''}</div></aside>`;
 }
 function bind(){
  const f=$('#client-payment-form');const cid=current;if(cid===null)return;const d=draft(cid);
  const refreshButton=$('#client-payment-refresh');if(refreshButton)refreshButton.onclick=async()=>{try{await refresh(false);d.needsRefresh=false;d.error='';render();}catch{d.error='No se pudieron actualizar los saldos. Intenta otra vez.';render();}};
  if(!f)return;
  const update=CindyNotices.bind('client-inline',()=>d,patch=>Object.assign(d,patch),()=>CindyNotices.values(S.clients.find(c=>c.id===cid),S.orders.find(o=>o.id===d.orderId),d.amount,d.date,balance(cid)));
  const inputs=[['#client-payment-order','orderId',v=>Number(v)||null],['#client-payment-amount','amount',v=>v],['#client-payment-date','date',v=>v],['#client-payment-method','method',v=>v],['#client-payment-note','note',v=>v]];
  for(const [selector,key,convert] of inputs){const input=$(selector);if(input)input.oninput=()=>{d[key]=convert(input.value);update();};}
  $('#client-payment-verified').onchange=e=>{d.verified=e.target.checked;};
  f.onsubmit=e=>submit(e,cid);

 }
 async function submit(event,cid){
  event.preventDefault();const d=draft(cid);if(d.busy||d.needsRefresh)return;
  if(!d.pending){
   const order=active(cid).find(o=>o.id===d.orderId),value=Number(d.amount);
   if(!order||order.review||!Number.isSafeInteger(value)||value<=0||value>order.balance){d.error='Elige una compra o cuenta e ingresa un monto que no supere su saldo.';render();return;}
   if(!d.verified||!/^\d{4}-\d{2}-\d{2}$/.test(d.date)){d.error='Confirma la recepción y la fecha del pago.';render();return;}
   if(d.notify&&(!d.noticeTemplate.trim()||d.noticeTemplate.length>1000)){d.error='Revisa el mensaje de confirmación.';render();return;}
   d.pending={order_id:order.id,amount:value,date:d.date,method:d.method,note:d.note,operation:op(),notify:d.notify,notice_template:d.noticeTemplate};save();
  }
  const pending={...d.pending};d.busy=true;d.error='';render();
  try{
   const result=await api('payments',pending);
   d.pending=null;save();d.amount='';d.note='';d.noticeTemplate=CindyNotices.template(S.settings);d.verified=false;d.notify=false;d.notice=result.notice||null;d.success='Abono de '+money(pending.amount)+' registrado.';
   try{await refresh(false);}catch{d.needsRefresh=true;d.error='El abono ya fue registrado. Actualiza los saldos antes de ingresar otro.';}
  }catch(error){
   if(error.status&&error.status<500){d.pending=null;save();d.error=error.message;}
   else d.error='No se pudo confirmar la respuesta. Reintenta el mismo abono; no se descontará dos veces.';
  }finally{d.busy=false;render();}
 }
 function reset(){drafts.clear();current=null;restored=false;try{sessionStorage.removeItem(storageKey);}catch{}}
 window.CindyClientPayment={view,bind,reset,hasDraft:()=>[...drafts.values()].some(d=>d.amount||d.pending||d.busy||d.needsRefresh)};
})();
