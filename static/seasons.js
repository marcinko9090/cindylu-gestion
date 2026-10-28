/* Recurring, restrained seasonal decorations. Beige and gold remain permanent. */
(function(){
 'use strict';
 const $=s=>document.querySelector(s);
 const reduced=()=>matchMedia('(prefers-reduced-motion: reduce)').matches;
 const shapes={
  pumpkin:'<path d="M31 17c-1-6 2-9 6-10M30 17c-5-5-11-1-10 3"/><ellipse cx="32" cy="36" rx="23" ry="18"/><ellipse cx="32" cy="36" rx="12" ry="18"/><path d="M32 18v36"/>',
  moon:'<path d="M44 9a24 24 0 1 0 11 37A24 24 0 0 1 44 9Z"/><path d="m17 8 2 5 5 2-5 2-2 5-2-5-5-2 5-2Z"/>',
  star:'<path d="m32 7 6 17 18 1-14 12 5 19-15-11-15 11 5-19L8 25l18-1Z"/>',
  ghost:'<path d="M15 54V28a17 17 0 0 1 34 0v26l-9-6-8 6-8-6Z"/><path d="M26 28v3m12-3v3"/>',
  tree:'<path d="m32 6-15 17h8L12 38h11L9 53h46L41 38h11L39 23h8ZM32 53v6"/><path d="m22 34 20 10M26 20l12 8"/>',
  snow:'<path d="M32 6v52M9 19l46 26M9 45l46-26M26 10l6 7 6-7M26 54l6-7 6 7M11 26l9-2-1-10M53 38l-9 2 1 10M11 38l9 2-1 10M53 26l-9-2 1-10"/>',
  teddy:'<circle cx="18" cy="16" r="8"/><circle cx="46" cy="16" r="8"/><circle cx="32" cy="27" r="19"/><ellipse cx="32" cy="52" rx="17" ry="10"/><ellipse cx="32" cy="34" rx="9" ry="6"/><path d="M24 25h1m14 0h1m-9 7h2m-1 0v4"/>',
  bow:'<path d="M28 29C13 5 2 23 11 33c5 5 12 2 17-1m8-3C51 5 62 23 53 33c-5 5-12 2-17-1"/><rect x="27" y="25" width="10" height="11" rx="3"/><path d="m29 36-9 20 10-5 3 7 2-22m2 0 9 20-9-6"/>',
  balloon:'<ellipse cx="32" cy="23" rx="17" ry="20"/><path d="m32 43-4 6h8Zm0 6c-10 5 9 6 0 12M23 13c-4 3-5 5-5 9"/>',
  heart:'<path d="M32 53C-8 28 10-1 32 18 54-1 72 28 32 53Z"/>',
  flower:'<path d="M32 29C9 18 21 0 32 18 43 0 55 18 35 29 59 20 68 40 44 40 63 54 45 67 34 45 32 69 11 64 22 43-2 52-2 30 22 31 3 14 20 4 32 29Z"/><circle cx="32" cy="34" r="7"/>',
  pearl:'<circle cx="32" cy="32" r="20"/><path d="m32 17 4 11 11 4-11 4-4 11-4-11-11-4 11-4Z"/>'
 };
 const palettes={base:['star','pearl'],halloween:['pumpkin','moon','star','ghost'],christmas:['tree','snow','star','bow'],birthday:['teddy','bow','balloon','pearl','star'],mother:['flower','heart','bow','pearl']};
 function svg(name){return '<svg viewBox="0 0 64 64" fill="none" stroke="currentColor" stroke-width="1.35" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'+(shapes[name]||shapes.star)+'</svg>';}
 function random(seed){let n=seed||1;return ()=>{n=(n*16807)%2147483647;return (n-1)/2147483646;};}
 let current=null,signature='';
 function apply(config){
  if(!config)return;
  current=config;document.body.dataset.season=config.key;document.body.dataset.seasonVariant=config.variant;
  document.querySelectorAll('[data-season-countdown]').forEach(el=>{el.textContent=config.countdown;el.classList.toggle('hidden',!config.active);});
  const banner=$('#season-banner');if(banner){banner.classList.toggle('hidden',!config.active);$('.season-banner-title').textContent=config.label;$('.season-banner-greeting').textContent=config.greeting;$('.season-banner-motif').innerHTML=svg(palettes[config.key]?.[0]||'star');}
  const greeting=$('.welcome-season-greeting');if(greeting)greeting.textContent=config.active?config.greeting:'';
  const nextSignature=config.key+':'+config.year;
  if(signature===nextSignature)return;
  signature=nextSignature;
  const rng=random(config.seed),motifs=palettes[config.key]||palettes.base;
  const ornaments=$('#season-ornaments');if(ornaments)ornaments.innerHTML=config.active?Array.from({length:4},(_,i)=>'<span class="season-ornament" style="--x:'+(i%2?94:3)+'%;--y:'+(14+i*23)+'%;--size:'+(34+rng()*24)+'px;--tilt:'+(-12+rng()*24)+'deg">'+svg(motifs[(i+config.variant)%motifs.length])+'</span>').join(''):'';
  const glitter=$('.welcome-glitter');if(glitter){
   const particles=Array.from({length:28},()=>'<i style="--x:'+(rng()*100)+'%;--y:'+(rng()*100)+'%;--size:'+(1+rng()*3)+'px;--drift:'+(-22+rng()*44)+'px;--duration:'+(7+rng()*8)+'s;--delay:'+(-rng()*15)+'s"></i>').join('');
   const marks=Array.from({length:config.active?5:2},(_,i)=>'<span class="welcome-motif" style="--x:'+(9+rng()*80)+'%;--y:'+(9+rng()*78)+'%;--size:'+(24+rng()*25)+'px;--tilt:'+(-18+rng()*36)+'deg">'+svg(motifs[(i+config.variant)%motifs.length])+'</span>').join('');
   glitter.innerHTML=particles+marks;
  }
 }
 // Calendar rules stay internal; no configuration panel is rendered.
 window.CindySeasons={apply};
 try{apply(JSON.parse(document.body.dataset.seasonConfig||'null'));}catch{}
 const video=$('#welcome-video'),film=$('.auth-film');
 if(video&&film){
  let finale=false;
  const reveal=()=>{if(finale)return;finale=true;film.dataset.phase='brand';};
  video.addEventListener('timeupdate',()=>{if(video.currentTime>=2.9)reveal();});
  video.addEventListener('error',reveal);video.addEventListener('ended',reveal);
  if(reduced()){video.autoplay=false;video.pause();reveal();}
  // If autoplay is blocked or a video stalls, the continuous web finale remains usable.
  setTimeout(reveal,4200);
  document.addEventListener('visibilitychange',()=>{if(!document.hidden&&!$('#auth')?.classList.contains('hidden')&&!reduced())video.play().catch(reveal);});
 }
 // Refresh calendar decoration for a page left open overnight, without touching account data.
 setInterval(async()=>{
  if(document.hidden||!current)return;
  const parts=new Intl.DateTimeFormat('en',{year:'numeric',month:'2-digit',day:'2-digit',timeZone:'America/Santiago'}).formatToParts(new Date());
  const value=t=>parts.find(p=>p.type===t).value;
  const day=value('year')+'-'+value('month')+'-'+value('day');
  if(day===current.date)return;
  try{const response=await fetch('/api/session');if(response.ok){const data=await response.json();apply(data.season);}}catch{}
 },60000);
})();

