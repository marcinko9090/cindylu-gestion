const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
const code=fs.readFileSync(path.join(__dirname,'../static/client_payment.js'),'utf8');
function fixture(model,store=new Map(),send=async()=>({id:1})){ 
 const elements=new Map();for(const id of ['client-payment-form','client-payment-order','client-payment-amount','client-payment-date','client-payment-method','client-payment-note','client-payment-verified'])elements.set('#'+id,{});
 const ctx={window:{},S:model,active:cid=>model.orders.filter(o=>o.client_id===cid&&o.status==='active'),balance:cid=>model.orders.filter(o=>o.client_id===cid&&o.status==='active').reduce((n,o)=>n+o.balance,0),
  $:q=>elements.get(q),esc:s=>String(s??'').replaceAll('<','&lt;'),money:n=>'$'+n,op:()=> 'a'.repeat(40),render(){},refresh:async()=>{},api:send,
  sessionStorage:{getItem:k=>store.get(k),setItem:(k,v)=>store.set(k,v),removeItem:k=>store.delete(k)},
  CindyNotices:{template:()=> 'Hola {nombre}',editor:()=>'',format:s=>s,values:()=>({}),hint:()=>'',bind:()=>()=>{},status:()=>''}};
 vm.createContext(ctx);vm.runInContext(code,ctx);const api=ctx.window.CindyClientPayment;
 function input(id,value){const el=elements.get('#'+id);el.value=value;el.oninput();}
 function verify(){elements.get('#client-payment-verified').onchange({target:{checked:true}});}
 return {api,ctx,elements,input,verify,submit:()=>elements.get('#client-payment-form').onsubmit({preventDefault(){}}),store};
}
const model=()=>({clients:[{id:1,name:'Clienta'}],orders:[{id:10,client_id:1,status:'active',source:'cxc',number:'CXC-2026-10-1',balance:20000}],today:'2026-10-28',settings:{},integrations:{},demo:false});
(async()=>{
 let calls=[],m=model(),f=fixture(m,new Map(),async(path,payload)=>{calls.push({path,payload});return {id:1};});
 assert(f.api.view(1).includes('Ingresar nuevo abono'));f.api.bind();
 f.input('client-payment-amount','5000');f.input('client-payment-date','2026-10-27');
 await f.submit();assert.equal(calls.length,0); // receipt confirmation is mandatory
 f.verify();await f.submit();assert.equal(calls.length,1);
 assert.equal(calls[0].path,'payments');assert.equal(calls[0].payload.order_id,10);assert.equal(calls[0].payload.amount,5000);assert.equal(calls[0].payload.date,'2026-10-27');
 assert.equal(calls[0].payload.notify,false);assert(!f.api.hasDraft());
 // An abono reduces only the explicitly selected account and therefore the client balance.
 m=model();m.orders.push({id:11,client_id:1,status:'active',source:'manual',number:'#other',balance:7000});
 f=fixture(m,new Map(),async(_path,payload)=>{m.orders.find(o=>o.id===payload.order_id).balance-=payload.amount;return {id:2};});
 const choose=f.api.view(1);assert(!choose.includes('<label class="hidden">Aplicar a'));
 f.api.bind();f.input('client-payment-order','10');f.input('client-payment-amount','5000');f.verify();await f.submit();
 assert.equal(m.orders[0].balance,15000);assert.equal(m.orders[1].balance,7000);assert.equal(f.ctx.balance(1),22000);
 assert(!f.api.view(1).includes('Saldo vigente:')); // One balance belongs below the ledger, not repeated in the form.
 m.orders[0].balance=0;
 assert(f.api.view(1).includes('value="11" selected')); // Closing a purchase must not leave a hidden stale selection.
 // Lost response after a committed payment, then a page reload: retry the identical operation.
 m=model();const store=new Map();let first;
 f=fixture(m,store,async(_path,payload)=>{first=JSON.stringify(payload);m.orders[0].balance=0;throw Error('Lost response');});
 f.api.view(1);f.api.bind();f.input('client-payment-amount','20000');f.verify();await f.submit();assert(f.api.hasDraft());
 let retried;
 f=fixture(m,store,async(_path,payload)=>{retried=JSON.stringify(payload);return {id:7};});
 assert(f.api.view(1).includes('Reintentar el mismo abono'));f.api.bind();await f.submit();
 assert.equal(retried,first);assert(!f.api.hasDraft());assert.equal(m.orders[0].balance,0);
 // Read-only Shopify snapshots never become a payable local purchase.
 m=model();m.orders=[];m.settings.shopify_pending_orders=[{total:10000,outstanding:10000}];
 f=fixture(m);const empty=f.api.view(1);assert(!empty.includes('id="client-payment-form"'));assert(empty.includes('no tiene un saldo confirmado'));
 f.api.reset();assert(!f.api.hasDraft());
 console.log('Inline abonos: selected local account, actual date, verified receipt, no automatic message, identical retry after reload and no unconfirmed Shopify debt passed.');
})().catch(e=>{console.error(e);process.exit(1);});

