const assert=require('node:assert/strict');
const {group,purchaseYear}=require('../static/annual.js');
const input=[
 {purchased:'2025-06-30',total:100000,balance:60000,status:'active'},
 {purchased:'2025-12-01',total:20000,balance:0,status:'active'},
 {purchased:'2026-10-22',total:48390,balance:38390,status:'active'},
 {purchased:'2026-10-23',total:90000,balance:90000,status:'cancelled'}
];
assert.deepEqual(group(input),[
 {year:'2026',total:48390,paid:10000,balance:38390,open:1,count:1},
 {year:'2025',total:120000,paid:60000,balance:60000,open:1,count:2}
]);
assert.deepEqual(group([]),[]);
assert.equal(purchaseYear('2026-01-01T01:00:00Z'),'2025');
assert.equal(purchaseYear('2026-01-01'),'2026');
assert.equal(purchaseYear('2026-01'),'2026'); // A debt cut has month precision, not an invented purchase day.
const after=input.map(o=>({...o}));after[0].balance-=10000;
assert.equal(group(after)[1].paid,70000);assert.equal(group(after)[0].paid,10000);
for(const row of group(after))assert.equal(row.total-row.paid,row.balance);
assert.equal(purchaseYear(null),'Sin fecha');
console.log('Annual totals: purchase-year cohorts, abonos, paid purchases, cancellations and Chile year boundary passed.');


// Verify the real client-ledger rendering against paid/part-paid/cancelled history.
const fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(require('node:path').join(__dirname,'../static/app.js'),'utf8');
const makeOrder=(id,client_id,total,base_paid,balance,purchased,status='active',items=[])=>({id,client_id,total,base_paid,balance,purchased,status,items,number:'#'+id,review:''});
const ledgerOrders=[
 makeOrder(1,1,30000,5000,15000,'2025-06-30','active',[{quantity:3,title:'Perfume Ámbar & Rosa'}]),
 makeOrder(2,1,20000,0,0,'2026-01-05','active',[{quantity:2,title:'Perfume <Vainilla>'}]),
 {...makeOrder(3,1,9000,0,9000,'2026-10-01'),review:'Cambio por revisar'},
 makeOrder(4,1,70000,0,60000,'2026-10-02','cancelled'),
 makeOrder(5,2,50000,0,40000,'2026-10-03')
];
const ledgerPayments=[
 {id:11,order_id:1,amount:10000,date:'2026-10-10',reversed:0},
 {id:12,order_id:2,amount:20000,date:'2026-10-12',reversed:0},
 {id:13,order_id:1,amount:777,date:'2026-10-13',reversed:1},
 {id:14,order_id:4,amount:10000,date:'2026-10-14',reversed:0},
 {id:15,order_id:5,amount:10000,date:'2026-10-15',reversed:0}
];
const model={clients:[{id:1,name:'Ana <Norte>'}],orders:ledgerOrders,payments:ledgerPayments,installments:[],today:'2026-10-27'};
const ui={norm:s=>String(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase(),S:model,selected:1,clientSupportOpen:false,CindyClientPayment:{view:()=>'<aside id="client-payment-panel"></aside>'},CindyAnnual:{group},money:n=>'$'+new Intl.NumberFormat('es-CL').format(n),day:s=>s,
 esc:s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])),initials:()=> 'AN',chat:()=>'<div data-test-chat></div>',clientList:()=>'<div data-test-directory></div>'};
