/* Settled history is descriptive. Only the CXC cut and new confirmed payments affect debt. */
(function(root){
 'use strict';
 const api={};
 api.render=function(S,cid,esc,money,day){
  const history=(S.purchase_history||[]).filter(h=>h.client_id===cid);
  if(!history.length)return '';
  const months=new Map();
  for(const h of history){const period=h.period||'Sin fecha';if(!months.has(period))months.set(period,{total:0,rows:[]});const g=months.get(period);g.total+=h.amount;g.rows.push(h);}
  const total=history.reduce((a,h)=>a+h.amount,0);
  return `<section class="card purchase-history"><div class="card-head"><h3>Histórico de compras pagadas</h3><strong>${money(total)}</strong></div><p class="subtle">Compras del CLUB por mes, con descuentos y ajustes registrados. Este histórico está pagado y no genera deuda.</p>${[...months].sort((a,b)=>b[0].localeCompare(a[0])).map(([period,g])=>`<details class="history-month"><summary><span>${esc(period)}</span><strong>${money(g.total)}</strong></summary><div class="table-scroll"><table><thead><tr><th>Fecha / pedido</th><th>Detalle disponible</th><th>Monto</th></tr></thead><tbody>${g.rows.map(h=>`<tr><td>${h.date?day(h.date):'Sin día registrado'}<small>${esc(h.number||'Sin número de pedido')}</small></td><td>${h.items?.length?`<ul class="ledger-products">${h.items.map(i=>`<li>${esc(i.quantity)} × ${esc(i.title)}</li>`).join('')}</ul>`:esc(h.detail||'Detalle no informado')}${!h.items?.length&&String(h.detail).toUpperCase()==='PEDIDO'?'<small>Productos no detallados en el Excel. Se completan al encontrar una coincidencia verificada en Shopify.</small>':''}${h.kind!=='purchase'?`<small>${h.kind==='discount'?'Descuento':'Ajuste histórico'}</small>`:''}</td><td>${money(h.amount)}</td></tr>`).join('')}</tbody></table></div></details>`).join('')}</section>`;
 };
 api.payments=function(S,cid){
  // Current cut MONTO movements are already real payments on its CXC account.
  return (S.cxc_history||[]).filter(p=>p.client_id===cid&&!p.current).map(p=>({...p,id:null,imported:true,reference:p.kind==='last_payment_reference'}));
 };
 root.CindyHistory=api;
})(typeof window!=='undefined'?window:globalThis);
