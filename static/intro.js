/* Warm original major-key melody, without bells or metallic overtones. */
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
   // A warm, lightly plucked major melody with a soft accompanying chord.
   const notes=[
    [261.63,0,.75,.026],[329.63,0,.75,.018],[392,0,.75,.016],
    [523.25,.08,.48,.045],[659.25,.36,.48,.043],[783.99,.64,.62,.040],
    [659.25,1.08,.44,.040],[698.46,1.36,.44,.038],[783.99,1.64,.56,.040],
    [349.23,1.36,.8,.020],[440,1.36,.8,.015],
    [659.25,2.12,.45,.040],[587.33,2.40,.45,.037],
    [523.25,2.72,1.25,.043],[261.63,2.72,1.25,.025],[329.63,2.72,1.25,.018],[392,2.72,1.25,.016]
   ];
   notes.forEach(([frequency,offset,length,volume])=>{
    const start=now+offset;
    // Low integer harmonics give a rounded keyboard tone, not a bell.
    [1,2,3].forEach((ratio,j)=>{
     const oscillator=audio.createOscillator(),gain=audio.createGain();
     oscillator.type='sine';oscillator.frequency.value=frequency*ratio;
     gain.gain.setValueAtTime(0,start);
     gain.gain.linearRampToValueAtTime(volume*[1,.16,.04][j],start+.028);
     gain.gain.exponentialRampToValueAtTime(.0001,start+length);
     oscillator.connect(gain);gain.connect(audio.destination);
     oscillator.start(start);oscillator.stop(start+length+.04);
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
