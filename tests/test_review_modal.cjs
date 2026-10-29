const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(require('node:path').join(__dirname,'../static/app.js'),'utf8');
let markup,submit,request;
const context={Intl,Number,S:{settings:{shopify_review_orders:[{number:'#1',client_name:'Prueba',total:'38500',currency:'CLP',shopify_id:'1',fingerprint:'snapshot'}]}},day:()=>'',actions:'',modal:(title,html,save)=>{markup=html;submit=save},api:(path,data)=>{request={path,data}}};
vm.createContext(context);
vm.runInContext(source.split('\n').filter(line=>line.startsWith('const esc=')||line.startsWith('const remoteMoney=')).join('\n')+'\n'+source.slice(source.indexOf('function shopOrderReviewModal(')),context);
context.shopOrderReviewModal(0);
assert(markup.includes('38.500 CLP'));
assert(markup.includes('Al contado')&&markup.includes('Agregar al saldo'));
for(const decision of ['cash','debt']){submit({decision:{value:decision}});assert.equal(request.path,'shopify/review');assert.equal(request.data.decision,decision);assert.equal(request.data.fingerprint,'snapshot');}
console.log('Review dialog opens, formats totals and submits both decisions.');
