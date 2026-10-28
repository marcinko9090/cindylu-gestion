/* Money follows the purchase year; a later abono belongs to that purchase. */
(function(root){
 'use strict';
 function purchaseYear(value){
  const text=String(value||'');
  if(/^\d{4}-\d{2}-\d{2}$/.test(text))return text.slice(0,4);
  const date=new Date(text);
  return Number.isNaN(date.getTime())?'Sin fecha':new Intl.DateTimeFormat('en',{year:'numeric',timeZone:'America/Santiago'}).format(date);
 }
 function group(orders){
  const years=new Map();
  for(const o of orders){
   if(o.status!=='active')continue;
   const year=purchaseYear(o.purchased);
   if(!years.has(year))years.set(year,{year,total:0,paid:0,balance:0,open:0,count:0});
   const row=years.get(year);row.total+=o.total;row.balance+=o.balance;row.paid+=o.total-o.balance;
   row.open+=o.balance>0?1:0;row.count++;
  }
  return [...years.values()].sort((a,b)=>b.year.localeCompare(a.year));
 }
 const api={group,purchaseYear};
 if(typeof module!=='undefined'&&module.exports)module.exports=api;
 else root.CindyAnnual=api;
})(typeof window!=='undefined'?window:globalThis);
