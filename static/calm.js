/* Gentle, local-only encouragement for the internal workspace. */
(function(root){
 'use strict';
 const daily=[
  'Una cosa a la vez. Vas avanzando.',
  'Hoy puedes avanzar a tu propio ritmo.',
  'Un paso pequeño también cuenta.',
  'No hace falta resolver todo ahora.',
  'Tu esfuerzo de cada día tiene valor.',
  'Empieza con algo sencillo.',
  'Hay espacio para trabajar con calma.',
  'Paso a paso también se llega.',
  'Puedes darte tiempo para hacerlo bien.',
  'Hoy, lo importante puede ir primero.',
  'Cada pequeño avance construye algo.',
  'Tu ritmo también merece respeto.',
  'Puedes empezar de nuevo con calma.',
  'Una tarea a la vez es suficiente.',
  'Haz espacio para lo que sí puedes hoy.',
  'Lo que haces con cuidado tiene valor.',
  'Avanzar despacio también es avanzar.',
  'Hoy no necesitas hacerlo perfecto.',
  'Confía en el siguiente paso.',
  'Tu trabajo puede tener un ritmo amable.',
  'Estás construyendo algo, día a día.'
 ];
 const pauses=[
  'Puedes soltar los hombros un momento.',
  'Una pausa breve también cuenta.',
  'Vuelve a una sola cosa, con calma.',
  'Date un momento para respirar a tu ritmo.',
  'Ya has avanzado. Puedes ir con calma.',
  'Puedes descansar la mirada un momento.',
  'Tu bienestar también tiene un lugar aquí.'
 ];
 const PERIOD=30*60*1000,IDLE=60000,KEY='cindy-calm-daily-v1';
 const day=()=>new Intl.DateTimeFormat('en-CA',{timeZone:'America/Santiago',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
 function phrase(date){const parts=date.match(/\d+/g)||[];const n=parts.reduce((sum,v)=>sum*31+Number(v),0);return daily[n%daily.length];}
 // Only elapsed visible time near a real interaction counts; idle time never catches up.
 function elapsed(from,to,last,visible){return visible?Math.max(0,Math.min(to,last+IDLE)-from):0;}
 let running=false,lastTick=0,lastActivity=0,active=0,sequence=0,interval=null;
 let dailyTimer=null,removeTimer=null,node=null,seen='',generation=0;
 const clock=()=>performance.now();
 function clearMessage(){if(node){node.remove();node=null;}clearTimeout(removeTimer);}
 function show(text){
  if(!running||document.hidden||document.querySelector('dialog[open]')||node)return false;
  const shell=document.querySelector('#shell');if(!shell||shell.classList.contains('hidden'))return false;
  node=document.createElement('div');node.className='calm-message';node.setAttribute('role','status');node.setAttribute('aria-live','polite');node.textContent=text;
  document.body.appendChild(node);
  // The animation includes both fades and ends at exactly three seconds.
  removeTimer=setTimeout(clearMessage,3000);
  return true;
 }
 function greet(){
  const today=day();let stored='';try{stored=localStorage.getItem(KEY)||'';}catch{}
  if(today===seen||today===stored)return;
  if(!show(phrase(today)))return;
  seen=today;try{localStorage.setItem(KEY,today);}catch{}
 }
 function tick(){
  if(!running)return;
  const now=clock();active+=elapsed(lastTick,now,lastActivity,!document.hidden);lastTick=now;
  if(active>=PERIOD&&show(pauses[sequence%pauses.length])){active%=PERIOD;sequence++;}
 }
 function activity(event){
  if(!running||document.hidden||event.isTrusted===false)return;
  const now=clock();if(now-lastActivity<1000)return;
  tick();lastActivity=now;
 }
 function start(options={}){
  if(running)return;
  running=true;const token=++generation;lastTick=lastActivity=clock();active=0;
  dailyTimer=setTimeout(()=>{if(running&&token===generation)greet();},options.delay||0);
  interval=setInterval(tick,10000);
 }
 function stop(){running=false;generation++;clearInterval(interval);clearTimeout(dailyTimer);clearMessage();active=0;}
 for(const type of ['pointerdown','pointermove','keydown','scroll','wheel','touchstart'])document.addEventListener(type,activity,{passive:true,capture:true});
 document.addEventListener('visibilitychange',()=>{
  // Never accrue the hidden interval or show a delayed message on the login screen.
  lastTick=clock();if(document.hidden){clearMessage();return;}
  if(running){lastActivity=lastTick;greet();}
 });
 root.CindyCalm={start,stop,phrase,elapsed};
})(typeof window!=='undefined'?window:globalThis);
