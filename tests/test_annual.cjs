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
const ui={S:model,selected:1,clientSupportOpen:false,CindyAnnual:{group},money:n=>'$'+new Intl.NumberFormat('es-CL').format(n),day:s=>s,
 esc:s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])),initials:()=> 'AN',chat:()=>'<div data-test-chat></div>',clientList:()=>'<div data-test-directory></div>'};
vm.createContext(ui);
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
assert(main.includes('Total de todas las compras</span><strong>$59.000'));
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
assert(page.includes('id="client-ledger-support" class="client-ledger-support" >'));assert(page.includes('data-test-chat'));assert(page.includes('data-action="explain"'));assert(page.includes('/api/clients/1/statement.pdf'));
ui.clientSupportOpen=true;assert(ui.detail().includes('class="client-ledger-support" open>'));
// The same purchase-year and total balances update after a confirmed payment.
model.orders[0].balance-=1000;model.payments.push({id:16,order_id:1,amount:1000,date:'2026-10-27',reversed:0});
assert(ui.clientLedger(1).includes('Saldo vigente</span><strong>$23.000'));assert(ui.stats(1).includes('$14.000'));
model.clients.push({id:3,name:'Sin compras'});ui.selected=3;
page=ui.detail();assert(page.includes('No hay compras registradas.'));assert(page.includes('Todavía no hay pagos registrados.'));assert(page.includes('Saldo vigente</span><strong>$0'));
ui.selected=999;assert(ui.detail().includes('data-test-directory'));assert.equal(ui.selected,null);
console.log('Simple client ledger: exact products/quantities, fully paid purchases, single current balance, dated/undated payments, annulled history, year-only summary and payment actions passed.');