vm.createContext(ui);
vm.runInContext(fs.readFileSync(require('node:path').join(__dirname,'../static/history.js'),'utf8'),ui);
vm.runInContext(source.slice(source.indexOf('function clientWorkplace('),source.indexOf('function clientDirectory(')),ui);
vm.runInContext(source.slice(source.indexOf('function orders('),source.indexOf('function receiptCard(')),ui);
vm.runInContext(source.slice(source.indexOf('function ledgerProducts('),source.indexOf('function clientWorkplace(')),ui);
const upper=ui.stats(1),head=upper.slice(upper.indexOf('<thead>'),upper.indexOf('</thead>'));
assert.deepEqual([...head.matchAll(/<th>(.*?)<\/th>/g)].map(m=>m[1]),['Año','Saldo vigente']);
for(const absent of ['Total de compras','Total abonado','Compras con saldo','registradas por año'])assert(!upper.includes(absent));
assert(upper.includes('2025'));assert(upper.includes('2026'));assert(upper.includes('$15.000'));assert(upper.includes('$9.000'));
const html=ui.clientLedger(1),main=html.split('<details class="ledger-archive">')[0],archive=html.split('<details class="ledger-archive">')[1];
assert.deepEqual([...main.matchAll(/data-ledger-order="(\d+)"/g)].map(m=>Number(m[1])),[1,2,3]); // Fully paid purchase is still shown.
assert(main.includes('3 ×</span> Perfume Ámbar &amp; Rosa'));
assert(main.includes('2 ×</span> Perfume &lt;Vainilla&gt;'));
assert(main.includes('Detalle de productos no informado.'));
assert(!main.includes('Total de compras registradas en esta cuenta'));
assert(main.indexOf('Abonos realizados')<main.indexOf('ledger-current-balance'));
assert.equal((main.match(/class="total-row final ledger-current-balance"/g)||[]).length,1);
assert(main.includes('Saldo vigente</span><strong>$24.000'));
assert.deepEqual([...main.matchAll(/data-ledger-payment="(\d+)"/g)].map(m=>Number(m[1])),[11,12]);
assert(main.includes('2026-10-10'));assert(main.includes('2026-10-12'));
assert(main.includes('Sin fecha registrada'));assert(main.includes('Pago previo al registro'));assert(main.includes('$5.000'));
assert(!main.includes('Saldo pendiente'));assert(!main.includes('formula-box'));assert(!main.includes('Total abonado'));
assert(archive.includes('data-ledger-order="4"'));assert(archive.includes('data-ledger-payment="13"'));assert(archive.includes('data-ledger-payment="14"'));
assert(!html.includes('data-ledger-order="5"'));assert(!html.includes('data-ledger-payment="15"'));
assert(main.includes('data-action="pay" data-id="1"'));assert(!main.includes('data-action="pay" data-id="2"'));assert(!main.includes('data-action="pay" data-id="3"'));
let page=ui.detail();assert(page.includes('Ana &lt;Norte&gt;'));assert(!page.includes('client-info'));assert(!page.includes('class="workspace"'));
assert(page.includes('id="client-ledger-support" class="client-ledger-support" >'));assert(page.includes('data-test-chat'));assert(page.includes('data-action="share-statement"'));assert(!page.includes('data-action="explain"'));assert(!page.includes('data-action="open-whatsapp"'));
ui.clientSupportOpen=true;assert(ui.detail().includes('class="client-ledger-support" open>'));
// The same purchase-year and total balances update after a confirmed payment.
model.orders[0].balance-=1000;model.payments.push({id:16,order_id:1,amount:1000,date:'2026-10-27',reversed:0});
assert(ui.clientLedger(1).includes('Saldo vigente</span><strong>$23.000'));assert(ui.stats(1).includes('$14.000'));
model.clients.push({id:3,name:'Sin compras'});ui.selected=3;
page=ui.detail();assert(!page.includes('No hay compras registradas.'));assert(!page.includes('<h3>Compras</h3>'));assert(!page.includes('data-action="manual"'));assert(page.includes('Todavía no hay pagos registrados.'));assert(page.includes('Saldo vigente</span><strong>$0'));
ui.selected=999;assert(ui.detail().includes('data-test-directory'));assert.equal(ui.selected,null);
console.log('Simple client ledger: exact products/quantities, fully paid purchases, single current balance, dated/undated payments, annulled history, year-only summary and payment actions passed.');
model.purchase_history=[{client_id:1,period:'2024-02',date:'2024-02-10',number:'#200',amount:2500,kind:'purchase',detail:'PEDIDO',items:[{quantity:2,title:'Labial <Rosa> 5 ml'}]},
 {client_id:1,period:'2024-02',date:'2024-02-11',number:'',amount:-500,kind:'discount',detail:'DESCUENTO',items:[]}];
model.cxc_history=[{client_id:1,key:'old',date:'2026-01-03',amount:1000,current:0,kind:'last_payment_reference'},
 {client_id:1,key:'current',date:'2026-10-10',amount:500,current:1,kind:'movement'}];
