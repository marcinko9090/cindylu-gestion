/* First presentation soundtrack, with attenuated metallic highs. */
(function(){
 'use strict';
 const scene=document.querySelector('.intro-scene'),burst=document.querySelector('.intro-burst');
 if(!scene||!burst)return;
 let seed=1977;const random=()=>{seed=(seed*16807)%2147483647;return(seed-1)/2147483646};
 burst.innerHTML=Array.from({length:96},(_,i)=>{
  const angle=i/96*Math.PI*2,spread=.35+random()*.7;
  return '<i style="--dx:'+Math.cos(angle)*spread+';--dy:'+Math.sin(angle)*spread+';--size:'+(3+random()*4.5)+'px;--delay:'+(random()*.42)+'s"></i>';
 }).join('');
 // Reuse the first presentation's actual soundtrack with softened metallic highs.
 let context=null,track=null,enabled=false,generation=0;
 const button=document.querySelector('#intro-sound');
 const visible=()=>!document.hidden&&!document.querySelector('#auth').classList.contains('hidden');
 function silence(){generation++;if(track){track.pause();track.currentTime=0;}}
 async function play(){
  if(!enabled||!visible())return;
  const ticket=++generation;
  try{
   if(!context){
    const AudioContext=window.AudioContext||window.webkitAudioContext;
    context=new AudioContext();
    track=new Audio('/static/presentacion.mp4');track.preload='none';track.volume=.65;
    const source=context.createMediaElementSource(track);
    const shelf=context.createBiquadFilter();shelf.type='highshelf';shelf.frequency.value=1300;shelf.gain.value=-24;
    const low=context.createBiquadFilter();low.type='lowpass';low.frequency.value=1800;low.Q.value=.5;
    source.connect(shelf);shelf.connect(low);low.connect(context.destination);
   }
   await context.resume();
   if(ticket!==generation||!enabled||!visible())return;
   track.currentTime=0;await track.play();
  }catch{enabled=false;silence();button.textContent='Reintentar sonido';button.setAttribute('aria-pressed','false');}
 }
 if(button)button.onclick=async()=>{
  enabled=!enabled;button.textContent=enabled?'Silenciar':'Activar sonido';button.setAttribute('aria-pressed',String(enabled));
  if(enabled)await play();else silence();
 };
 scene.querySelector('.intro-brand').addEventListener('animationiteration',()=>{if(enabled)play()});
 document.addEventListener('visibilitychange',()=>{if(document.hidden)silence()});
 window.CindyIntro={start(){if(enabled)play()},stop(){silence();enabled=false;if(button){button.textContent='Activar sonido';button.setAttribute('aria-pressed','false')}}};
})();
