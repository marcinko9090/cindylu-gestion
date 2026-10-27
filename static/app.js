'use strict';
let S=null, csrf='', selected=null, view='clients', tab='purchases', mobile='details', query='', setup=false, salesFilter='all', salesQuery='', workplaceFilter='', clientQuery='';
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const money=n=>new Intl.NumberFormat('es-CL',{style:'currency',currency:'CLP',maximumFractionDigits:0}).format(n||0);
const day=s=>s?new Date(String(s).length===10?s+'T12:00:00':s).toLocaleDateString('es-CL',{day:'2-digit',month:'short',year:'numeric'}):'—';
const norm=s=>String(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
const initials=n=>n.split(' ').filter(Boolean).slice(0,2).map(x=>x[0]).join('');
const op=()=>Array.from(crypto.getRandomValues(new Uint8Array(20)),x=>x.toString(16).padStart(2,'0')).join('');
function toast(t){$('#toast').textContent=t;$('#toast').classList.remove('hidden');clearTimeout(toast.timer);toast.timer=setTimeout(()=>$('#toast').classList.add('hidden'),6000)}
async function api(path,data,form=false){const opts={headers:{}};if(data!==undefined){opts.method='POST';opts.headers['X-CSRF-Token']=csrf;if(form)opts.body=data;else{opts.headers['Content-Type']='application/json';opts.body=JSON.stringify(data)}}const r=await fetch('/api/'+path,opts);let j;try{j=await r.json()}catch{throw Error('No se pudo leer la respuesta del servidor.')}if(!r.ok){if(r.status===401&&path!=='login'){showAuth(false)}throw Error(j.error||'No se pudo completar la operación.')}return j}
function statusPill(p){return p.pending===0?'<span class="pill green">✓ Pagada</span>':p.due<S.today?'<span class="pill red">Vencida</span>':p.pending<p.amount?'<span class="pill warm">Abono parcial</span>':'<span class="pill">Pendiente</span>'}
function orders(cid){return S.orders.filter(o=>o.client_id===cid)}
function active(cid){return S.orders.filter(o=>(cid==null||o.client_id===cid)&&o.status==='active')}
function installments(cid){const ids=new Set(active(cid).map(o=>o.id));return S.installments.filter(i=>ids.has(i.order_id))}
function balance(cid){return active(cid).reduce((a,o)=>a+o.balance,0)}
function totals(cid){const os=active(cid),ins=installments(cid),ids=new Set(os.map(o=>o.id));return {total:os.reduce((a,o)=>a+o.total,0),paid:os.reduce((a,o)=>a+o.base_paid,0)+S.payments.filter(p=>ids.has(p.order_id)&&!p.reversed).reduce((a,p)=>a+p.amount,0),balance:balance(cid),overdue:ins.filter(i=>i.due<S.today).reduce((a,i)=>a+i.pending,0),month:ins.filter(i=>i.due.slice(0,7)===S.today.slice(0,7)).reduce((a,i)=>a+i.pending,0),next:ins.filter(i=>i.pending>0).sort((a,b)=>a.due.localeCompare(b.due))[0]}}
function stats(cid){const t=totals(cid);return `<div class="stats"><div class="stat"><div class="orb">▤</div><div><label>Total de compras</label><strong>${money(t.total)}</strong><small>${cid==null?'Todas las clientas':'Compras activas de esta clienta'}</small></div></div><div class="stat"><div class="orb">✓</div><div><label>Abonos confirmados</label><strong>${money(t.paid)}</strong><small>Incluye pagos previos importados</small></div></div><div class="stat"><div class="orb">◷</div><div><label>Saldo pendiente</label><strong>${money(t.balance)}</strong><small>Todo lo que queda por pagar</small></div></div><div class="stat"><div class="orb">▦</div><div><label>Próximo cobro pendiente</label><strong>${t.next?day(t.next.due).replace(/ de /g,' ').replace(/ 20\d\d/,''):'—'}</strong><small>${t.next?money(t.next.pending):'Sin cuotas pendientes'}</small></div></div></div>`}
function totalCard(cid){const t=totals(cid);return `<div class="card totals"><h3>La cuenta, siempre clara</h3><div class="total-row"><span>Cuotas vencidas por pagar</span><b>${money(t.overdue)}</b></div><div class="total-row"><span>Cuotas pendientes de este mes</span><b>${money(t.month)}</b></div><div class="total-row"><span>Total abonado y pagos previos</span><b>${money(t.paid)}</b></div><div class="total-row final"><span>Saldo final · Todas sus compras</span><strong>${money(t.balance)}</strong></div><p class="subtle">Las cuotas del mes y las vencidas pueden coincidir. El saldo final cuenta cada deuda una sola vez.</p></div>`}
function allocDetail(iid){const as=(S.allocations||[]).filter(a=>a.installment_id===iid);if(!as.length)return '<span class="subtle">Sin abonos aún</span>';return as.map(a=>`<span class="alloc-chip">✓ ${money(a.amount)} (${day(a.date)})</span>`).join(' ')}
function orderCard(o){const ins=S.installments.filter(i=>i.order_id===o.id),ps=S.payments.filter(p=>p.order_id===o.id&&!p.reversed),paidConfirm=ps.reduce((a,p)=>a+p.amount,0),financed=o.total-o.base_paid;return `<article class="card order"><div class="order-top"><div><span class="order-number">${esc(o.number)} · ${o.source==='shopify'?'SHOPIFY':o.source==='demo'?'EJEMPLO':o.source==='excel'?'SALDO EXCEL':'REGISTRO MANUAL'}</span><h3>Compra del ${day(o.purchased)}</h3><small>${ins.length?ins.length+' cuotas · '+ins.filter(i=>!i.pending).length+' pagadas':'Plan de cuotas por definir'} ${o.status!=='active'?'· Anulada en Shopify':''}</small></div><div class="order-total"><span>Total de compra</span><strong>${money(o.total)}</strong></div></div><div class="order-body"><div class="articles">${o.items.map(i=>`<span class="article">${i.quantity} × ${esc(i.title)}</span>`).join('')}</div><div class="formula-box"><div><span>Cálculo de esta compra:</span> <b>${money(o.total)}</b> (total)${o.base_paid?` − <b>${money(o.base_paid)}</b> (pago previo/pie)`:''}${paidConfirm?` − <b>${money(paidConfirm)}</b> (${ps.length} ${ps.length===1?'abono confirmado':'abonos confirmados'})`:''} = <strong>${money(o.balance)} pendiente</strong></div>${ins.length?`<small>Monto repartido en ${ins.length} cuotas: ${money(financed)} (${ins.map(i=>money(i.amount)).filter((v,idx,arr)=>arr.indexOf(v)===idx).join(' / ')} por cuota)</small>`:'<small>Aún sin dividir en cuotas · Pulsa «Definir cuotas» o «Ajustar cuotas / saldo» para programarlas.</small>'}</div>${o.review?`<div class="review-banner">${esc(o.review)} Puedes conciliar y destrabar esta compra con el botón «⚙ Ajustar cuotas / saldo».</div>`:''}${ins.length?`<div class="table-scroll"><table><thead><tr><th>Cuota</th><th>Vencimiento</th><th>Valor cuota</th><th>Abonado</th><th>Resta pagar</th><th>Abonos aplicados a esta cuota</th><th>Estado</th></tr></thead><tbody>${ins.map(i=>{const paidAmt=i.amount-i.pending;return `<tr><td><b>${i.number} de ${ins.length}</b></td><td>${day(i.due)}</td><td>${money(i.amount)}</td><td>${paidAmt>0?`<span class="green-text">${money(paidAmt)}</span>`:'$0'}</td><td><b>${money(i.pending)}</b></td><td>${allocDetail(i.id)}</td><td>${statusPill(i)}</td></tr>`}).join('')}</tbody></table></div>`:o.balance>0?'<div class="info-box">Esta compra todavía no tiene cuotas. Define cuántas serán y cuándo comienza el pago.</div>':'<div class="info-box">Esta compra figura pagada ($0 pendiente). Si en Shopify se marcó como pagada pero se vendió en cuotas, pulsa «⚙ Ajustar cuotas / saldo» para pasarla a cuotas.</div>'}<div class="order-bottom"><div><small>Saldo pendiente de esta compra</small><strong>${money(o.balance)}</strong></div><div class="statement-actions"><button class="outline" data-action="adjust" data-id="${o.id}">⚙ Ajustar cuotas / saldo</button>${o.balance>0&&!o.review&&o.status==='active'?`<button class="${ins.length?'primary':'primary'}" data-action="${ins.length?'pay':'plan'}" data-id="${o.id}">${ins.length?'＋ Registrar abono':'＋ Definir cuotas'}</button>`:''}</div></div></div></article>`}
function receiptCard(r){return `<div class="receipt"><div class="receipt-title"><div class="receipt-icon">▤</div><div><strong>${esc(r.filename)}</strong><small>${day(r.created)}</small><a class="receipt-link" href="/api/receipts/${r.id}/file" target="_blank" rel="noopener">Ver comprobante ↗</a></div></div>${r.status==='pending'?`<div class="receipt-review"><small>◷ Pendiente de revisión<br>El saldo aún no cambia</small><button class="primary" data-action="review" data-id="${r.id}">Revisar abono</button></div>`:`<div class="receipt-review"><span class="pill ${r.status==='confirmed'?'green':'red'}">${r.status==='confirmed'?'✓ Abono confirmado':'Comprobante rechazado'}</span></div>`}</div>`}
function noticeList(cid){return (S.payment_notices||[]).filter(n=>n.client_id===cid).map(n=>`<div class="bubble out">${esc(n.body)}<span class="bubble-time">Confirmación de abono · ${({pending:'Pendiente de envío',sending:'Enviando',sent:'Enviada',review:'Revisar envío',cancelled:'Cancelada',demo:'Simulada · no enviada'})[n.status]||esc(n.status)}</span>${n.error?`<p class="subtle">${esc(n.error)}</p>`:''}${n.status==='pending'?`<button class="text-button" data-action="cancel-notice" data-id="${n.payment_id}">Cancelar aviso</button>`:''}</div>`).join('')}
function chat(cid){const cl=S.clients.find(c=>c.id===cid),ms=S.messages.filter(m=>m.client_id===cid),rs=S.receipts.filter(r=>r.client_id===cid),seen=new Set();return `<section class="card chat"><div class="chat-head"><div class="wa-icon">◔</div><div><h3>WhatsApp · ${esc(cl.name.split(' ')[0])}</h3><p>${cl.phone?'+'+esc(cl.phone):'Teléfono por completar'}</p></div><span class="pill ${S.integrations.whatsapp?'green':''}">${S.demo?'Muestra':S.integrations.whatsapp?'Configurado':'Sin conectar'}</span></div><div class="chat-scroll" id="chat-scroll"><div class="chat-day">MENSAJES Y COMPROBANTES</div>${ms.map(m=>{let r=rs.find(x=>x.id===m.receipt_id);if(r)seen.add(r.id);return `<div class="bubble ${m.direction==='out'?'out':''}">${esc(m.body)}<span class="bubble-time">${new Date(m.created).toLocaleTimeString('es-CL',{hour:'2-digit',minute:'2-digit'})} · ${m.status==='received'?'Recibido':m.status==='sent'?'Enviado':m.status==='read'?'Leído':m.status==='delivered'?'Entregado':m.status==='demo'?'Ejemplo':m.status==='review'?'Revisar envío':esc(m.status)}</span></div>${r?receiptCard(r):''}`}).join('')}${rs.filter(r=>!seen.has(r.id)).map(receiptCard).join('')}${noticeList(cid)}${statementHistory(cid)}${!ms.length&&!rs.length?'<div class="empty"><div class="empty-symbol">◌</div><h3>La conversación comienza aquí</h3><p>Los mensajes aparecerán al conectar WhatsApp. Mientras tanto, puedes cargar un comprobante manualmente.</p></div>':''}</div><div class="chat-compose"><form id="send-form"><div class="compose-row"><button type="button" class="icon-button" data-action="upload" title="Cargar comprobante">＋</button><input id="message-draft" name="body" placeholder="Escribe una respuesta…" autocomplete="off" required maxlength="3000"><button class="send" type="submit">Enviar ↗</button></div></form><div class="chat-tools"><button class="quick" data-action="statement" data-id="${cid}">▤ Enviar estado de cuenta</button><button class="quick" data-action="quick">ϟ Respuesta rápida</button><button class="text-button" data-action="remind" data-id="${cid}">Programar cobro</button></div><label class="check-label"><input id="client-consent" type="checkbox" ${cl.consent?'checked':''}> Clienta autoriza mensajes por WhatsApp</label><p class="chat-help">${S.integrations.whatsapp?'La respuesta automática confirma la recepción, nunca el pago.':'Vinculación de Meta pendiente. Cargar un archivo aquí no envía mensajes a WhatsApp.'}</p></div></section>`}
function detail(){const cl=S.clients.find(c=>c.id===selected);if(!cl){selected=null;return clientList()}const os=orders(cl.id),ids=new Set(os.map(o=>o.id));const ps=S.payments.filter(p=>ids.has(p.order_id));return `${stats(cl.id)}${accountQuick(cl.id)}<div class="mobile-tabs"><button data-mobile="details" class="${mobile==='details'?'active':''}">Ficha y compras</button><button data-mobile="chat" class="${mobile==='chat'?'active':''}">WhatsApp y comprobantes</button></div><div class="workspace"><div class="detail-col ${mobile!=='details'?'mobile-hide':''}"><section class="card"><div class="client-heading"><div class="client-avatar">${esc(initials(cl.name))}</div><div><h2>${esc(cl.name)}</h2><p>${os.length} compras registradas · ${cl.shopify_id?'Vinculada a Shopify':'Ficha local'}</p></div><button class="text-button" data-action="edit">Editar ficha</button></div><div class="client-info"><div><span>WHATSAPP</span><strong>${cl.phone?'+'+esc(cl.phone):'Sin teléfono'}</strong></div><div><span>CORREO</span><strong>${esc(cl.email||'Sin correo')}</strong></div>${cl.notes?`<div class="full"><span>NOTAS</span><strong>${esc(cl.notes)}</strong></div>`:''}</div></section><div class="section-label" style="margin:14px 0 8px"><h3>Compras y cuotas de la clienta (${os.length})</h3><button data-action="manual" class="outline">＋ Registrar compra manual</button></div>${os.length?os.map(orderCard).join(''):'<div class="card empty"><h2>Aún no hay compras</h2><p>Sincroniza Shopify o registra una compra manual.</p></div>'}<div class="card" style="margin-top:14px"><h3>Historial de abonos (${ps.length})</h3><div class="table-scroll"><table><thead><tr><th>Fecha</th><th>Compra</th><th>Abono</th><th>Estado</th><th></th></tr></thead><tbody>${ps.map(p=>`<tr><td>${day(p.date)}</td><td>${esc(os.find(o=>o.id===p.order_id)?.number)}</td><td>${money(p.amount)}<br><small>${esc(p.method)}</small></td><td><span class="pill ${p.reversed?'red':'green'}">${p.reversed?'Anulado':'Confirmado'}</span></td><td>${!p.reversed?`<button class="text-button danger" data-action="reverse" data-id="${p.id}">Anular</button>`:''}</td></tr>`).join('')}</tbody></table></div>${!ps.length?'<p class="info-box">Todavía no hay abonos registrados aquí.</p>':''}</div>${totalCard(cl.id)}</div><div class="chat-col ${mobile!=='chat'?'mobile-hide':''}">${chat(cl.id)}</div></div>`}
function clientWorkplace(c){
 const explicit=String(c.workplace||c.work||'').trim();if(explicit)return explicit;
 const notes=String(c.notes||'').trim();
 const labeled=notes.match(/(?:^|[·\n])\s*(?:lugar de trabajo|trabajo|empresa|instituci[oó]n)\s*:\s*([^·\n]+)/i);
 if(labeled)return labeled[1].trim();
 const imported=notes.match(/^COD\s+\S+\s*·\s*([^·\n]+)/i);
 return imported&&imported[1].trim()?imported[1].trim():'Sin lugar informado';
}
function clientDirectory(){
 const key=s=>norm(s).replace(/\s+/g,' ').trim(),labels=new Map();
 for(const c of S.clients){const label=clientWorkplace(c),k=key(label);if(!labels.has(k))labels.set(k,label)}
 const options=[...labels].sort((a,b)=>a[1].localeCompare(b[1],'es'));
 const q=key(clientQuery),cs=S.clients.filter(c=>(!workplaceFilter||key(clientWorkplace(c))===workplaceFilter)&&(!q||key(c.name+' '+c.phone+' '+clientWorkplace(c)).includes(q)));
 cs.sort((a,b)=>balance(b.id)-balance(a.id)||a.name.localeCompare(b.name,'es')||a.id-b.id);
 const grouped=new Map();for(const c of cs){const k=key(clientWorkplace(c));if(!grouped.has(k))grouped.set(k,{key:k,label:labels.get(k),clients:[],debt:0});const g=grouped.get(k);g.clients.push(c);g.debt+=balance(c.id)}
 const groups=[...grouped.values()].sort((a,b)=>a.label.localeCompare(b.label,'es'));
 return {options,clients:cs,groups,debt:cs.reduce((sum,c)=>sum+balance(c.id),0)};
}
function clientList(){
 const d=clientDirectory();return `<section class="card client-directory-controls"><div class="section-label"><h2>Clientas por lugar de trabajo</h2><div><button class="outline" data-action="cxc-review">Importar Excel Cindy Lú</button> <button class="outline" data-action="import">Importar Excel / CSV</button></div></div><div class="directory-filters"><label>Filtrar por lugar de trabajo<select id="workplace-filter"><option value="">Todos los lugares de trabajo</option>${d.options.map(([key,label])=>`<option value="${esc(key)}" ${workplaceFilter===key?'selected':''}>${esc(label)}</option>`).join('')}</select></label><label>Buscar clienta o lugar de trabajo<input id="directory-search" autocomplete="off" placeholder="Nombre, teléfono o lugar de trabajo…" value="${esc(clientQuery)}"></label></div><div class="directory-summary"><span>${d.clients.length} ${d.clients.length===1?'clienta':'clientas'} · Ordenadas de mayor a menor deuda dentro de cada lugar</span><div><small>Deuda total de la selección</small><strong>${money(d.debt)}</strong></div></div></section>${d.groups.map(g=>`<section class="workplace-group" aria-label="${esc(g.label)}"><div class="workplace-group-heading"><div><h2>${esc(g.label)}</h2><span>${g.clients.length} ${g.clients.length===1?'clienta':'clientas'}</span></div><strong>${money(g.debt)}</strong></div><div class="client-list">${g.clients.map(c=>`<button class="client-tile" data-client="${c.id}"><div class="client-avatar">${esc(initials(c.name))}</div><h3>${esc(c.name)}</h3><p>${c.phone?'+'+esc(c.phone):'Sin teléfono'}</p><strong>${money(balance(c.id))}</strong><small>Deuda total pendiente</small></button>`).join('')}</div></section>`).join('')}${!d.clients.length?'<div class="card empty"><h2>Sin coincidencias</h2><p>Prueba con otro nombre o selecciona otro lugar de trabajo.</p></div>':''}`;
}
function overview(){const ts=totals(null),pending=S.receipts.filter(r=>r.status==='pending');return `${stats(null)}<div class="grid-two"><div class="card"><div class="card-head"><h2>Para revisar hoy</h2><span class="pill warm">${pending.length} comprobantes</span></div>${pending.slice(0,8).map(r=>`<div class="list-line"><div class="client-avatar">${esc(initials(S.clients.find(c=>c.id===r.client_id)?.name||'?'))}</div><div class="grow"><strong>${esc(S.clients.find(c=>c.id===r.client_id)?.name)}</strong><p class="subtle">Comprobante pendiente · ${day(r.created)}</p></div><button class="outline" data-client="${r.client_id}">Abrir ficha</button></div>`).join('')||'<div class="empty"><div class="empty-symbol">✓</div><p>No hay comprobantes pendientes.</p></div>'}</div><div class="card totals"><h2>Tu cartera de pagos</h2><div class="total-row"><span>Vencido por cobrar</span><b>${money(ts.overdue)}</b></div><div class="total-row"><span>Cuotas pendientes del mes</span><b>${money(ts.month)}</b></div><div class="total-row final"><span>Saldo por cobrar</span><strong>${money(ts.balance)}</strong></div><p class="subtle">Incluye las compras sin plan de cuotas. Las anuladas se muestran por separado en su ficha.</p></div></div><div class="card"><div class="card-head"><h2>Últimas compras</h2><button class="outline" data-action="sync">↻ Sincronizar Shopify</button></div><div class="table-scroll"><table><thead><tr><th>Pedido</th><th>Clienta</th><th>Fecha</th><th>Total</th><th>Saldo</th><th></th></tr></thead><tbody>${S.orders.slice(0,10).map(o=>`<tr><td>${esc(o.number)}</td><td>${esc(S.clients.find(c=>c.id===o.client_id)?.name)}</td><td>${day(o.purchased)}</td><td>${money(o.total)}</td><td>${money(o.balance)}</td><td><button class="text-button" data-client="${o.client_id}">Ver compra →</button></td></tr>`).join('')}</tbody></table></div></div>`}
function reminders(){return `<div class="card"><div class="card-head"><h2>Cobros programados</h2><span class="pill">Hora local del dispositivo</span></div><div class="info-box">Los cobros se envían solo con el servidor encendido, WhatsApp configurado, envíos habilitados y plantilla aprobada. Se pausan si la clienta tiene un comprobante pendiente de revisión.</div>${S.reminders.map(r=>`<div class="list-line"><div class="grow"><strong>${esc(S.clients.find(c=>c.id===r.client_id)?.name)}</strong><p class="subtle">${new Date(r.at).toLocaleString('es-CL')} · ${esc(r.body)}</p>${r.error?`<p class="danger">${esc(r.error)}</p>`:''}</div><span class="pill">${({pending:'Programado',sent:'Enviado',cancelled:'Cancelado',review:'Revisar',sending:'Enviando'})[r.status]||esc(r.status)}</span>${r.status==='pending'?`<button data-action="cancel-reminder" data-id="${r.id}" class="text-button">Cancelar</button>`:''}</div>`).join('')||'<div class="empty"><h2>Todo a su tiempo</h2><p>Abre una clienta y elige «Programar cobro» para añadir su recordatorio.</p></div>'}</div>`}
function receipts(){return `<div class="card"><div class="card-head"><h2>Comprobantes recibidos</h2><p>La foto no modifica la deuda</p></div>${S.receipts.map(r=>`<div class="list-line"><div class="grow"><strong>${esc(S.clients.find(c=>c.id===r.client_id)?.name)}</strong><p class="subtle">${esc(r.filename)} · ${day(r.created)}</p></div><span class="pill ${r.status==='confirmed'?'green':''}">${({pending:'Pendiente',confirmed:'Confirmado',rejected:'Rechazado'})[r.status]}</span><button class="outline" data-client="${r.client_id}">Ver ficha</button></div>`).join('')||'<div class="empty"><h2>Nada pendiente</h2><p>Los comprobantes se guardarán aquí y en la ficha de cada clienta.</p></div>'}</div>`}
function configuration(){const cfg=S.settings;const mode=cfg.shopify_credit_mode||'credit_when_paid';const defIns=cfg.shopify_default_installments||0;return `<div class="settings-grid"><section class="card"><div class="integration"><div class="mark">S</div><div><h3>Shopify · Enlace de clientas y ventas</h3><p>${esc(S.integrations.shop||'cindylu.myshopify.com')}</p></div><span class="pill ${S.integrations.shopify?'green':''}">${S.integrations.shopify?'Conectado':'Por enlazar'}</span></div><p>Importa clientas, ventas y artículos desde Shopify. Como Shopify suele marcar los pedidos como «Pagado», aquí puedes hacer que entren automáticamente con saldo pendiente para controlar sus cuotas en Cindy Lú.</p><form id="shopify-form" style="margin-top:14px"><div class="fields"><label class="full">Dominio de tu tienda Shopify<input name="shopify_domain" value="${esc(cfg.shopify_domain||S.integrations.shop||'cindylu.myshopify.com')}" placeholder="cindylu.myshopify.com" required></label><label class="full">Token de acceso Admin API (shpat_…)<input name="shopify_token" type="password" placeholder="${cfg.has_shopify_token?'Token guardado en el servidor (escribe otro solo si deseas cambiarlo)':'Pega aquí tu token shpat_... de Shopify Admin API'}"></label><label class="full">¿Cómo importar los pedidos que en Shopify figuran «Pagados»?<select name="shopify_credit_mode"><option value="credit_when_paid" ${mode==='credit_when_paid'?'selected':''}>Vendemos en cuotas: si en Shopify dice «Pagado», importar con saldo total pendiente aquí (Recomendado)</option><option value="credit_all" ${mode==='credit_all'?'selected':''}>Pasar siempre el 100% del total de cada pedido a saldo en cuotas en Cindy Lú</option><option value="respect_shopify" ${mode==='respect_shopify'?'selected':''}>Respetar como ya pagado lo que Shopify marque como pagado</option></select></label><label class="full">Cuotas automáticas al importar una venta nueva de Shopify<select name="shopify_default_installments"><option value="0" ${defIns===0?'selected':''}>Definir manualmente en cada compra (0 cuotas automáticas)</option><option value="2" ${defIns===2?'selected':''}>Dividir automáticamente en 2 cuotas mensuales</option><option value="3" ${defIns===3?'selected':''}>Dividir automáticamente en 3 cuotas mensuales</option><option value="4" ${defIns===4?'selected':''}>Dividir automáticamente en 4 cuotas mensuales</option><option value="6" ${defIns===6?'selected':''}>Dividir automáticamente en 6 cuotas mensuales</option></select></label></div><div class="info-box">${cfg.sync_at?'Última sincronización: '+new Date(cfg.sync_at).toLocaleString('es-CL'):'Todavía no se ha ejecutado una sincronización.'}<br>Sincronización automática cada 5 minutos con el servidor activo. Si necesitas cambiar el pie o las cuotas de un pedido ya importado, usa el botón «⚙ Ajustar cuotas / saldo» en la compra.</div><div class="form-actions"><button type="submit" class="outline">Guardar configuración Shopify</button><button type="button" class="primary" data-action="sync">↻ Sincronizar Shopify ahora</button></div></form></section><section class="card"><div class="integration"><div class="mark">◔</div><div><h3>WhatsApp Business</h3><p>Mensajes y comprobantes</p></div><span class="pill ${S.integrations.whatsapp?'green':''}">${S.integrations.whatsapp?'Credenciales configuradas':'Sin conectar'}</span></div><p>Requiere WhatsApp Business Platform de Meta y una dirección HTTPS pública para recibir mensajes.</p><div class="info-box">No basta con tener WhatsApp Business en el celular. El número debe incorporarse a la integración oficial; conservarlo en la app depende de la modalidad de conexión disponible.</div><p class="subtle">La recepción de comprobantes nunca confirma una transferencia bancaria.</p></section><section class="card"><h2>Mensajes y respuestas</h2><form id="settings-form"><label class="check-label"><input type="checkbox" name="sending" ${cfg.sending?'checked':''}> Habilitar envíos reales de WhatsApp</label><label class="check-label"><input type="checkbox" name="auto_reply" ${cfg.auto_reply?'checked':''}> Responder al recibir un comprobante</label><label class="check-label"><input name="payment_notify" type="checkbox" ${cfg.payment_notify?'checked':''}> Activar por defecto el aviso al confirmar abonos</label><label>Mensaje al confirmar un pago<textarea name="payment_text" rows="4">${esc(cfg.payment_text)}</textarea></label><p class="chat-help">Variables: {nombre}, {monto}, {compra}, {saldo_compra}, {saldo_total}, {fecha}. Se completan con el pago confirmado.</p><h3>Estados de cuenta en PDF</h3><div class="fields"><label>Plantilla con encabezado Documento PDF<input name="statement_template" value="${esc(cfg.statement_template)}" placeholder="estado_cuenta_cindy_lu"></label><label>Idioma<input name="statement_language" value="${esc(cfg.statement_language)}"></label></div><p class="chat-help">Fuera de la conversación de 24 horas, usa una plantilla aprobada con PDF y dos variables: nombre y saldo. Consulta el texto y la estructura en la guía.</p><label>Respuesta automática<textarea name="reply_text" rows="3">${esc(cfg.reply_text)}</textarea></label><div class="fields"><label>Plantilla aprobada en Meta<input name="template" value="${esc(cfg.template)}" placeholder="aviso_cindy_lu"></label><label>Idioma de la plantilla<input name="template_language" value="${esc(cfg.template_language)}"></label></div><p class="chat-help">Plantilla con dos variables de texto: nombre y mensaje. Debe estar aprobada para su contenido. No se enviará nada sin credenciales y autorización de la clienta.</p><div class="form-actions"><button class="primary">Guardar configuración</button></div></form></section><section class="card"><h2>Tus datos, contigo</h2><p class="info-box">Descarga un respaldo de las clientas, compras, cuotas, pagos y comprobantes ya descargados. Guárdalo en un lugar privado.</p><a href="/api/backup" class="receipt-link">↓ Descargar respaldo completo</a><h3 class="section-label">Acceso desde otros dispositivos</h3><p>Esta versión puede probarse en Windows y Mac. Para acceder desde el teléfono fuera de casa necesita un servidor con HTTPS. Consulta LEEME-PRIMERO.txt.</p><p class="chat-help">No requiere una cuenta de ChatGPT. La versión local no está publicada en internet.</p></section></div>`}
function render(){if(!S)return;const titles={clients:['Clientas y pagos','Cada compra, cada abono. Todo en su lugar.'],'shopify-sales':['Ventas realizadas en Shopify y Pedidos','Productos, datos de la clienta, programación de cuotas y fechas de cobro en un solo lugar.'],overview:['Un vistazo a tu tienda','Lo importante de hoy, en un solo lugar.'],receipts:['Comprobantes','Revisa primero. Confirma después.'],reminders:['Cobros programados','Acompaña cada cuota con un recordatorio.'],settings:['Configuración','Conecta tu tienda a tu manera.']};$('#page-title').textContent=titles[view][0];$('#page-subtitle').textContent=titles[view][1];$$('nav button').forEach(b=>b.classList.toggle('active',b.dataset.view===view));$('#pending-count').textContent=S.receipts.filter(r=>r.status==='pending').length;
const newSalesCnt=getNewSales().length;
const nsb=$('#new-sales-badge');
if(nsb){nsb.textContent='⚠️ '+newSalesCnt+' nuevas';nsb.classList.toggle('hidden',newSalesCnt===0)}
const nsBanner=$('#new-sales-banner');
if(nsBanner){
 if(newSalesCnt>0){
  nsBanner.classList.remove('hidden');
  nsBanner.innerHTML=`<div><strong>🔴 ⚠️ Atención: Tienes ${newSalesCnt} ventas nuevas</strong><div style="font-size:13px;margin-top:2px">Revisa sus productos, datos de la clienta y confirma sus cuotas y fechas de cobro.</div></div><div style="display:flex;gap:8px;align-items:center">${view!=='shopify-sales'||salesFilter!=='new'?`<button type="button" class="primary" style="background:#dc2626;border-color:#dc2626" id="go-new-sales">Ver ventas nuevas (${newSalesCnt}) →</button>`:`<button type="button" class="outline" id="mark-all-sales-seen">✓ Marcar todas como revisadas</button>`}</div>`;
 }else{
  nsBanner.classList.add('hidden');
 }
}$('#demo-label').classList.toggle('hidden',!S.demo);$('#connection').textContent=S.demo?'WhatsApp · Muestra':S.integrations.whatsapp?'WhatsApp configurado':'WhatsApp sin conectar';$('#connection').className='pill '+(S.integrations.whatsapp?'green':'');$('#sync-notice').textContent=S.settings.sync_error;$('#sync-notice').classList.toggle('hidden',!S.settings.sync_error);const content={clients:()=>selected?detail():clientList(),'shopify-sales':shopifySalesView,overview,receipts,reminders,settings:configuration};$('#content').innerHTML=content[view]();$('#refresh-status').textContent=S.demo?'Datos ficticios · Entorno de demostración':'Actualizado '+new Date().toLocaleTimeString('es-CL',{hour:'2-digit',minute:'2-digit'});bindContent()}
async function refresh(renderNow=true){S=await api('state');if(renderNow)render()}
function choose(id){selected=Number(id);query='';$('#search').value='';view='clients';tab='purchases';$('#suggestions').classList.add('hidden');$('#search').setAttribute('aria-expanded','false');render();$('.sidebar').classList.remove('open')}
function suggest(){query=$('#search').value;const q=norm(query.trim());const box=$('#suggestions');if(!q){box.classList.add('hidden');$('#search').setAttribute('aria-expanded','false');return}const matches=S.clients.filter(c=>norm(c.name+' '+c.phone+' '+clientWorkplace(c)).includes(q)).slice(0,20);box.innerHTML=matches.map(c=>`<button role="option" data-client="${c.id}"><div class="client-avatar">${esc(initials(c.name))}</div><div>${esc(c.name)}<small>${c.phone?'+'+esc(c.phone):'Sin teléfono'}</small></div><strong>${money(balance(c.id))}</strong></button>`).join('')||'<p>No hay coincidencias por nombre, teléfono o lugar de trabajo.</p>';box.classList.remove('hidden');$('#search').setAttribute('aria-expanded','true');box.querySelectorAll('button').forEach(b=>b.onclick=()=>choose(b.dataset.client))}
function modal(title,html,submit){$('#modal-title').textContent=title;$('#modal-body').innerHTML=html;$('#modal').showModal();const form=$('#modal-body form');if(form&&submit)form.onsubmit=async e=>{e.preventDefault();const b=form.querySelector('button[type=submit]');b.disabled=true;try{await submit(form);$('#modal').close();await refresh();toast('Cambios guardados.')}catch(err){toast(err.message)}finally{b.disabled=false}}}
const actions='<div class="form-actions"><button type="button" data-close>Cancelar</button><button type="submit" class="primary">Guardar</button></div>';
const data=f=>Object.fromEntries(new FormData(f));
function newClient(){modal('Nueva clienta',`<form><div class="fields"><label class="full">Nombre completo<input name="name" required maxlength="150" placeholder="Nombre y apellido"></label><label>WhatsApp<input name="phone" placeholder="+56 9 1234 5678"></label><label>Correo<input name="email" type="email"></label><label class="full">Notas<textarea name="notes" rows="2"></textarea></label></div><label class="check-label"><input type="checkbox" name="consent"> La clienta autorizó recibir mensajes por WhatsApp</label>${actions}</form>`,async f=>{const d=data(f);d.consent=f.consent.checked;const r=await api('clients',d);selected=r.id;view='clients'})}
function planModal(id){const o=S.orders.find(o=>o.id===id);modal('Cuotas de '+o.number,`<form><div class="info-box">Saldo por distribuir: <b>${money(o.balance)}</b>. Se divide en pesos enteros; cualquier diferencia de redondeo se reparte entre las primeras cuotas.</div><div class="fields"><label>Cantidad de cuotas<input name="count" type="number" min="1" max="60" value="3" required></label><label>Primer vencimiento<input name="first" type="date" value="${S.today}" required></label><label class="full">Frecuencia<select name="frequency"><option value="monthly">Mensual</option><option value="fortnight">Cada 15 días</option><option value="weekly">Semanal</option></select></label></div>${actions}</form>`,f=>api('plan',{...data(f),order_id:id}))}
function paymentModal(oid,rid=null){const r=rid?S.receipts.find(r=>r.id===rid):null;const cid=r?r.client_id:selected;const eligible=active(cid).filter(o=>o.balance>0&&!o.review&&S.installments.some(i=>i.order_id===o.id));if(!eligible.length){toast('Primero define las cuotas de una compra con saldo pendiente.');return}oid=oid||eligible[0].id;const operation=op();modal(r?'Revisar y confirmar comprobante':'Registrar abono',`${r?(r.mime.startsWith('image/')?`<img class="receipt-preview" src="/api/receipts/${r.id}/file" alt="Comprobante recibido">`:'')+`<a class="receipt-link" href="/api/receipts/${r.id}/file" target="_blank" rel="noopener">Abrir comprobante completo ↗</a>`:''}<form><div class="info-box">${r?'Comprueba el ingreso en tu banco y escribe el monto real. La imagen por sí sola no acredita el pago.':'Registra solo pagos que ya hayas verificado.'} El abono cubrirá primero las cuotas pendientes más antiguas de la compra elegida.</div><div class="fields"><label class="full">Compra a la que se aplica<select name="order_id">${eligible.map(o=>`<option value="${o.id}" ${o.id===oid?'selected':''}>${esc(o.number)} · ${money(o.balance)} pendiente</option>`).join('')}</select></label><label>Monto confirmado<input name="amount" type="number" min="1" step="1" required placeholder="Ej. 20000"></label><label>Fecha de pago<input name="date" type="date" value="${S.today}" required></label><label>Medio de pago<select name="method"><option value="transferencia">Transferencia</option><option value="efectivo">Efectivo</option><option value="otro">Otro</option></select></label><label>Nota<input name="note" maxlength="1000" placeholder="Referencia bancaria (opcional)"></label></div><label class="check-label"><input type="checkbox" required> Verifiqué que el pago fue recibido</label><label class="check-label"><input name="notify" type="checkbox" ${S.settings.payment_notify?'checked':''}> Enviar confirmación personalizada por WhatsApp</label><p class="subtle">El mensaje incluirá nombre, monto, compra y saldo actualizado. Si WhatsApp no está conectado, queda pendiente y podrás cancelarlo.</p><div class="form-actions">${r?`<button type="button" class="danger" id="reject-receipt">Rechazar comprobante</button>`:''}<button type="submit" class="primary">✓ Confirmar y descontar</button></div></form>`,f=>api('payments',{...data(f),receipt_id:rid,operation,notify:f.notify.checked}));if(r)$('#reject-receipt').onclick=async()=>{try{await api('receipts/'+rid+'/reject',{});$('#modal').close();await refresh();toast('Comprobante rechazado. El saldo no cambió.')}catch(e){toast(e.message)}}}
function manual(){modal('Registrar compra manual',`<form><div class="info-box">Para compras antiguas o ventas fuera de Shopify. Este registro no se envía a Shopify ni modifica stock.</div><div class="fields"><label class="full">Artículo o descripción<input name="article" required maxlength="300"></label><label>Fecha de compra<input name="purchased" type="date" value="${S.today}" required></label><label>Total de compra<input name="total" type="number" min="1" step="1" required></label><label class="full">Pagos ya recibidos antes de registrarla<input name="initial" type="number" value="0" min="0" step="1" required></label></div>${actions}</form>`,f=>api('orders',{...data(f),client_id:selected}))}
function upload(){modal('Cargar comprobante',`<form><p class="info-box">Se guardará como pendiente. No descontará dinero hasta que confirmes el abono.</p><label>Archivo (JPG, PNG, WEBP o PDF, hasta 8 MB)<input type="file" name="file" required accept="image/png,image/jpeg,image/webp,application/pdf"></label>${actions}</form>`,f=>{const fd=new FormData(f);fd.append('client_id',selected);return api('receipts',fd,true)})}
function remind(cid){modal('Programar recordatorio',`<form><div class="fields"><label class="full">Fecha y hora (hora local del dispositivo)<input name="at" type="datetime-local" required></label><label class="full">Mensaje<textarea name="body" rows="4" required maxlength="1000">Hola, ${esc(S.clients.find(c=>c.id===cid)?.name.split(' ')[0])}. Te recordamos que tienes un saldo pendiente de ${money(balance(cid))}. Gracias por tu compra en Cindy Lú.</textarea></label></div><p class="info-box">Para enviarlo automáticamente, WhatsApp debe estar conectado y la plantilla aprobada. Se pausa si hay comprobantes por revisar.</p>${actions}</form>`,f=>{const d=data(f);return api('reminders',{...d,at:new Date(d.at).toISOString(),client_id:cid})})}
async function action(name,id){try{switch(name){case'new':newClient();break;case'statement':statementModal(id||null);break;case'adjust':adjustModal(id);break;case'mark-seen':await api('settings',{mark_seen_order_id:id});await refresh();toast('Venta marcada como revisada.');break;case'edit-client-id':editClientById(id);break;case'edit-order-items':editOrderItemsModal(id);break;case'new-sale-full':newSaleFullModal();break;case'explain':explainModal(id);break;case'cxc-review':reviewCindy();break;case'cancel-notice':await api('payments/'+id+'/notification/cancel',{});await refresh();break;case'edit':editClient();break;case'import':importClients();break;case'plan':planModal(id);break;case'pay':paymentModal(id);break;case'review':paymentModal(null,id);break;case'manual':manual();break;case'upload':upload();break;case'quick':$('#message-draft').value=S.settings.reply_text;$('#message-draft').focus();break;case'remind':remind(id);break;case'cancel-reminder':await api('reminders/'+id+'/cancel',{});await refresh();break;case'sync':toast('Consultando Shopify…');const r=await api('shopify/sync',{});await refresh();toast(r.count+' pedidos revisados.');break;case'reverse':modal('Anular abono',`<form><p class="info-box">El monto volverá a quedar pendiente en las cuotas. Se conservará el historial.</p><label>Motivo de la anulación<textarea name="reason" minlength="5" required rows="3"></textarea></label>${actions}</form>`,f=>api('payments/'+id+'/reverse',data(f)));break}}catch(e){toast(e.message)}}
function bindContent(){const wf=$('#workplace-filter');if(wf)wf.onchange=()=>{workplaceFilter=wf.value;render()};const ds=$('#directory-search');if(ds)ds.oninput=()=>{clientQuery=ds.value;const pos=ds.selectionStart;render();const field=$('#directory-search');field.focus();field.setSelectionRange(pos,pos)};$$('[data-client]').forEach(b=>b.onclick=()=>choose(b.dataset.client));$$('[data-action]').forEach(b=>b.onclick=()=>action(b.dataset.action,Number(b.dataset.id)));$$('[data-tab]').forEach(b=>b.onclick=()=>{tab=b.dataset.tab;render()});$$('[data-mobile]').forEach(b=>b.onclick=()=>{mobile=b.dataset.mobile;render()});const sf=$('#send-form');if(sf)sf.onsubmit=async e=>{e.preventDefault();const draft=$('#message-draft').value,b=sf.querySelector('[type=submit]');b.disabled=true;try{await api('messages',{client_id:selected,body:draft});await refresh();toast('Mensaje enviado.')}catch(err){toast(err.message)}finally{b.disabled=false}};const cc=$('#client-consent');if(cc)cc.onchange=async()=>{try{await api('consent/'+selected,{consent:cc.checked});await refresh(false)}catch(e){toast(e.message)}};const cfg=$('#settings-form');if(cfg)cfg.onsubmit=async e=>{e.preventDefault();try{await api('settings',{...data(cfg),sending:cfg.sending.checked,auto_reply:cfg.auto_reply.checked,payment_notify:cfg.payment_notify.checked});await refresh();toast('Configuración guardada.')}catch(err){toast(err.message)}};const gns=$('#go-new-sales');if(gns)gns.onclick=()=>{view='shopify-sales';salesFilter='new';render()};const mas=$('#mark-all-sales-seen');if(mas)mas.onclick=async()=>{await api('settings',{mark_all_seen:true});salesFilter='all';await refresh();toast('Todas las ventas nuevas quedaron marcadas como revisadas.')};const sFilter=$$('[data-sales-filter]');sFilter.forEach(b=>b.onclick=()=>{salesFilter=b.dataset.salesFilter;render()});const sSearch=$('#sales-search-input');if(sSearch){sSearch.oninput=()=>{salesQuery=sSearch.value;const pos=sSearch.selectionStart;render();const el=$('#sales-search-input');if(el){el.focus();el.setSelectionRange(pos,pos)}}}const shf=$('#shopify-form');if(shf)shf.onsubmit=async e=>{e.preventDefault();try{await api('settings',data(shf));await refresh();toast('Enlace y reglas de Shopify guardados.')}catch(err){toast(err.message)}}}
function showAuth(isSetup){setup=isSetup;if(!matchMedia('(prefers-reduced-motion: reduce)').matches){$('#welcome-video').play().catch(()=>{});$('#video-pause').textContent='Pausar presentación'}$('#auth').classList.remove('hidden');$('#shell').classList.add('hidden');$('#auth-title').textContent=isSetup?'Tu tienda comienza aquí':'Bienvenida de nuevo';$('#auth-desc').textContent=isSetup?'Crea tu acceso privado. Elige una contraseña de al menos 12 caracteres.':'Un solo lugar para tus clientas, compras y pagos.';$('#login-submit').textContent=isSetup?'Crear mi acceso →':'Entrar a mi tienda →';$('#login-form').password.autocomplete=isSetup?'new-password':'current-password';$('#login-form').password.minLength=isSetup?12:1}
async function start(){const s=await api('session');if(!s.authenticated){showAuth(s.setup);if(s.demo){$('#auth-hint').innerHTML='<button type="button" id="enter-demo" class="outline">Explorar demostración →</button>';$('#enter-demo').onclick=async()=>{await api('demo',{});await start()}}return}csrf=s.csrf;$('#welcome-video').pause();$('#auth').classList.add('hidden');$('#shell').classList.remove('hidden');await refresh();if(S.demo&&S.clients.length&&!selected){selected=S.clients.find(c=>c.id===1)?.id||S.clients[0].id;render()}}
$('#login-form').onsubmit=async e=>{e.preventDefault();const b=$('#login-submit');b.disabled=true;try{const d=data(e.target);try{if($('#remember-user').checked)localStorage.setItem('cindyRememberedUser',d.email);else localStorage.removeItem('cindyRememberedUser')}catch{}if(setup){await api('setup',d);toast('Acceso creado.')}const s=await api('login',d);csrf=s.csrf;$('#login-form').password.value='';await start()}catch(err){toast(err.message)}finally{b.disabled=false}};
$('#statement-open').onclick=()=>statementModal();$('#new-client').onclick=newClient;$('#search').oninput=suggest;$('#search').onfocus=()=>{if(S)suggest()};$('#search').onkeydown=e=>{if(e.key==='ArrowDown'){e.preventDefault();$('#suggestions button')?.focus()}if(e.key==='Escape')$('#suggestions').classList.add('hidden')};$('#suggestions').onkeydown=e=>{const bs=$$('#suggestions button'),i=bs.indexOf(document.activeElement);if(e.key==='ArrowDown'){e.preventDefault();bs[(i+1)%bs.length]?.focus()}if(e.key==='ArrowUp'){e.preventDefault();bs[(i-1+bs.length)%bs.length]?.focus()}if(e.key==='Escape'){$('#suggestions').classList.add('hidden');$('#search').focus()}};
document.addEventListener('click',e=>{if(!e.target.closest('.search-wrap')){$('#suggestions').classList.add('hidden');$('#search').setAttribute('aria-expanded','false')}if(e.target.closest('[data-close]'))$('#modal').close()});$('#close-modal').onclick=()=>$('#modal').close();$('#menu').onclick=()=>$('.sidebar').classList.toggle('open');$$('nav [data-view]').forEach(b=>b.onclick=()=>{view=b.dataset.view;if(view==='clients')selected=null;render();$('.sidebar').classList.remove('open')});$('#logout').onclick=async()=>{await api('logout',{});S=null;selected=null;showAuth(false)};
setInterval(async()=>{if(!S||document.hidden||$('#modal').open||!$('#suggestions').classList.contains('hidden')||document.activeElement?.matches('input,textarea,select')||$('#message-draft')?.value)return;try{const old=JSON.stringify(S);await refresh(false);if(JSON.stringify(S)!==old)render()}catch{if(S)$('#refresh-status').textContent='Sin conexión · Reintentando'}},10000);
start().catch(e=>toast(e.message));

function editClient(){const c=S.clients.find(c=>c.id===selected);modal('Editar ficha',`<form><div class="fields"><label class="full">Nombre<input name="name" value="${esc(c.name)}" required></label><label>Teléfono<input name="phone" value="${esc(c.phone)}"></label><label>Correo<input name="email" type="email" value="${esc(c.email)}"></label><label class="full">Notas<textarea name="notes">${esc(c.notes)}</textarea></label></div>${actions}</form>`,f=>api('clients/'+selected,data(f)))}
function importClients(){modal('Importar tabla Excel o CSV de clientas, ventas y cuotas',`<form><p class="info-box">Primera hoja, hasta 1000 filas. Encabezados obligatorios: <b>nombre, telefono</b>.<br>Opcionales: <b>correo, deuda (o saldo), total, articulo, cuotas, vencimiento, fecha</b>. Si indicas número de cuotas, el plan de cuotas se creará automáticamente.</p><a href="/api/import/template" class="receipt-link">↓ Descargar plantilla CSV para Excel</a><label>Archivo Excel (.xlsx) o CSV<input type="file" name="file" accept=".xlsx,.csv" required></label><div class="form-actions"><button class="primary" type="submit">Revisar archivo</button></div></form>`,async f=>{const result=await api('import/preview',new FormData(f),true);setTimeout(()=>{const valid=result.rows.filter(r=>r.data);modal('Revisar importación',`<form><p class="info-box">${valid.length} filas válidas · ${result.rows.length-valid.length} con error. Solo se importarán las válidas. Se omiten teléfonos que ya existan.</p><div class="table-scroll"><table><thead><tr><th>Fila</th><th>Clienta</th><th>Artículo</th><th>Deuda / Cuotas / Error</th></tr></thead><tbody>${result.rows.map(r=>`<tr><td>${r.row}</td><td>${esc(r.data?.name||'—')}</td><td>${esc(r.data?.article||'—')}</td><td>${r.error?esc(r.error):money(r.data.debt)+(r.data.installments?' ('+r.data.installments+' cuotas)':'')}</td></tr>`).join('')}</tbody></table></div><div class="form-actions"><button class="primary" type="submit">Confirmar importación</button></div></form>`,async()=>{const r=await api('import/confirm',{rows:valid.map(v=>v.data)});setTimeout(()=>toast(r.inserted+' clientas importadas; '+r.skipped+' teléfonos existentes omitidos.'),100)})},100)})}

try{const remembered=localStorage.getItem('cindyRememberedUser');if(remembered){$('#login-form').email.value=remembered;$('#remember-user').checked=true}}catch{}
$('#remember-user').onchange=()=>{if(!$('#remember-user').checked){try{localStorage.removeItem('cindyRememberedUser')}catch{}}};
$('#video-sound').onclick=()=>{const v=$('#welcome-video');v.muted=!v.muted;$('#video-sound').textContent=v.muted?'Activar sonido':'Silenciar';v.play().catch(()=>{})};
$('#video-pause').onclick=()=>{const v=$('#welcome-video');if(v.paused){v.play().catch(()=>{});$('#video-pause').textContent='Pausar presentación'}else{v.pause();$('#video-pause').textContent='Reproducir presentación'}};
if(matchMedia('(prefers-reduced-motion: reduce)').matches){$('#welcome-video').autoplay=false;$('#welcome-video').pause();$('#video-pause').textContent='Reproducir presentación'}

function reviewCindy(){modal('Importar y conciliar libros Excel de Cindy Lú',`<form><p class="info-box">Selecciona tus archivos Excel (por ejemplo <b>CXC 2026</b>, <b>CLUB CINDYLÚ</b> u otros libros con hojas de ventas, clientas y saldos). El sistema analizará todas las hojas, cruzará los contactos por código/teléfono y te permitirá importar el corte elegido directamente a la tienda con sus cuotas.</p><label>Uno o varios archivos Excel (.xlsx)<input type="file" name="files" accept=".xlsx" multiple required></label><div class="form-actions"><button class="primary" type="submit">Analizar hojas e importar</button></div></form>`,async f=>{const r=await api('import/cindy-review',new FormData(f),true);const imp=r.importable_sources||[];setTimeout(()=>modal('Hojas detectadas en tus Excel',`<form id="cindy-import-form"><p class="info-box">${r.contacts} códigos con datos de contacto · ${r.sheets.length} hojas analizadas. ${imp.length?'Elige abajo qué hoja o corte de saldo deseas incorporar a la tienda:':'No se detectaron filas importables con saldo.'}</p><div class="review-table"><table><thead><tr><th>Hoja / Libro</th><th>Filas</th><th>Abonos detectados</th></tr></thead><tbody>${r.sheets.map(s=>`<tr><td><b>${esc(s.sheet)}</b><br><small>${esc(s.file)}</small></td><td>${s.rows}</td><td>${s.payments||'—'}</td></tr>`).join('')}</tbody></table>${r.balance_sources.length?`<h3 style="margin:12px 0 6px">Cortes de saldo por hoja</h3><table><thead><tr><th>Hoja</th><th>Clientas</th><th>Saldo total del corte</th></tr></thead><tbody>${r.balance_sources.map(s=>`<tr><td>${esc(s.sheet)}</td><td>${s.clients}</td><td><b>${money(s.total)}</b></td></tr>`).join('')}</tbody></table>`:''}</div>${r.comparisons.map(c=>`<p class="info-box">${esc(c.left)} frente a ${esc(c.right)}: ${c.shared} códigos comunes (${c.different} con distinto saldo). Elige solo el corte vigente que quieras controlar.</p>`).join('')}${imp.length?`<div class="fields" style="margin-top:14px"><label class="full">Hoja o corte a importar a la tienda<select name="source_id" id="cindy-source-select">${imp.map((s,idx)=>`<option value="${idx}">${esc(s.label)}</option>`).join('')}</select></label><label>Dividir saldos en cuotas<select name="installments_count"><option value="0">Definir después en cada clienta</option><option value="1">1 cuota</option><option value="2">2 cuotas</option><option value="3" selected>3 cuotas</option><option value="4">4 cuotas</option><option value="6">6 cuotas</option></select></label><label>Primer vencimiento<input type="date" name="first_due" value="${S.today}" required></label><label class="full">Frecuencia de cuotas<select name="frequency"><option value="monthly">Mensual</option><option value="fortnight">Cada 15 días</option><option value="weekly">Semanal</option></select></label></div><div class="form-actions"><button type="submit" class="primary">✓ Importar hoja seleccionada a la tienda</button></div>`:''}</form>`,imp.length?async formEl=>{const d=data(formEl);const chosen=imp[Number(d.source_id)]||imp[0];const res=await api('import/cindy-confirm',{records:chosen.records,source_label:chosen.label.split(' · ')[0],installments_count:Number(d.installments_count),first_due:d.first_due,frequency:d.frequency});setTimeout(()=>toast(`Importación lista: ${res.created_clients} nuevas clientas, ${res.updated_clients} actualizadas y ${res.created_orders} saldos/compras registrados.`),120)}:null),100)})}

function isNewSale(o){
 if(o.status!=='active'||o.balance<=0)return false;
 const seen=new Set(S.settings.seen_new_orders||[]);
 if(seen.has(o.id))return false;
 const hasIns=S.installments.some(i=>i.order_id===o.id);
 if(!hasIns)return true;
 const hasPays=S.payments.some(p=>p.order_id===o.id&&!p.reversed);
 if(!hasPays && (o.source==='shopify' || String(o.purchased).slice(0,10)>='2026-10-14'))return true;
 return false;
}
function getNewSales(){
 if(!S||!S.orders)return [];
 return S.orders.filter(isNewSale);
}
function buildClientExplanation(cid, customOpts=null){
 const cl=S.clients.find(c=>c.id===cid),os=active(cid).filter(o=>o.balance>0);
 const firstName=cl?.name.split(' ')[0]||'Clienta';
 if(!cl||!os.length)return `Hola, ${firstName} ✨ Actualmente no tienes compras con saldo pendiente en Cindy Lú.`;
 const cfg=customOpts||S.settings||{};
 const introTpl=cfg.explain_intro??'Hola, {nombre} ✨ Aquí está el detalle actualizado de tu cuenta y tus cuotas en Cindy Lú Tienda:';
 const bankTpl=cfg.explain_bank??'Datos para transferencia: Cindy Lú Tienda (envíanos tu comprobante por WhatsApp al transferir).';
 const outroTpl=cfg.explain_outro??'Cualquier duda con alguna cuota o abono avísanos y lo revisamos juntas 💛';
 const showSummary=cfg.explain_show_summary!==false;
 const showPayments=cfg.explain_show_payments!==false;
 const showInstallments=cfg.explain_show_installments!==false;
 const showBank=cfg.explain_show_bank!==false;

 const total=os.reduce((s,o)=>s+o.total,0),pending=os.reduce((s,o)=>s+o.balance,0),paid=total-pending;
 const rpl=txt=>String(txt||'').replace(/\{nombre\}/gi,firstName).replace(/\{nombre_completo\}/gi,cl.name).replace(/\{saldo\}/gi,money(pending)).replace(/\{total\}/gi,money(total));

 let lines=[];
 if(introTpl.trim())lines.push(rpl(introTpl.trim()),'');
 if(showSummary){
  lines.push(`• Total compras activas: ${money(total)}`);
  lines.push(`• Total abonado: −${money(paid)}`);
  lines.push(`• SALDO TOTAL A PAGAR: ${money(pending)}`,'');
 }
 if(showPayments||showInstallments){
  os.forEach(o=>{
   const ins=S.installments.filter(i=>i.order_id===o.id),ps=S.payments.filter(p=>p.order_id===o.id&&!p.reversed);
   const itemsTxt=o.items.map(i=>`${i.quantity}x ${i.title}`).join(', ');
   lines.push(`▸ Compra ${o.number} (${day(o.purchased)}): ${itemsTxt}`);
   if(showPayments){
    lines.push(`  Total: ${money(o.total)}${o.base_paid?` | Pago previo: −${money(o.base_paid)}`:''}${ps.length?` | Abonos: −${money(ps.reduce((a,p)=>a+p.amount,0))} (${ps.map(p=>money(p.amount)+' el '+day(p.date)).join(', ')})`:''} → Saldo pendiente: ${money(o.balance)}`);
   }
   if(showInstallments){
    if(ins.length){
     ins.forEach(i=>{
      const paidI=i.amount-i.pending;
      const st=i.pending===0?'✓ PAGADA':paidI>0?`Abonado ${money(paidI)} · Resta ${money(i.pending)}`:`Pendiente ${money(i.pending)}`;
      lines.push(`    - Cuota ${i.number}/${ins.length} (${day(i.due)}): ${money(i.amount)} → ${st}`);
     });
    }else{
     lines.push(`    - Saldo pendiente: ${money(o.balance)}`);
    }
   }
   lines.push('');
  });
 }
 if(showBank && bankTpl.trim())lines.push(rpl(bankTpl.trim()),'');
 if(outroTpl.trim())lines.push(rpl(outroTpl.trim()));
 return lines.join('\n').replace(/\n{3,}/g,'\n\n').trim();
}
function adjustModal(oid){
 const o=S.orders.find(x=>x.id===oid);if(!o)return;
 const ins=S.installments.filter(i=>i.order_id===oid),ps=S.payments.filter(p=>p.order_id===oid&&!p.reversed),paidConfirm=ps.reduce((a,p)=>a+p.amount,0);
 const firstDue=ins[0]?.due||S.today,defCount=ins.length||3;
 modal('Programar cuotas y fecha de cobro · '+o.number,`<form><div class="info-box">Define o ajusta el número de cuotas y la fecha de cobro de esta venta. Los abonos ya registrados (${money(paidConfirm)}) se conservan y descuentan automáticamente de las primeras cuotas.</div><div class="fields"><label>Total de la venta (CLP)<input name="total" type="number" min="1" step="1" value="${o.total}" required></label><label>Pago inicial / Pie previo<input name="base_paid" type="number" min="0" step="1" value="${o.base_paid}" required></label><label>Cantidad de cuotas (1 a 60)<input name="count" type="number" min="1" max="60" value="${defCount}" required></label><label>Fecha 1er cobro<input name="first" type="date" value="${firstDue}" required></label><label class="full">Frecuencia de cobro<select name="frequency"><option value="monthly">Mensual</option><option value="fortnight">Cada 15 días</option><option value="weekly">Semanal</option></select></label></div><div class="form-actions"><button type="button" data-close>Cancelar</button><button type="submit" class="primary">✓ Guardar cuotas y fecha</button></div></form>`,f=>api('orders/'+oid+'/adjust',data(f)));
}
function explainModal(cid){
 const cfg=S.settings||{};
 const introVal=cfg.explain_intro??'Hola, {nombre} ✨ Aquí está el detalle actualizado de tu cuenta y tus cuotas en Cindy Lú Tienda:';
 const bankVal=cfg.explain_bank??'Datos para transferencia: Cindy Lú Tienda (envíanos tu comprobante por WhatsApp al transferir).';
 const outroVal=cfg.explain_outro??'Cualquier duda con alguna cuota o abono avísanos y lo revisamos juntas 💛';
 const txt=buildClientExplanation(cid);
 modal('Mensaje personalizable para copiar a WhatsApp',`
  <p class="info-box" style="margin-bottom:8px">Puedes editar libremente el texto de abajo antes de copiarlo, o personalizar tu plantilla fija para que todas las clientas salgan con tu propio saludo y datos de transferencia.</p>
  <textarea id="explain-text" rows="11" style="font-family:monospace;font-size:12.5px;line-height:1.45;width:100%">${esc(txt)}</textarea>
  <div class="form-actions" style="margin-top:8px;justify-content:space-between">
   <button type="button" class="outline" id="toggle-tpl-editor">✎ Personalizar mi plantilla fija</button>
   <div style="display:flex;gap:8px">
    <button type="button" class="primary" id="copy-explain">📋 Copiar mensaje para WhatsApp</button>
   </div>
  </div>
  <div id="tpl-editor-box" class="custom-tpl-box hidden">
   <strong style="display:block;margin-bottom:8px">Plantilla personalizada (usa {nombre} y {saldo} si deseas)</strong>
   <div class="fields">
    <label class="full">Saludo inicial<input id="tpl-intro" value="${esc(introVal)}"></label>
    <label class="full">Datos de transferencia / medio de pago<input id="tpl-bank" value="${esc(bankVal)}"></label>
    <label class="full">Mensaje final de despedida<input id="tpl-outro" value="${esc(outroVal)}"></label>
   </div>
   <div style="display:flex;flex-wrap:wrap;gap:12px;margin:8px 0">
    <label class="check-label"><input type="checkbox" id="tpl-sum" ${cfg.explain_show_summary!==false?'checked':''}> Resumen total</label>
    <label class="check-label"><input type="checkbox" id="tpl-pay" ${cfg.explain_show_payments!==false?'checked':''}> Compras y abonos</label>
    <label class="check-label"><input type="checkbox" id="tpl-ins" ${cfg.explain_show_installments!==false?'checked':''}> Detalle de cuotas</label>
    <label class="check-label"><input type="checkbox" id="tpl-bnk" ${cfg.explain_show_bank!==false?'checked':''}> Datos transferencia</label>
   </div>
   <div class="form-actions">
    <button type="button" class="primary" id="save-tpl-btn">✓ Guardar plantilla para todas las clientas</button>
   </div>
  </div>
 `);
 const collectOpts=()=>({
  explain_intro:$('#tpl-intro').value,
  explain_bank:$('#tpl-bank').value,
  explain_outro:$('#tpl-outro').value,
  explain_show_summary:$('#tpl-sum').checked,
  explain_show_payments:$('#tpl-pay').checked,
  explain_show_installments:$('#tpl-ins').checked,
  explain_show_bank:$('#tpl-bnk').checked
 });
 const updateLive=()=>{
  $('#explain-text').value=buildClientExplanation(cid,collectOpts());
 };
 ['#tpl-intro','#tpl-bank','#tpl-outro','#tpl-sum','#tpl-pay','#tpl-ins','#tpl-bnk'].forEach(sel=>{
  const el=$(sel);if(el){el.oninput=updateLive;el.onchange=updateLive;}
 });
 $('#toggle-tpl-editor').onclick=()=>$('#tpl-editor-box').classList.toggle('hidden');
 $('#save-tpl-btn').onclick=async()=>{
  const opts=collectOpts();
  await api('settings',opts);
  Object.assign(S.settings,opts);
  updateLive();
  toast('Plantilla personalizada guardada.');
 };
 $('#copy-explain').onclick=()=>{
  const el=$('#explain-text');el.select();
  try{navigator.clipboard.writeText(el.value)}catch{document.execCommand('copy')}
  toast('Mensaje copiado al portapapeles listo para pegar en WhatsApp.');
 };
}
function accountQuick(cid){const os=active(cid).filter(o=>o.balance>0),total=os.reduce((s,o)=>s+o.total,0),basePaid=os.reduce((s,o)=>s+o.base_paid,0),pending=os.reduce((s,o)=>s+o.balance,0),confirmedPaid=total-basePaid-pending,ins=installments(cid).filter(i=>i.pending>0);return `<section class="card"><div class="card-head"><div><h2>Estado de cuenta rápido y cuadratura de cuotas</h2><p>Todo en una sola vista · Descarga el PDF con logo o copia el mensaje personalizable para WhatsApp.</p></div><div class="statement-actions"><button class="primary" data-action="explain" data-id="${cid}">📋 Copiar mensaje WhatsApp (editable)</button><a class="outline" href="/api/clients/${cid}/statement.pdf">↓ Descargar PDF con logo</a></div></div><div class="table-scroll"><table><thead><tr><th>Compra / Fecha</th><th>Artículos</th><th>Total compra</th><th>Pago previo</th><th>Abonos confirmados</th><th>Saldo pendiente</th><th>Cuotas pendientes</th></tr></thead><tbody>${os.map(o=>{const oIns=S.installments.filter(i=>i.order_id===o.id),pendIns=oIns.filter(i=>i.pending>0),oPaid=o.total-o.base_paid-o.balance;return `<tr><td><b>${esc(o.number)}</b><br><small>${day(o.purchased)}</small>${isNewSale(o)?'<br><span class="new-sale-pill">⚠️ Venta nueva</span>':''}</td><td>${o.items.map(i=>esc(i.quantity+' × '+i.title)).join('<br>')}${o.review?'<br><b>Saldo por revisar</b>':''}</td><td>${money(o.total)}</td><td>${money(o.base_paid)}</td><td>${money(oPaid)}</td><td><b>${money(o.balance)}</b></td><td>${pendIns.length?pendIns.map(i=>`Cuota ${i.number}/${oIns.length}: <b>${money(i.pending)}</b> (${day(i.due)})`).join('<br>'):'<span class="subtle">Por definir cuotas</span>'}</td></tr>`}).join('')}</tbody></table></div>${!os.length?'<p>No tiene compras con deuda pendiente.</p>':''}<div class="reconcile-strip"><div><span>Cuadratura exacta:</span> <b>${money(total)}</b> (compras) − <b>${money(basePaid)}</b> (pagos previos) − <b>${money(confirmedPaid)}</b> (abonos confirmados) = <strong>${money(pending)} saldo total</strong></div><small>${ins.length?`Suma de sus ${ins.length} cuotas pendientes: ${ins.map(i=>money(i.pending)).join(' + ')} = ${money(ins.reduce((a,i)=>a+i.pending,0))}`:'Define las cuotas en las compras pendientes para ver el calendario de vencimientos.'}</small></div></section>`}

function statementHistory(cid){return (S.statement_sends||[]).filter(x=>x.client_id===cid).map(x=>`<div class="bubble out"><strong>▤ Estado de cuenta PDF</strong><p>${esc(x.body)}</p><a class="receipt-link" href="/api/statement-sends/${x.id}/file">↓ Ver copia del documento</a><span class="bubble-time">${new Date(x.created).toLocaleString('es-CL')} · ${esc(({preparing:'Preparando',sending:'Enviando',sent:'Aceptado por WhatsApp',delivered:'Entregado',read:'Leído',review:'Revisar envío',failed:'No entregado',demo:'Demostración · No enviado'})[x.status]||x.status)}</span>${x.error?`<p class="subtle">${esc(x.error)}</p>`:''}</div>`).join('')}
function statementModal(initial=null){
 let chosen=null,preview=null,operation='',generation=0,busy=false;
 modal('Descargar o enviar estado de cuenta PDF',`<form id="statement-form"><label>Buscar y seleccionar clienta<input id="statement-search" placeholder="Escribe un nombre, apellido o teléfono…" autocomplete="off" role="combobox" aria-expanded="true" aria-controls="statement-results"></label><div id="statement-results" class="statement-results" role="listbox" aria-label="Coincidencias de clientas"></div><section id="statement-preview" class="statement-preview"><p>Selecciona una clienta para descargar su PDF con logo o copiar su desglose.</p></section><div id="statement-feedback" role="status" class="subtle"></div><div class="form-actions"><button type="button" id="statement-close">Cerrar</button></div></form>`);
 const input=$('#statement-search'),results=$('#statement-results'),area=$('#statement-preview');
 const select=async cid=>{chosen=cid;const cl=S.clients.find(c=>c.id===cid);if(!cl)return;input.value=cl.name;results.innerHTML='';area.innerHTML=`<div class="statement-recipient"><strong>${esc(cl.name)}</strong><span>WhatsApp: ${cl.phone?'+'+esc(cl.phone):'Sin teléfono'}</span></div><div class="total-row"><span>Saldo total pendiente</span><strong>${money(balance(cid))}</strong></div><div style="display:flex;gap:10px;margin-top:12px"><a class="primary" style="text-decoration:none;padding:10px 16px;border-radius:999px" href="/api/clients/${cid}/statement.pdf">↓ Descargar PDF con logo</a><button type="button" class="outline" id="open-explain-from-stmt">📋 Copiar mensaje WhatsApp</button></div>`;$('#open-explain-from-stmt').onclick=()=>$('#modal').close()||explainModal(cid);};
 const suggestClients=()=>{const q=norm(input.value.trim()),all=S.clients.filter(c=>norm(c.name+' '+c.phone+' '+clientWorkplace(c)).includes(q)),cs=all.slice(0,20);results.innerHTML=cs.map(c=>`<button type="button" role="option" data-statement-client="${c.id}"><span><strong>${esc(c.name)}</strong><small>${c.phone?'+'+esc(c.phone):'Sin teléfono'}</small></span><b>${money(balance(c.id))}</b></button>`).join('')||'<p>Sin coincidencias.</p>';results.querySelectorAll('button').forEach(b=>b.onclick=()=>select(Number(b.dataset.statementClient)))};
 input.oninput=suggestClients;input.onfocus=()=>{if(!chosen)suggestClients()};$('#statement-close').onclick=()=>$('#modal').close();
 if(initial)select(initial);else suggestClients();input.focus();
}
function editClientById(cid){
 const c=S.clients.find(x=>x.id===cid);if(!c)return;
 modal('Datos de la clienta · '+c.name,`<form><div class="fields"><label class="full">Nombre completo<input name="name" value="${esc(c.name)}" required></label><label>WhatsApp (con código 569)<input name="phone" value="${esc(c.phone)}" placeholder="56912345678"></label><label>Correo electrónico<input name="email" type="email" value="${esc(c.email)}"></label><label class="full">Lugar de trabajo / Código / Notas<textarea name="notes" rows="2">${esc(c.notes)}</textarea></label></div>${actions}</form>`,f=>api('clients/'+cid,data(f)));
}
function editOrderItemsModal(oid){
 const o=S.orders.find(x=>x.id===oid);if(!o)return;
 const currentItems=o.items.map(i=>(i.quantity>1?i.quantity+'x ':'')+i.title).join(', ');
 modal('Editar productos y pedido · '+o.number,`<form><div class="info-box">Puedes detallar los productos comprados (separados por coma) o ajustar el número y fecha del pedido.</div><div class="fields"><label>Número de pedido<input name="number" value="${esc(o.number)}" required></label><label>Fecha de compra<input name="purchased" type="date" value="${esc(String(o.purchased).slice(0,10))}" required></label><label class="full">Productos comprados (separados por coma)<textarea name="article" rows="3" required>${esc(currentItems)}</textarea></label></div>${actions}</form>`,f=>api('orders/'+oid+'/items',data(f)));
}
function newSaleFullModal(){
 const cs=S.clients;
 modal('Registrar venta y programar cuotas',`<form><div class="info-box">Selecciona la clienta, anota los productos y deja programadas de inmediato sus cuotas y primera fecha de cobro.</div><div class="fields"><label class="full">Clienta<select name="client_id" required>${cs.map(c=>`<option value="${c.id}" ${c.id===selected?'selected':''}>${esc(c.name)} ${c.notes?'('+esc(c.notes)+')':''}</option>`).join('')}</select></label><label class="full">Productos comprados<input name="article" required maxlength="300" placeholder="Ej. Perfume Lattafa, Set Cuidado Facial"></label><label>Fecha de venta<input name="purchased" type="date" value="${S.today}" required></label><label>Total venta (CLP)<input name="total" type="number" min="1" step="1" required placeholder="Ej. 90000"></label><label>Pie / Pago inicial recibido<input name="initial" type="number" value="0" min="0" step="1" required></label><label>Cantidad de cuotas<input name="count" type="number" min="1" max="60" value="3" required></label><label>Fecha 1er cobro<input name="first" type="date" value="${S.today}" required></label><label>Frecuencia de cobro<select name="frequency"><option value="monthly">Mensual</option><option value="fortnight">Cada 15 días</option><option value="weekly">Semanal</option></select></label></div>${actions}</form>`,async f=>{
  const d=data(f);
  const res=await api('orders',{client_id:Number(d.client_id),article:d.article,purchased:d.purchased,total:d.total,initial:d.initial});
  if(Number(d.count)>0 && (Number(d.total)-Number(d.initial))>=Number(d.count)){
   await api('plan',{order_id:res.id,count:Number(d.count),first:d.first,frequency:d.frequency});
  }
 });
}
function shopifySalesView(){
 const allActive=S.orders.filter(o=>o.status==='active'&&o.balance>0);
 const newSalesList=getNewSales();
 const q=norm(salesQuery.trim());
 const filtered=allActive.filter(o=>{
  const cl=S.clients.find(c=>c.id===o.client_id)||{name:'',phone:'',email:'',notes:''};
  const oIns=S.installments.filter(i=>i.order_id===o.id);
  const nextI=oIns.filter(i=>i.pending>0).sort((a,b)=>a.due.localeCompare(b.due))[0];
  if(salesFilter==='new' && !isNewSale(o))return false;
  if(salesFilter==='shopify' && o.source!=='shopify')return false;
  if(salesFilter==='month' && (!nextI || nextI.due.slice(0,7)!==S.today.slice(0,7)))return false;
  if(q){
   const hay=norm([o.number,cl.name,cl.phone,cl.email,cl.notes,o.items.map(i=>i.title).join(' ')].join(' '));
   if(!hay.includes(q))return false;
  }
  return true;
 });
 const totalSalesAmt=filtered.reduce((a,o)=>a+o.total,0);
 const totalPendingAmt=filtered.reduce((a,o)=>a+o.balance,0);
 const totalPaidAmt=totalSalesAmt-totalPendingAmt;

 return `
 <div class="stats">
  <div class="stat"><div class="orb" style="background:#fee2e2;color:#dc2626">⚠️</div><div><label>Ventas nuevas por revisar</label><strong style="color:#dc2626">${newSalesList.length} nuevas</strong><small>Confirma sus cuotas o márcalas listas</small></div></div>
  <div class="stat"><div class="orb">🛍</div><div><label>Ventas en lista</label><strong>${filtered.length} pedidos</strong><small>Total vendido: ${money(totalSalesAmt)}</small></div></div>
  <div class="stat"><div class="orb">✓</div><div><label>Total abonado</label><strong>${money(totalPaidAmt)}</strong><small>Descontado en estas ventas</small></div></div>
  <div class="stat"><div class="orb">◷</div><div><label>Saldo por cobrar</label><strong>${money(totalPendingAmt)}</strong><small>Deuda vigente de estos pedidos</small></div></div>
 </div>

 <section class="card" style="margin-bottom:18px">
  <div class="card-head">
   <div>
    <h2>Ventas realizadas en Shopify y Pedidos en Cuotas</h2>
    <p>Todo en una sola vista rápida: productos, clienta, cuotas, mensaje copiable para WhatsApp y PDF.</p>
   </div>
   <div class="statement-actions">
    <button class="outline" data-action="sync">↻ Sincronizar Shopify</button>
    <button class="outline" data-action="cxc-review">📥 Importar Excel</button>
    <button class="primary" data-action="new-sale-full">＋ Nueva venta y cuotas</button>
   </div>
  </div>

  <div class="sales-toolbar">
   <div class="tabs" style="margin:0">
    <button type="button" data-sales-filter="new" class="filter-btn-red ${salesFilter==='new'?'active':''}">🔴 ⚠️ Ventas nuevas (${newSalesList.length})</button>
    <button type="button" data-sales-filter="all" class="${salesFilter==='all'?'active':''}">Todas las ventas (${allActive.length})</button>
    <button type="button" data-sales-filter="shopify" class="${salesFilter==='shopify'?'active':''}">Origen Shopify (${allActive.filter(o=>o.source==='shopify').length})</button>
    <button type="button" data-sales-filter="month" class="${salesFilter==='month'?'active':''}">Cobro este mes</button>
   </div>
   <div class="sales-search">
    <input id="sales-search-input" value="${esc(salesQuery)}" placeholder="Buscar por #pedido, clienta, producto, CLC, PDI, teléfono…">
   </div>
  </div>

  <div class="table-scroll">
   <table>
    <thead>
     <tr>
      <th>Pedido / Estado</th>
      <th>Productos comprados</th>
      <th>Datos de la clienta</th>
      <th>Total / Abonado / Saldo</th>
      <th>Cuotas y Fechas de Cobro</th>
      <th>Acciones Rápidas</th>
     </tr>
    </thead>
    <tbody>
     ${filtered.slice(0,120).map(o=>{
      const cl=S.clients.find(c=>c.id===o.client_id)||{id:o.client_id,name:'Clienta',phone:'',email:'',notes:''};
      const oIns=S.installments.filter(i=>i.order_id===o.id);
      const pendIns=oIns.filter(i=>i.pending>0);
      const nextI=pendIns[0];
      const paidAmt=o.total-o.balance;
      const isNew=isNewSale(o);
      const srcBadge=o.source==='shopify'?'<span class="pill green">Shopify</span>':'<span class="pill warm">Cindy Lú</span>';
      return `<tr class="${isNew?'row-new-sale':''}">
       <td>
        <b style="font-size:15px">${esc(o.number)}</b> · <small>${day(o.purchased)}</small><br>
        ${srcBadge}
        ${isNew?`<br><span class="new-sale-pill">🔴 ⚠️ VENTA NUEVA</span><br><button type="button" class="text-button sales-edit-link" data-action="mark-seen" data-id="${o.id}">✓ Marcar revisada</button>`:''}
       </td>
       <td>
        <div style="font-weight:500">${o.items.map(i=>esc(i.quantity+' × '+i.title)).join('<br>')}</div>
        <button type="button" class="text-button sales-edit-link" data-action="edit-order-items" data-id="${o.id}">✎ Editar productos</button>
       </td>
       <td>
        <strong><a href="#" data-client="${cl.id}">${esc(cl.name)}</a></strong><br>
        <small>${cl.notes?esc(cl.notes):'Sin lugar de trabajo'}</small><br>
        <small>${cl.phone?'📱 +'+esc(cl.phone):'<span style="color:#b45309">⚠ Sin celular</span>'}</small><br>
        <button type="button" class="text-button sales-edit-link" data-action="edit-client-id" data-id="${cl.id}">✎ Editar clienta</button>
       </td>
       <td>
        <div>Total: <b>${money(o.total)}</b></div>
        <div style="color:#15803d">Abonado: −${money(paidAmt)}</div>
        <div style="margin-top:4px;font-size:14px">Saldo: <strong style="color:#8e3b5e">${money(o.balance)}</strong></div>
       </td>
       <td>
        ${oIns.length?`
         <div><b>${oIns.length} cuotas</b> · Próx.: <b>${nextI?day(nextI.due):'Pagado'}</b></div>
         <div class="sales-installments">
          ${oIns.map(i=>`<div>Cuota ${i.number}/${oIns.length} (${day(i.due)}): <b>${money(i.amount)}</b> → ${i.pending===0?'<span style="color:#15803d">✓ Pagada</span>':i.pending<i.amount?`<span style="color:#b45309">Resta ${money(i.pending)}</span>`:`<span>Pendiente ${money(i.pending)}</span>`}</div>`).join('')}
         </div>
        `:`<span class="new-sale-pill">⚠️ Definir cuotas</span>`}
       </td>
       <td>
        <div class="sales-actions">
         <button type="button" class="primary full-btn" data-action="adjust" data-id="${o.id}">📅 Programar cuotas y fecha</button>
         <button type="button" class="outline" data-action="pay" data-id="${o.id}">💵 Abonar</button>
         <button type="button" class="outline" data-action="explain" data-id="${cl.id}">📋 Mensaje</button>
         <a class="outline" href="/api/clients/${cl.id}/statement.pdf">↓ PDF</a>
         <button type="button" class="outline" data-client="${cl.id}">Ficha →</button>
        </div>
       </td>
      </tr>`;
     }).join('')}
    </tbody>
   </table>
  </div>
  ${filtered.length>120?`<p class="subtle" style="margin-top:10px">Mostrando 120 de ${filtered.length} ventas. Usa el buscador para filtrar al instante.</p>`:''}
  ${!filtered.length?`<p class="info-box" style="margin-top:12px">No hay ventas en este filtro.</p>`:''}
 </section>`;
}

