const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(require('node:path').join(__dirname,'../static/seasons.js'),'utf8');
const config={key:'halloween',event_key:'halloween',label:'Halloween',greeting:'Un toque de magia dorada',countdown:'4 días para Halloween',active:true,year:2026,variant:2,seed:64000,date:'2026-10-27',calendar:[{label:'Halloween',starts:'2026-10-21',date:'2026-10-31'}]};
const nodes=new Map(),handlers={};
const node=()=>({dataset:{},textContent:'',innerHTML:'',classList:{toggle(){},contains(){return false}},addEventListener(name,fn){handlers[name]=fn;},pause(){},play(){return Promise.resolve();}});
for(const selector of ['#banner-garland','#header-garland','#season-banner','.season-banner-title','.season-banner-greeting','.season-banner-motif','.welcome-season-greeting','#season-ornaments','.welcome-glitter','#welcome-video','.auth-film','#auth'])nodes.set(selector,node());
const badge=node();
const document={body:{dataset:{seasonConfig:JSON.stringify(config)}},hidden:false,querySelector:s=>nodes.get(s)||null,querySelectorAll:()=>[badge],addEventListener(){}};
const context={window:{},document,matchMedia:()=>({matches:false}),setInterval(){},setTimeout(){},Intl,Date,fetch(){throw Error('Unexpected fetch');}};
vm.runInNewContext(source,context);
assert.equal(document.body.dataset.season,'halloween');assert.equal(badge.textContent,'4 días para Halloween');
assert(nodes.get('.welcome-glitter').innerHTML.includes('animation')===false);
assert(nodes.get('.welcome-glitter').innerHTML.includes('--duration:'));
const original=nodes.get('.welcome-glitter').innerHTML;
const garland=nodes.get('#header-garland').innerHTML;assert(garland.includes('header-garland-wire'));assert(garland.includes('data-motif="pumpkin"'));assert(garland.includes('data-motif="bat"'));
assert.equal((garland.match(/class="header-garland-hanger"/g)||[]).length,9);
context.window.CindySeasons.apply({...config,countdown:'3 días para Halloween'});
assert.equal(nodes.get('.welcome-glitter').innerHTML,original);assert.equal(nodes.get('#header-garland').innerHTML,garland); // Updating a countdown must not restart particles.
context.window.CindySeasons.apply({...config,year:2027,variant:3,seed:64031});
assert.notEqual(nodes.get('.welcome-glitter').innerHTML,original);
nodes.get('#welcome-video').currentTime=3;handlers.timeupdate();
assert.equal(nodes.get('.auth-film').dataset.phase,'brand');
nodes.get('#welcome-video').currentTime=0;handlers.timeupdate();
assert.equal(nodes.get('.auth-film').dataset.phase,'brand'); // Video looping cannot freeze/reset the finale.
assert.equal(context.window.CindySeasons.settingsMarkup,undefined);
const app=fs.readFileSync(require('node:path').join(__dirname,'../static/app.js'),'utf8');
assert(!app.includes('settingsMarkup'));
assert(!source.includes('Celebraciones automáticas'));
// The season module decorates fixed UI elements, never financial/message content.
assert(!source.includes('statement-preview'));
assert(!source.includes('explain-text'));
context.window.CindySeasons.apply({...config,key:'base',active:false});
assert.equal(document.body.dataset.season,'base');
assert(nodes.get('#header-garland').innerHTML.includes('data-motif="star"'));assert(nodes.get('#header-garland').innerHTML.includes('data-motif="moon"'));assert(!nodes.get('#header-garland').innerHTML.includes('data-motif="pumpkin"'));
assert.equal(nodes.get('#season-ornaments').innerHTML,'');
context.window.CindySeasons.apply(config);
assert.equal(document.body.dataset.season,'halloween');
assert(nodes.get('#season-ornaments').innerHTML.includes('<svg'));
console.log('Seasonal countdown, yearly composition, stable continuous finale and internal-only decoration, hidden calendar and base-theme reset passed.');