model.orders.push({...makeOrder(6,1,2000,0,1500,'2026-10'),source:'cxc'});
model.payments.push({id:17,order_id:6,amount:500,date:'2026-10-10',reversed:0});
const historyHtml=ui.CindyHistory.render(model,1,ui.esc,ui.money,ui.day);
assert(historyHtml.includes('Total comprado por año'));
assert(historyHtml.includes('history-year'));
const yearly=ui.CindyHistory.years([
 {period:'2024-01',amount:5000},{period:'2024-02',amount:-500},
 {period:'2025-03',amount:1000},{period:'',date:'',amount:200}
]);
assert.equal(yearly.map(y=>y.year).join(','),'2025,2024,Sin fecha');
assert.equal(yearly[1].total,4500);
assert.equal(yearly[1].months.size,2);
assert.equal(yearly.reduce((s,y)=>s+y.total,0),5700);
assert(historyHtml.includes('$2.000'));assert(historyHtml.includes('2 × Labial &lt;Rosa&gt; 5 ml'));assert(historyHtml.includes('2024-02'));assert(historyHtml.includes('no genera deuda'));
const cutHtml=ui.clientLedger(1);
assert(!cutHtml.includes('Saldo del corte CXC'));assert(!cutHtml.includes('El archivo informa una deuda por clienta.'));assert(cutHtml.includes('Abonos realizados'));assert(!cutHtml.includes('Sin pedido indicado en CXC'));
assert(!cutHtml.includes('data-ledger-order="6"'));
assert(!ui.ledgerPaymentRow({amount:500,date:'2026-10-10'},{source:'cxc',number:'CXC-2026-10-1'}).includes('CXC-2026-10-1')); // A cut is not presented as a product purchase.
assert.equal((cutHtml.match(/data-ledger-payment="17"/g)||[]).length,1);
assert.equal(ui.CindyHistory.payments(model,1).length,1);
assert(!cutHtml.includes('ya considerado en el corte, no se descuenta otra vez'));assert(!cutHtml.includes('Último abono indicado en CXC'));assert(!cutHtml.includes('Reemplazada por corte CXC'));
console.log('Settled monthly history, exact product details, CXC cut separation, payment references and month-only year grouping passed.');



