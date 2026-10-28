const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const code=fs.readFileSync(path.join(__dirname,'../static/calm.js'),'utf8');
function fixture(){
 let now=0,id=0,modal=false,hiddenShell=false;
 const timers=new Map(),events={},nodes=[],saved=new Map();
 const doc={hidden:false,body:{appendChild:n=>nodes.push(n)},
  querySelector:q=>q==='dialog[open]'?(modal?{}:null):q==='#shell'?{classList:{contains:()=>hiddenShell}}:null,
  createElement:()=>({setAttribute(){},remove(){nodes.splice(nodes.indexOf(this),1);}}),
  addEventListener:(type,fn)=>events[type]=fn};
 const ctx={document:doc,Intl,Date,performance:{now:()=>now},
  localStorage:{getItem:k=>saved.get(k),setItem:(k,v)=>saved.set(k,v)},
  setTimeout:(fn,ms)=>{timers.set(++id,{fn,at:now+ms});return id;},clearTimeout:i=>timers.delete(i),
  setInterval:(fn,ms)=>{timers.set(++id,{fn,at:now+ms,period:ms});return id;},clearInterval:i=>timers.delete(i)};
 vm.createContext(ctx);vm.runInContext(code,ctx);
 function advance(ms){const end=now+ms;while(true){let hit;for(const [i,t] of timers)if(t.at<=end&&(!hit||t.at<hit[1].at))hit=[i,t];if(!hit)break;now=hit[1].at;if(hit[1].period)hit[1].at+=hit[1].period;else timers.delete(hit[0]);hit[1].fn();}now=end;}
 return {api:ctx.CindyCalm,advance,events,doc,nodes,saved,modal:v=>modal=v,shell:v=>hiddenShell=v};
}
let f=fixture();f.api.start();f.advance(0);assert.equal(f.nodes.length,1);assert(f.nodes[0].textContent.length<65);
f.advance(4999);assert.equal(f.nodes.length,1);f.advance(1);assert.equal(f.nodes.length,0);
f.api.start();f.advance(0);assert.equal(f.nodes.length,0); // refresh cannot replay
f.api.stop();f.api.start();f.advance(0);assert.equal(f.nodes.length,0); // same-day login cannot replay
assert.equal(f.api.elapsed(0,1800000,0,true),60000);assert.equal(f.api.elapsed(0,1800000,0,false),0);
f.advance(31*60000);assert.equal(f.nodes.length,0); // idle page
f.api.stop();f.api.start();f.advance(0);
for(let i=0;i<29*60;i++){f.events.pointerdown({isTrusted:true});f.advance(1000);}
assert.equal(f.nodes.length,0);
for(let i=0;i<60;i++){f.events.keydown({isTrusted:true});f.advance(1000);}
assert.equal(f.nodes.length,1);f.advance(5000);assert.equal(f.nodes.length,0);
f.doc.hidden=true;f.events.visibilitychange();f.advance(60*60000);assert.equal(f.nodes.length,0);
f.doc.hidden=false;f.events.visibilitychange();assert.equal(f.nodes.length,0);
f.api.stop();f.advance(60*60000);assert.equal(f.nodes.length,0);
f=fixture();f.modal(true);f.api.start();f.advance(0);assert.equal(f.nodes.length,0);
f=fixture();f.api.start({delay:4200});f.advance(4199);assert.equal(f.nodes.length,0);f.advance(1);assert.equal(f.nodes.length,1);
f.api.stop();assert.equal(f.nodes.length,0);f.advance(5000);assert.equal(f.nodes.length,0);
f=fixture();f.api.start({delay:4200});f.api.stop();f.advance(5000);assert.equal(f.nodes.length,0);
assert.notEqual(f.api.phrase('2026-10-28'),f.api.phrase('2026-10-29'));
const css=fs.readFileSync(path.join(__dirname,'../static/seasons.css'),'utf8');
assert(css.includes('cindy-calm-note 5s'));assert(css.includes('cindy-calm-still 5s'));assert(css.includes('pointer-events:none'));
console.log('Calm notes: daily once, exact five seconds, real active time, idle/background exclusion, dialogs, logout, welcome delay and reduced motion passed.');

