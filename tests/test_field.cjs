const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../static/field.js'),'utf8');
const app=fs.readFileSync(path.join(__dirname,'../static/app.js'),'utf8');
function harness(){
 let html='',nodes=new Map(),buttons=[],requests=[],operation=0,commits=new Map(),networkFailure=false,refreshFailure=false,serverError=false;
 const store=new Map();
 const norm=s=>String(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
 const clients=[{id:1,name:'Ana Norte',phone:'56911111111',notes:'Trabajo: Hospital'},{id:2,name:'Bea Sur',phone:'56922222222',notes:'Trabajo: Colegio'},{id:3,name:'María <script>',phone:'56933333333',notes:'Trabajo: HOSPITAL'}];
 const order=(id,cid,balance,extra={})=>({id,client_id:cid,number:'#'+id,purchased:'2026-10-01',total:balance,base_paid:0,balance,review:'',status:'active',items:[{title:'Vestido & bolso',quantity:1}],...extra});
 const S={today:'2026-10-28',clients,orders:[order(11,1,20000),order(12,1,10000),order(13,1,8000,{review:'Cambio pendiente'}),order(14,1,0),order(15,1,9000,{status:'cancelled'}),order(21,2,7000)]};
 const ctx={window:{},S,norm,money:n=>'$'+new Intl.NumberFormat('es-CL').format(n),day:s=>s,esc:s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])),op:()=>String(++operation).padStart(40,'0'),sessionStorage:{getItem:k=>store.get(k),setItem:(k,v)=>store.set(k,v),removeItem:k=>store.delete(k)},console};
 ctx.active=cid=>S.orders.filter(o=>o.status==='active'&&o.client_id===cid);
 ctx.balance=cid=>ctx.active(cid).reduce((sum,o)=>sum+o.balance,0);
 ctx.$=selector=>nodes.get(selector.slice(1))||null;
 ctx.$$=selector=>selector.includes('[data-field-place]')?buttons.filter(b=>b.dataset.fieldPlace):selector.includes('[data-field-client]')?buttons.filter(b=>b.dataset.fieldClient):[];
 const attr=(text,name)=>text.match(new RegExp('(?:^|\\s)'+name+'="([^"]*)"'))?.[1]||'';
 function parse(){
  nodes=new Map();buttons=[];
  for(const match of html.matchAll(/<(input|select|button|form|fieldset|strong)(\s[^>]+)>/g)){
   const [tag,kind,attrs]=match,id=attr(attrs,'id');
   const el={value:attr(attrs,'value'),type:attr(attrs,'type'),disabled:/(?:^|\s)disabled(?:\s|$)/.test(attrs),dataset:{},selectionStart:null,textContent:'',focus(){},setSelectionRange(){}};
   if(kind==='select'){
    const body=html.slice(match.index+tag.length,html.indexOf('</select>',match.index));
    const selected=[...body.matchAll(/<option([^>]+)>/g)].find(m=>/(?:^|\s)selected(?:\s|$)/.test(m[1]));el.value=selected?attr(selected[1],'value'):'';
   }
   for(const [name,key] of [['data-field-place','fieldPlace'],['data-field-client','fieldClient']]){const v=attr(attrs,name);if(v)el.dataset[key]=v;}
   if(id)nodes.set(id,el);if(kind==='button')buttons.push(el);
  }
 }
 ctx.render=()=>{html=ctx.window.CindyField.view();parse();ctx.window.CindyField.bind();};
 ctx.refresh=async()=>{if(refreshFailure)throw Error('refresh offline');};
 ctx.api=async(route,payload)=>{
  requests.push({route,payload:{...payload}});assert.equal(route,'payments');
  if(serverError)throw Object.assign(Error('Saldo actualizado: revisa el monto.'),{status:400});
  if(commits.has(payload.operation))return {id:commits.get(payload.operation)};
  const o=S.orders.find(o=>o.id===payload.order_id);assert(payload.amount<=o.balance);o.balance-=payload.amount;commits.set(payload.operation,commits.size+1);
  if(networkFailure)throw Error('response lost after commit');
  return {id:commits.size};
 };
 vm.createContext(ctx);vm.runInContext(app.slice(app.indexOf('function clientWorkplace('),app.indexOf('function clientDirectory(')),ctx);
 function reload(){vm.runInContext(source,ctx);ctx.render();}
 reload();
 function clickPlace(name){const b=buttons.find(b=>b.dataset.fieldPlace===name);assert(b);b.onclick();}
 function clickClient(id){const b=buttons.find(b=>Number(b.dataset.fieldClient)===id);assert(b);b.onclick();}
 function chooseOrder(id){const el=nodes.get('field-order');el.value=String(id);el.onchange();}
 function enter(id,value,event='oninput'){const el=nodes.get(id);assert(el);el.value=value;el[event]();}
 return {ctx,S,store,requests,reload,clickPlace,clickClient,chooseOrder,enter,node:id=>nodes.get(id),html:()=>html,submit:()=>nodes.get('field-payment-form').onsubmit({preventDefault(){}}),network:v=>networkFailure=v,refreshFailure:v=>refreshFailure=v,serverError:v=>serverError=v};
}
(async()=>{
 const h=harness();assert(!h.node('field-client'));h.enter('field-place','hos');assert(h.html().includes('Hospital'));assert(!h.html().includes('Colegio'));
 h.clickPlace('hospital');assert(!h.html().includes('Bea Sur'));assert(h.html().includes('María &lt;script&gt;'));
 h.enter('field-client','ana');assert(!h.html().includes('María'));h.clickClient(1);
 assert(h.node('field-order'));assert.equal(h.node('field-order').value,'');assert(h.node('field-amount').disabled);
 assert(h.html().includes('value="13"  disabled'));assert(h.html().includes('value="14"  disabled'));assert(!h.html().includes('value="15"'));assert(!h.html().includes('value="21"'));
 h.chooseOrder(12);assert(!h.node('field-amount').disabled);h.enter('field-amount','5000');assert.equal(h.node('field-after-balance').textContent,'$5.000');
 assert(h.ctx.window.CindyField.hasDraft());await h.submit();
 assert.equal(h.requests.length,1);assert.equal(h.requests[0].payload.order_id,12);assert.equal(h.requests[0].payload.notify,false);
 assert.equal(h.S.orders.find(o=>o.id===12).balance,5000);assert.equal(h.S.orders.find(o=>o.id===11).balance,20000);assert.equal(h.S.orders.find(o=>o.id===21).balance,7000);
 assert(h.html().includes('Saldo de la compra: $5.000'));assert(h.html().includes('Saldo total de la clienta: $33.000'));assert.equal(h.store.size,0);
 // Overpayments are rejected against the chosen purchase even if the client owes more overall.
 h.enter('field-amount','6000');await h.submit();assert.equal(h.requests.length,1);assert(h.html().includes('no supere su saldo'));
 h.node('field-change-client').onclick();assert(!h.node('field-order'));h.node('field-change-place').onclick();assert(!h.node('field-client'));
 // An uncertain response survives reload and reuses exactly the same operation/purchase/amount.
 const lost=harness();lost.clickPlace('hospital');lost.clickClient(1);lost.chooseOrder(11);lost.enter('field-amount','3000');lost.network(true);await lost.submit();
 assert.equal(lost.S.orders[0].balance,17000);assert.equal(lost.store.size,1);const token=lost.requests[0].payload.operation;
 lost.reload();assert(lost.html().includes('Reintentar el mismo abono'));assert(lost.node('field-place').disabled);assert(lost.node('field-amount').disabled);
 lost.network(false);await lost.submit();assert.equal(lost.requests[1].payload.operation,token);assert.equal(lost.S.orders[0].balance,17000);assert.equal(lost.store.size,0);
 // A refresh failure after success must not invite a second payment.
 const stale=harness();stale.clickPlace('hospital');stale.clickClient(1);stale.chooseOrder(12);stale.enter('field-amount','2000');stale.refreshFailure(true);await stale.submit();
 assert(stale.html().includes('El abono ya fue registrado'));assert(stale.node('field-confirm').disabled);assert.equal(stale.store.size,0);assert.equal(stale.requests.length,1);
 stale.refreshFailure(false);await stale.node('field-refresh').onclick();assert(!stale.node('field-confirm').disabled);assert.equal(stale.requests.length,1);
 // Definite validation failures allow correction; double taps while awaiting a reply are ignored.
 const invalid=harness();invalid.clickPlace('hospital');invalid.clickClient(1);invalid.chooseOrder(12);invalid.enter('field-amount','2000');invalid.serverError(true);await invalid.submit();assert.equal(invalid.store.size,0);assert(!invalid.node('field-amount').disabled);
 invalid.serverError(false);const handler=invalid.node('field-payment-form').onsubmit;const e={preventDefault(){}};await Promise.all([handler(e),handler(e)]);assert.equal(invalid.requests.length,2);assert.equal(invalid.S.orders.find(o=>o.id===12).balance,8000);
 invalid.ctx.window.CindyField.reset();assert.equal(invalid.store.size,0);
 console.log('Field collection: location/client isolation, explicit purchase, balances, validation, idempotent retry/reload, double-tap and refresh failures passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