// Directory membership follows the current active debt, not settled CLUB history.
ui.norm=s=>String(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
ui.clientQuery='';ui.workplaceFilter='';ui.clientDebtView='debt';
model.settings={shopify_client_tags:{1:{tags:['Hospital','Otra etiqueta']},2:{tags:['Hospital']},3:{tags:['Colegio']},4:{tags:['Hospital']}}};
vm.runInContext(source.slice(source.indexOf('function clientDirectory('),source.indexOf('function reminders(')),ui);
model.clients=[{id:1,name:'Ana',workplace:'Hospital'},{id:2,name:'Bea',workplace:'Hospital'},
 {id:3,name:'Celia',workplace:'Colegio'},{id:4,name:'Dora',workplace:'Hospital'}];
model.orders=[makeOrder(101,1,10000,0,5000,'2026-10'),makeOrder(102,2,10000,0,0,'2026-10'),
 makeOrder(104,4,5000,0,5000,'2026-10','restructured')];
model.purchase_history=[{client_id:3,amount:900000,period:'2025-01'}];
assert.equal(ui.clientDirectory().clients.map(c=>c.id).join(','),'1');
ui.clientDebtView='no-debt';
assert.equal(ui.clientDirectory().clients.map(c=>c.id).sort().join(','),'2,3,4');
const directoryHtml=ui.clientList();assert(directoryHtml.includes('Clientas sin deuda'));assert(!directoryHtml.includes('data-client="1"'));
ui.workplaceFilter='hospital';assert.equal(ui.clientDirectory().clients.map(c=>c.id).sort().join(','),'2,4');
ui.clientQuery='Dora';assert.equal(ui.clientDirectory().clients.map(c=>c.id).join(','),'4');
ui.workplaceFilter='';ui.clientQuery='';model.orders[0].balance=0;
ui.clientDebtView='debt';assert.equal(ui.clientDirectory().clients.length,0);
ui.clientDebtView='no-debt';assert.equal(ui.clientDirectory().clients.length,4);
console.log('Debt directory: unpaid CXC, paid CXC, CLUB-only clients, archived purchases, filters and settled balance passed.');


// Every Shopify tag can filter a client, without multiplying her debt.
model.orders[0].balance=5000;ui.clientDebtView='debt';ui.workplaceFilter='otra etiqueta';
assert.equal(ui.clientDirectory().clients.map(c=>c.id).join(','),'1');assert.equal(ui.clientDirectory().debt,5000);
ui.workplaceFilter='';assert.equal(ui.clientDirectory().debt,5000);assert.equal(ui.clientDirectory().groups.length,1);
assert(ui.clientList().includes('Filtrar por etiquetas'));assert(!ui.clientList().includes('Filtrar por lugar de trabajo'));
// Shopify balances remain informational; Excel/local balance is unchanged.
model.settings.shopify_pending_orders=[{shopify_id:'gid/6437',number:'#6437',client_id:1,client_name:'Ana',phone:'',purchased:'2026-10-26',total:201950,outstanding:201950,financial_status:'PENDING',tags:['Hospital'],items:[{title:'Perfume <Rosa> 100 ml',quantity:1}]}];
ui.shopifyPendingQuery='';const pendingHtml=ui.shopifyPendingView();
assert(pendingHtml.includes('Perfume &lt;Rosa&gt; 100 ml'));assert(pendingHtml.includes('Ver ficha y abonos'));
assert.equal(ui.balance(1),5000);assert(ui.shopifyPendingClient(1).includes('#6437'));
ui.workplaceFilter='colegio';assert(!ui.shopifyPendingView().includes('Perfume &lt;Rosa&gt; 100 ml'));
console.log('Shopify pending products, Excel balances and multi-tag classification passed.');



ui.workplaceFilter='';ui.selected=1;
const reorganized=ui.detail();
assert(reorganized.indexOf('client-personal-data')<reorganized.indexOf('client-purchase-details'));
assert(reorganized.indexOf('client-purchase-details')<reorganized.indexOf('client-account-columns'));
assert(reorganized.indexOf('client-account-columns')<reorganized.indexOf('client-annual-history'));
assert(reorganized.includes('id="client-payment-panel"'));
assert(ui.clientLedger(1,true).includes('Abonos realizados'));
assert(!ui.clientLedger(1,true).includes('data-ledger-order='));
console.log('Client file: personal details, products, dated abonos and inline side panel order passed.');


// Missing Shopify tags use the existing Excel ficha, without new clients or debts.
const beforeClients=JSON.stringify(model.clients),beforeOrders=JSON.stringify(model.orders);
model.clients[0].workplace='CLC';model.settings.shopify_client_tags[1]={tags:[]};
assert.equal(ui.clientTags(model.clients[0]).join(','),'Clínica Las Condes');
assert.equal(ui.tagLabel('clc estoril'),'CLC Estoril');
assert.equal(ui.tagLabel('Clínica Las Condes Estoril'),'CLC Estoril');
model.clients[0].workplace='CLC ESTORIL';
assert.equal(ui.clientTags(model.clients[0]).join(','),'CLC Estoril');
model.clients[0].workplace='CLC';
assert.equal(ui.tagLabel('CLÍNICA LAS CONDES'),'Clínica Las Condes');
assert.equal(ui.tagLabels(['CLC','Clínica Las Condes','CLC ESTORIL']).length,2);
model.settings.shopify_client_tags[1]={tags:['VIP']};assert.equal(ui.clientTags(model.clients[0]).join(','),'VIP');
model.settings.shopify_client_tags[1]={tags:[]};ui.workplaceFilter='clinica las condes';ui.clientDebtView='debt';
assert.equal(ui.clientDirectory().clients.map(c=>c.id).join(','),'1');assert.equal(ui.clientDirectory().debt,5000);
assert.equal(model.clients.length,JSON.parse(beforeClients).length);assert.equal(JSON.stringify(model.orders),beforeOrders);
assert.equal(ui.clientTags({id:999,workplace:'sin codigo'}).join(','),'Sin etiquetas');
model.settings.shopify_pending_orders[0].tags=[];
assert(ui.shopifyPendingView().includes('Perfume &lt;Rosa&gt; 100 ml'));
console.log('Excel workplace fallback, CLC canonical label, Shopify tag precedence and unchanged client IDs/balances passed.');


// Product details survive CXC restructuring and incomplete Shopify snapshots.
const savedOrders=model.orders,savedPending=model.settings.shopify_pending_orders;
const debtBefore=ui.balance(1);
const oldProducts={...makeOrder(801,1,98490,0,98490,'2026-10-26','restructured',[{quantity:1,title:'Cartera <Steave>'},{quantity:1,title:'Base MAC stick'}]),number:'#6441',shopify_id:'gid/6441'};
model.orders=[...savedOrders,oldProducts,
 {...makeOrder(802,1,8000,0,8000,'2026-10-25','restructured',[{quantity:1,title:'Pedido #6442'}]),number:'#6442'},
 {...makeOrder(803,1,7000,0,7000,'2026-10-24','cancelled',[{quantity:1,title:'Producto anulado'}]),number:'#6443'},
 {...makeOrder(804,2,98490,0,98490,'2026-10-26','restructured',[{quantity:1,title:'Producto de otra clienta'}]),number:'#6441'}];
model.settings.shopify_pending_orders=[];
let cards=ui.clientPurchaseDetails(1);
assert(cards.includes('Cartera &lt;Steave&gt;'));assert(cards.includes('Base MAC stick'));
assert(cards.includes('Compra anterior · detalle de referencia'));
assert(!cards.includes('Pedido #6442'));assert(!cards.includes('Producto anulado'));
assert(!cards.includes('Producto de otra clienta'));
assert(!cards.includes('Pago pendiente en Shopify'));assert.equal(ui.balance(1),debtBefore);
model.settings.shopify_pending_orders=[{shopify_id:'gid/6441',number:'#6441',client_id:1,client_name:'Ana',purchased:'2026-10-26',total:98490,financial_status:'PENDING',items:[]}];
cards=ui.clientPurchaseDetails(1);
assert(cards.includes('Pago pendiente en Shopify'));assert(cards.includes('Base MAC stick'));
assert.equal((cards.match(/Base MAC stick/g)||[]).length,1);
assert(!cards.includes('data-id="801"'));assert.equal(ui.balance(1),debtBefore);
assert.equal(model.settings.shopify_pending_orders[0].items.length,0); // Read-only display, no source mutation.
model.settings.shopify_pending_orders[0].total=99999;
assert.equal((ui.clientPurchaseDetails(1).match(/Base MAC stick/g)||[]).length,1); // Separate reference, never attached to a mismatched order.
model.orders=[];model.settings.shopify_pending_orders=[];
cards=ui.clientPurchaseDetails(1);
assert(cards.includes('<h2>Compras</h2>'));assert(cards.includes('Todavía no hay productos vinculados'));
assert(cards.includes('data-action="sync"'));
model.orders=savedOrders;model.settings.shopify_pending_orders=savedPending;
console.log('Restructured products, incomplete pending details, no fabricated products and unchanged balances passed.');

// One account layout: no repeated client name, dated products, payments, balance, free abono.
const purchaseBlock=ui.clientPurchaseDetails(1),account=ui.detail();
assert(purchaseBlock.includes('COMPRA #6437'));
assert(purchaseBlock.includes('Realizada el 26 OCT 2026'));
assert(purchaseBlock.includes('Detalle de productos:'));
assert(!purchaseBlock.includes(' · Ana'));
assert(account.indexOf('Abonos realizados')<account.indexOf('ledger-current-balance'));
assert(account.indexOf('ledger-current-balance')<account.indexOf('id="client-payment-panel"'));
assert(!account.includes('Registrar compra'));
assert(!source.includes('function shopifySalesView'));
assert(!source.includes('function overview'));
assert(!source.includes('function manual('));
assert(!source.includes('function newSaleFullModal'));
const shell=fs.readFileSync(require('node:path').join(__dirname,'../templates/index.html'),'utf8');
assert(shell.includes('data-view="clients"'));
for(const old of ['data-view="overview"','data-view="shopify-sales"','data-view="order-review"','id="new-sales-banner"'])assert(!shell.includes(old));
assert(ui.clientDirectoryTabs().includes('data-directory-debt="review"'));
assert.equal(ui.purchaseDate('2026-01-01T01:00:00Z'),'31 DIC 2025');
console.log('Unified Clientas navigation, dated purchase cards, no repeated names and payments/balance/abono order passed.');

// Render the complete application (not only extracted functions) to catch broken navigation references.
const nodes=new Map();
for(const id of [...shell.matchAll(/\bid="([^"]+)"/g)].map(m=>m[1]))nodes.set('#'+id,{value:'',classList:{toggle(){},add(){},remove(){},contains(){return true;}},setAttribute(){},focus(){},querySelector(){return null;}});
const complete={console,Intl,Date,Map,Set,JSON,Number,String,Array,Math,RegExp,Promise,crypto:{},setTimeout(){},clearTimeout(){},setInterval(){},localStorage:{getItem(){return null;}},matchMedia:()=>({matches:true}),window:{addEventListener(){},scrollTo(){}},
 document:{querySelector:s=>nodes.get(s)||null,querySelectorAll:()=>[],addEventListener(){}},
 CindyField:{view:()=>'',bind(){}},CindyClientPayment:{view:()=>'<aside id="client-payment-panel"></aside>',bind(){},hasDraft:()=>false},
 CindyAnnual:{group},CindyCalm:{stop(){}},model};
vm.createContext(complete);vm.runInContext(fs.readFileSync(require('node:path').join(__dirname,'../static/history.js'),'utf8'),complete);
complete.CindyHistory=complete.window.CindyHistory;
vm.runInContext(source.replace('start().catch(e=>toast(e.message));',''),complete);
Object.assign(model,{receipts:[],messages:[],integrations:{},statement_sends:[]});
vm.runInContext("S=model;selected=null;view='clients';render();",complete);
assert(nodes.get('#content').innerHTML.includes('Clientas con deuda'));
vm.runInContext("view='shopify-sales';render();",complete);
assert.equal(nodes.get('#page-title').textContent,'Clientas');
vm.runInContext("selected=1;render();",complete);
assert(nodes.get('#content').innerHTML.includes('COMPRA #6437'));
assert(nodes.get('#content').innerHTML.includes('id="client-payment-panel"'));
vm.runInContext("S.orders.push({id:999,client_id:1,status:'cancelled',source:'excel',purchased:'2026-10-28',total:50,balance:0,items:[]});S.payments.push({id:999,order_id:999,reversed:true,date:'2026-10-28',amount:50});selected=1;render();",complete);
assert(nodes.get('#content').innerHTML.includes('Registros anteriores y anulados'));
console.log('Full app renders the unified directory, legacy navigation and client account without missing functions.');


(async()=>{
 let refreshes=0,authScreens=0;
 complete.api=async()=>({authenticated:true,setup:false,csrf:'test'});
 complete.CindySeasons={apply(){},welcome(){}};
 complete.CindyCalm={start(){},stop(){}};
 complete.showAuth=()=>{authScreens++};
 complete.refresh=async()=>{refreshes++};
 nodes.set('#welcome-video',{pause(){}});
 await vm.runInContext('start()',complete);
 assert.equal(authScreens,0,'Active saved session remains signed in');
 assert.equal(refreshes,1,'Active saved session loads the workspace');
 await vm.runInContext('start()',complete);
 assert.equal(refreshes,2,'Authenticated entry loads workspace');
 complete.api=async()=>({authenticated:false,setup:false});
 await vm.runInContext('start()',complete);
 assert.equal(authScreens,1,'Expired session returns to login');
 assert.equal(refreshes,2);
 assert(shell.includes('autocomplete="username"'));
 assert(shell.includes('autocomplete="current-password"'));
 console.log('Entry gate: saved sessions show login before loading data; successful login enters; expired sessions stay at login.');
})().catch(error=>{console.error(error);process.exitCode=1;});

{
 let now=100000000,stored=String(now),expiredCount=0;const events={};
 const ctx={Date:{now:()=>now},localStorage:{getItem:()=>stored,setItem:(k,v)=>{stored=v}},document:{hidden:false,addEventListener:(n,f)=>{events[n]=f}},window:{addEventListener(){}},setInterval(){}};
 vm.runInNewContext(fs.readFileSync(require('node:path').join(__dirname,'../static/activity.js'),'utf8'),ctx);
 const activity=ctx.window.CindyActivity;
 activity.start(()=>expiredCount++);now+=2*3600000;events.pointerdown();now+=2*3600000;
 assert.equal(activity.expired(),false,'Movement extends the active session across reloads');
 now+=3600001;assert.equal(activity.expired(),true);events.pointerdown();assert.equal(expiredCount,1,'Expired movement locks before extending activity');
}
