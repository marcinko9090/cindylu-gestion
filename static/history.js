/* Settled history is descriptive. Only the CXC cut and new confirmed payments affect debt. */
(function(root){
 'use strict';
 const api={};
 api.years=function(history){
  const years=new Map();
  for(const h of history){
   const year=/^\d{4}(?:-|$)/.test(h.period||h.date||'')?String(h.period||h.date).slice(0,4):'Sin fecha';
   if(!years.has(year))years.set(year,{year,total:0,months:new Map()});
   const g=years.get(year),period=h.period||'Sin fecha';
   if(!g.months.has(period))g.months.set(period,{total:0,rows:[]});
   g.total+=h.amount;g.months.get(period).total+=h.amount;g.months.get(period).rows.push(h);
  }
  return [...years.values()].sort((a,b)=>a.year==='Sin fecha'?1:b.year==='Sin fecha'?-1:b.year.localeCompare(a.year));
 };
 api.render=function(S,cid,esc,money,day){
  const history=(S.purchase_history||[]).filter(h=>h.client_id===cid);
  if(!history.length)return '';
  return `<section class="card purchase-history"><div class="card-head"><h3>Total comprado por año · CLUB</h3></div><p class="subtle">Monto final de cada año, con descuentos y ajustes registrados. Abre un año para ver fechas y productos disponibles. Este histórico no genera deuda; los abonos libres y el saldo actual se muestran en la cuenta CXC.</p>${api.years(history).map(y=>`<details class="history-month history-year"><summary><span>${esc(y.year)}</span> <strong>${money(y.total)}</strong></summary>${[...y.months].sort((a,b)=>b[0].localeCompare(a[0])).map(([period,g])=>`<details class="history-month"><summary><span>${esc(period)}</span><strong>${money(g.total)}</strong></summary><div class="table-scroll"><table><thead><tr><th>Fecha / pedido</th><th>Detalle disponible</th><th>Monto</th></tr></thead><tbody>${g.rows.map(h=>`<tr><td>${h.date?day(h.date):'Sin día registrado'}<small>${esc(h.number||'Sin número de pedido')}</small></td><td>${h.items?.length?`<ul class="ledger-products">${h.items.map(i=>`<li>${esc(i.quantity)} × ${esc(i.title)}</li>`).join('')}</ul>`:esc(h.detail||'Detalle no informado')}${!h.items?.length&&String(h.detail).toUpperCase()==='PEDIDO'?'<small>Productos no detallados en el Excel. Se completan al encontrar una coincidencia verificada en Shopify.</small>':''}${h.kind!=='purchase'?`<small>${h.kind==='discount'?'Descuento':'Ajuste histórico'}</small>`:''}</td><td>${money(h.amount)}</td></tr>`).join('')}</tbody></table></div></details>`).join('')}</details>`).join('')}</section>`;
 };
 api.payments=function(S,cid){
  // Current cut MONTO movements are already real payments on its CXC account.
  return (S.cxc_history||[]).filter(p=>p.client_id===cid&&!p.current).map(p=>({...p,id:null,imported:true,reference:p.kind==='last_payment_reference'}));
 };
 root.CindyHistory=api;
})(typeof window!=='undefined'?window:globalThis);

