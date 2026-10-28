/* Original synthesized crystal chime. No recording or old video soundtrack. */
(function(){
 'use strict';
 const scene=document.querySelector('.intro-scene'),burst=document.querySelector('.intro-burst');
 if(!scene||!burst)return;
 let seed=1977;const random=()=>{seed=(seed*16807)%2147483647;return(seed-1)/2147483646};
 burst.innerHTML=Array.from({length:64},(_,i)=>{
  const angle=i/64*Math.PI*2,spread=.35+random()*.7;
  return '<i style="--dx:'+Math.cos(angle)*spread+';--dy:'+Math.sin(angle)*spread+';--size:'+(2+random()*3.5)+'px;--delay:'+(random()*.42)+'s"></i>';
 }).join('');
 let audio=null,enabled=false,generation=0;
 const button=document.querySelector('#intro-sound');
 const visible=()=>!document.hidden&&!document.querySelector('#auth').classList.contains('hidden');
 function silence(){generation++;if(audio){const old=audio;audio=null;old.close().catch(()=>{});}}
 async function chime(){
  if(!enabled||!visible())return;
  const ticket=++generation;
  try{
   const Audio=window.AudioContext||window.webkitAudioContext;
   if(!Audio)throw Error('unsupported');
   if(!audio)audio=new Audio();
   await audio.resume();
   if(ticket!==generation||!enabled||!visible())return;
   const now=audio.currentTime+.03;
   [783.99,1046.5,1318.51,1567.98].forEach((frequency,i)=>{
    const start=now+i*.16;
    [1,2.003].forEach((ratio,j)=>{
     const oscillator=audio.createOscillator(),gain=audio.createGain();
     oscillator.type='sine';oscillator.frequency.value=frequency*ratio;
     gain.gain.setValueAtTime(0,start);
     gain.gain.linearRampToValueAtTime(j?.009:.035,start+.018);
     gain.gain.exponentialRampToValueAtTime(.0001,start+2.5);
     oscillator.connect(gain);gain.connect(audio.destination);
     oscillator.start(start);oscillator.stop(start+2.6);
     oscillator.onended=()=>{oscillator.disconnect();gain.disconnect();};
    });
   });
  }catch{enabled=false;button.textContent='Sonido no disponible';button.setAttribute('aria-pressed','false');}
 }
 if(button)button.onclick=async()=>{
  enabled=!enabled;button.textContent=enabled?'Silenciar':'Activar sonido';button.setAttribute('aria-pressed',String(enabled));
  if(enabled)await chime();else silence();
 };
 scene.querySelector('.intro-brand').addEventListener('animationiteration',()=>{if(enabled)chime()});
 document.addEventListener('visibilitychange',()=>{if(document.hidden)silence()});
 window.CindyIntro={start(){if(enabled)chime()},stop(){silence();enabled=false;if(button){button.textContent='Activar sonido';button.setAttribute('aria-pressed','false')}}};
})();
