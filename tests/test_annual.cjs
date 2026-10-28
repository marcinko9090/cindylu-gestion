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
