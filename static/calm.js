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
 const PERIOD=5*60*1000,IDLE=60000,KEY='cindy-calm-daily-v1';

 // Each complete message has a persistent index; the catalogue never loops.
 const endings=[
 'Tu dedicación merece también momentos de descanso.',
 'Puedes elegir solo el siguiente paso.',
 'No tienes que demostrar nada en este instante.',
 'Lo que queda pendiente puede esperar su momento.',
 'Un día difícil no borra lo que has construido.',
 'Hay valor en intentarlo con amabilidad.',
 'Puedes reconocer lo que hiciste, aunque sea pequeño.',
 'Darte espacio también es cuidar tu trabajo.',
 'No necesitas compararte con el ritmo de nadie.',
 'Tu valor va más allá de una lista de tareas.',
 'Puedes hacer una pausa sin tener que ganártela.',
 'Hoy puedes hablarte con la misma ternura que a alguien querido.',
 'El esfuerzo silencioso también merece reconocimiento.',
 'A veces avanzar es simplificar lo que tienes delante.',
 'Puedes cambiar de ritmo cuando lo necesites.',
 'No todo necesita una respuesta inmediata.',
 'Cuidarte puede formar parte de lo que construyes.',
 'Lo sencillo también puede ser suficiente por ahora.',
 'Puedes dejar un poco de espacio entre una tarea y otra.',
 'Un resultado imperfecto no resta valor a tu dedicación.',
 'Tu camino admite pausas y nuevos comienzos.',
 'Puedes darte permiso para pedir una mano.',
 'Este momento no tiene que contener todo el día.',
 'Hay cosas que pueden hacerse de a poco.',
 'Puedes mirar con cariño el camino recorrido.',
 'El descanso también tiene un lugar en tus planes.',
 'Tu constancia no necesita convertirse en exigencia.',
 'Puedes celebrar un avance sin empezar enseguida otra tarea.',
 'La paciencia contigo también se aprende paso a paso.',
 'Puedes volver a lo importante sin reprocharte la distracción.',
 'Hacer menos hoy no borra tu esfuerzo de ayer.'
 ];
 const catalogue=endings.flatMap((_,j)=>daily.concat(pauses).map((first,i)=>first+' '+endings[(j+i)%endings.length]));
 const HISTORY='cindy-calm-used-v2';
 function nextPhrase(){
  try{
   const raw=localStorage.getItem(HISTORY);
   const index=raw===null||raw===undefined?0:Number(raw);
   if(!Number.isSafeInteger(index)||index<0||index>=catalogue.length)return '';
   // Save before display; if storage is unavailable, avoid risking repeats.
   localStorage.setItem(HISTORY,String(index+1));
   return catalogue[index];
  }catch{return '';}
 }
 function ready(){
  const shell=document.querySelector('#shell');
  return running&&!document.hidden&&!document.querySelector('dialog[open]')&&!node&&shell&&!shell.classList.contains('hidden');
 }

 const day=()=>new Intl.DateTimeFormat('en-CA',{timeZone:'America/Santiago',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
 function phrase(date){const parts=date.match(/\d+/g)||[];const n=parts.reduce((sum,v)=>sum*31+Number(v),0);return daily[n%daily.length];}
 // Only elapsed visible time near a real interaction counts; idle time never catches up.
 function elapsed(from,to,last,visible){return visible?Math.max(0,Math.min(to,last+IDLE)-from):0;}
 let running=false,lastTick=0,lastActivity=0,active=0,sequence=0,interval=null;
 let dailyTimer=null,removeTimer=null,node=null,seen='',generation=0;
 const clock=()=>performance.now();
 function clearMessage(){if(node){node.remove();node=null;}clearTimeout(removeTimer);}
 function show(text){
  if(!ready()||!text)return false;
  const shell=document.querySelector('#shell');if(!shell||shell.classList.contains('hidden'))return false;
  node=document.createElement('div');node.className='calm-message';node.setAttribute('role','status');node.setAttribute('aria-live','polite');const label=document.createElement('span');label.textContent=text;node.appendChild(label);
  const dust=document.createElement('span');dust.className='calm-dust';dust.setAttribute('aria-hidden','true');
  for(let i=0;i<12;i++){const spark=document.createElement('i');spark.style.setProperty('--i',i);dust.appendChild(spark);}node.appendChild(dust);
  document.body.appendChild(node);
  // Five seconds to read, then a two-second flight with a trailing glow.
  removeTimer=setTimeout(clearMessage,7000);
  return true;
 }
 function greet(){
  const today=day();let stored='';try{stored=localStorage.getItem(KEY)||'';}catch{}
  if(today===seen||today===stored)return;
  if(!ready()||!show(nextPhrase()))return;
  seen=today;try{localStorage.setItem(KEY,today);}catch{}
 }
 function tick(){
  if(!running)return;
  const now=clock();active+=elapsed(lastTick,now,lastActivity,!document.hidden);lastTick=now;
  if(active>=PERIOD&&ready()&&show(nextPhrase())){active%=PERIOD;}
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