// Exercise the real welcome lifecycle with a DOM model: no child event can cut it short.
function runtime(season,{brokenLogo=false,waitingLogo=false,reduced=false}={}){
 const map=new Map(),timers=new Map();let nextTimer=0;
 function element(){
  const classes=new Set(),events=new Map(),styles=new Map();
  return {dataset:{},innerHTML:'',textContent:'',complete:true,naturalWidth:brokenLogo?0:240,
   decode:()=>Promise.resolve(),styles,events,
   style:{setProperty:(key,value)=>styles.set(key,value)},
   classList:{add:c=>classes.add(c),remove:c=>classes.delete(c),contains:c=>classes.has(c),toggle(c,force){if(force)classes.add(c);else classes.delete(c);}},
   addEventListener:(name,fn)=>events.set(name,fn),removeEventListener:name=>events.delete(name),pause(){},play:()=>Promise.resolve()};
 }
 for(const selector of ['#header-garland','#shell','#panel-welcome','#panel-welcome-logo','.panel-welcome-motifs','.panel-welcome-glitter','.panel-welcome-greeting','#season-banner','.season-banner-title','.season-banner-greeting','.season-banner-motif','.welcome-season-greeting','#season-ornaments','.welcome-glitter'])map.set(selector,element());
 map.get('#panel-welcome').classList.add('hidden');
 if(waitingLogo)map.get('#panel-welcome-logo').complete=false;
 const doc={body:{dataset:{seasonConfig:JSON.stringify(season)}},hidden:false,querySelector:s=>map.get(s)||null,querySelectorAll:()=>[],addEventListener(){}};
 const ctx={window:{},document:doc,matchMedia:()=>({matches:reduced}),setInterval(){},setTimeout(fn,ms){timers.set(++nextTimer,{fn,ms});return nextTimer;},clearTimeout:id=>timers.delete(id),Intl,Date,encodeURIComponent};
 vm.runInNewContext(source,ctx);
 return {map,timers,api:ctx.window.CindySeasons};
}
(async()=>{
 for(const [key,motifs] of Object.entries({halloween:['pumpkin','bat','ghost'],christmas:['tree','gift','snow'],birthday:['cake','teddy','balloon'],mother:['flower','heart'],newyear:['firework','clock']})){
  const r=runtime({...config,key});
  await r.api.welcome();
  const overlay=r.map.get('#panel-welcome'),marks=r.map.get('.panel-welcome-motifs');
  assert(!overlay.classList.contains('hidden'));
  for(const motif of motifs)assert(marks.innerHTML.includes('data-motif="'+motif+'"'),key+': '+motif);
  assert.equal(r.map.get('.panel-welcome-glitter').innerHTML.match(/<i /g).length,32);
  const primary=decodeURIComponent(r.map.get('#shell').styles.get('--season-primary'));
  assert(primary.includes('data-motif="'+motifs[0]+'"'));assert(primary.includes('#9b7838'));
  for(const motif of motifs)assert(r.map.get('#header-garland').innerHTML.includes('data-motif="'+motif+'"'));
  const originalMarks=marks.innerHTML;
  await r.api.welcome();assert.equal(marks.innerHTML,originalMarks);
  const ended=overlay.events.get('animationend');
  ended({target:marks,animationName:'cindy-panel-reveal'});assert(!overlay.classList.contains('hidden'));
  ended({target:overlay,animationName:'cindy-panel-reveal'});assert(overlay.classList.contains('hidden'));
  assert.equal(marks.innerHTML,'');assert.equal(r.map.get('.panel-welcome-glitter').innerHTML,'');
  assert(![...r.timers.values()].some(t=>t.ms===3800));
 }
 const fallback=runtime(config);await fallback.api.welcome();
 [...fallback.timers.values()].find(t=>t.ms===3800).fn();assert(fallback.map.get('#panel-welcome').classList.contains('hidden'));
 for(const opts of [{brokenLogo:true},{waitingLogo:true}]){const r=runtime(config,opts);await r.api.welcome();assert(r.map.get('#panel-welcome').classList.contains('hidden'));}
 const base=runtime({...config,key:'base',active:false});await base.api.welcome();
 assert(!base.map.get('.panel-welcome-motifs').innerHTML.includes('pumpkin'));
 assert.equal(base.map.get('.panel-welcome-greeting').textContent,'');
 const reduced=runtime(config,{reduced:true});await reduced.api.welcome();assert(!reduced.map.get('#panel-welcome').classList.contains('hidden'));
 // Run the actual session-entry function: returning sessions only, after data is ready.
 const entry=app.slice(app.indexOf('let firstSessionCheck=true;'),app.indexOf("$('#login-form').onsubmit"));
 async function sessionFlow(authenticated){
  let session={authenticated},welcomes=0,authScreens=0,refreshes=0;
  const ctx={api:async()=>session,CindyCalm:{start(){}},CindySeasons:{apply(){},welcome(){assert(refreshes>0);welcomes++;}},$:()=>({pause(){},classList:{add(){},remove(){}}}),refresh:async()=>{refreshes++;},showAuth(){authScreens++;},S:{demo:false},csrf:''};
  vm.runInNewContext(entry,ctx);await ctx.start();
  const first=welcomes;
  session={authenticated:true};await ctx.start();
  return {first,welcomes,authScreens};
 }
 assert.deepEqual(await sessionFlow(true),{first:1,welcomes:1,authScreens:0});
 assert.deepEqual(await sessionFlow(false),{first:0,welcomes:0,authScreens:1});
 const css=fs.readFileSync(require('node:path').join(__dirname,'../static/seasons.css'),'utf8');
 const envelope=css.slice(css.indexOf('@keyframes cindy-panel-reveal'),css.indexOf('@keyframes cindy-panel-logo'));
 assert(envelope.includes('0%{opacity:0}'));assert(envelope.includes('100%{opacity:0}'));
 assert(css.includes('.panel-welcome.is-playing{animation-duration:1.6s}'));
 assert(css.includes('#panel-welcome,#season-banner'));
 console.log('Returning-session welcome: all festivities, one-time entry, nested events, fallback, logo failures, reduced motion and fade endpoints passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});


