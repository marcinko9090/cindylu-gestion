const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(require('node:path').join(__dirname,'../static/seasons.js'),'utf8');
const config={key:'halloween',event_key:'halloween',label:'Halloween',greeting:'Un toque de magia dorada',countdown:'4 días para Halloween',active:true,year:2026,variant:2,seed:64000,date:'2026-10-27',calendar:[{label:'Halloween',starts:'2026-10-21',date:'2026-10-31'}]};
const nodes=new Map(),handlers={};
const node=()=>({dataset:{},textContent:'',innerHTML:'',classList:{toggle(){},contains(){return false}},addEventListener(name,fn){handlers[name]=fn;},pause(){},play(){return Promise.resolve();}});
for(const selector of ['#season-banner','.season-banner-title','.season-banner-greeting','.season-banner-motif','.welcome-season-greeting','#season-ornaments','.welcome-glitter','#welcome-video','.auth-film','#auth'])nodes.set(selector,node());
const badge=node();
const document={body:{dataset:{seasonConfig:JSON.stringify(config)}},hidden:false,querySelector:s=>nodes.get(s)||null,querySelectorAll:()=>[badge],addEventListener(){}};
const context={window:{},document,matchMedia:()=>({matches:false}),setInterval(){},setTimeout(){},Intl,Date,fetch(){throw Error('Unexpected fetch');}};
vm.runInNewContext(source,context);
assert.equal(document.body.dataset.season,'halloween');assert.equal(badge.textContent,'4 días para Halloween');
assert(nodes.get('.welcome-glitter').innerHTML.includes('animation')===false);
assert(nodes.get('.welcome-glitter').innerHTML.includes('--duration:'));
const original=nodes.get('.welcome-glitter').innerHTML;
context.window.CindySeasons.apply({...config,countdown:'3 días para Halloween'});
assert.equal(nodes.get('.welcome-glitter').innerHTML,original); // Updating a countdown must not restart particles.
context.window.CindySeasons.apply({...config,year:2027,variant:3,seed:64031});
assert.notEqual(nodes.get('.welcome-glitter').innerHTML,original);
nodes.get('#welcome-video').currentTime=3;handlers.timeupdate();
assert.equal(nodes.get('.auth-film').dataset.phase,'brand');
nodes.get('#welcome-video').currentTime=0;handlers.timeupdate();
assert.equal(nodes.get('.auth-film').dataset.phase,'brand'); // Video looping cannot freeze/reset the finale.
assert(context.window.CindySeasons.settingsMarkup().includes('Halloween'));
console.log('Seasonal countdown, yearly composition, stable continuous finale and recurring calendar UI passed.');
