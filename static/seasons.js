/* Recurring, restrained seasonal decorations. Beige and gold remain permanent. */
(function(){
 'use strict';
 const $=s=>document.querySelector(s);
 const reduced=()=>matchMedia('(prefers-reduced-motion: reduce)').matches;
 const shapes={
  pumpkin:'<path d="M30 18c-2-7 1-11 7-12l-1 7m-6 5c-4-7-10-6-12-3"/><path d="M32 19C21 10 7 19 7 35c0 16 13 23 25 18 12 5 25-2 25-18 0-16-14-25-25-16Z" fill="currentColor" fill-opacity=".08"/><path d="M23 20c-8 9-8 23 0 30m18-30c8 9 8 23 0 30M32 19v7m0 21v6" opacity=".6"/><path d="m17 33 7-7 3 8Zm20 1 3-8 7 7ZM30 37l2-4 2 4Z" fill="currentColor"/><path d="m16 40 8 3 1-3 7 4 7-4 1 3 8-3c-5 12-27 12-32 0Z" fill="currentColor" fill-opacity=".75"/>',
  moon:'<path d="M44 9a24 24 0 1 0 11 37A24 24 0 0 1 44 9Z" fill="currentColor" fill-opacity=".07"/><path d="m17 8 2 5 5 2-5 2-2 5-2-5-5-2 5-2Zm30 15 1 3 3 1-3 1-1 3-1-3-3-1 3-1Z"/>',
  star:'<path d="m32 7 6 17 18 1-14 12 5 19-15-11-15 11 5-19L8 25l18-1Z"/><path d="m32 20 3 9 10 1-8 6 2 10-7-6-7 6 2-10-8-6 10-1Z" opacity=".4"/>',
  ghost:'<path d="M16 31c0-13 6-21 16-21s17 9 17 21c0 8 4 14 9 18-6 5-10 2-14 0-4 9-9 9-13 2-5 8-10 8-14 0-4 3-9 4-12 0 7-5 11-12 11-20Z" fill="currentColor" fill-opacity=".07"/><ellipse cx="26" cy="28" rx="2.5" ry="4" fill="currentColor"/><ellipse cx="39" cy="28" rx="2.5" ry="4" fill="currentColor"/><ellipse cx="32" cy="38" rx="3" ry="4"/><path d="m20 35 3 1m20-1-3 1M16 38l6-2m27 2-6-2"/>',
  bat:'<path d="m28 26-2-8 6 4 6-4-2 8C45 19 53 17 60 15c-5 7-6 13-4 20-7-2-10 1-12 7-5-4-8-3-12 6-4-9-7-10-12-6-2-6-5-9-12-7 2-7 1-13-4-20 7 2 15 4 24 11Z" fill="currentColor" fill-opacity=".18"/><path d="M32 29v14m-4-12h1m6 0h1M27 28 12 22m25 6 15-6"/>',
  tree:'<path d="m32 3 2 5 6 1-5 4 1 6-4-3-4 3 1-6-5-4 6-1Z"/><path d="m27 20-9 10h7L13 43h10L9 55h46L41 43h10L39 30h7L37 20M28 55v6h8v-6"/><path d="m22 34 20 10m-19 2 16 6"/><circle cx="32" cy="27" r="2"/><circle cx="24" cy="42" r="2"/><circle cx="39" cy="49" r="2"/>',
  gift:'<rect x="10" y="27" width="44" height="10" rx="2"/><path d="M14 37v21h36V37M28 27v31m8-31v31"/><path d="M32 26C8 26 13 5 24 13c5 3 7 8 8 13Zm0 0C56 26 51 5 40 13c-5 3-7 8-8 13Z"/>',
  snow:'<path d="M32 6v52M9 19l46 26M9 45l46-26M26 10l6 7 6-7M26 54l6-7 6 7M11 26l9-2-1-10M53 38l-9 2 1 10M11 38l9 2-1 10M53 26l-9-2 1-10"/>',
  teddy:'<circle cx="18" cy="16" r="8"/><circle cx="46" cy="16" r="8"/><circle cx="18" cy="16" r="3"/><circle cx="46" cy="16" r="3"/><circle cx="32" cy="27" r="19"/><ellipse cx="32" cy="52" rx="17" ry="10"/><ellipse cx="32" cy="34" rx="9" ry="6"/><circle cx="24" cy="25" r="1.5" fill="currentColor"/><circle cx="40" cy="25" r="1.5" fill="currentColor"/><path d="m29 31 3 3 3-3Zm3 3v3m-4 0q4 3 8 0M26 49l6 4 6-4"/>',
  cake:'<path d="M10 38h44v20H10ZM16 27h32v11M8 58h48M22 27v-7m10 7v-7m10 7v-7M10 44q6 8 11 0 6 8 11 0 6 8 11 0 6 8 11 0"/><path d="M22 16c-7-4 0-9 0-9s7 5 0 9Zm10 0c-7-4 0-9 0-9s7 5 0 9Zm10 0c-7-4 0-9 0-9s7 5 0 9Z" fill="currentColor" fill-opacity=".15"/>',
  bow:'<path d="M28 29C13 5 2 23 11 33c5 5 12 2 17-1m8-3C51 5 62 23 53 33c-5 5-12 2-17-1"/><rect x="27" y="25" width="10" height="11" rx="3"/><path d="m29 36-9 20 10-5 3 7 2-22m2 0 9 20-9-6M16 24l11 6m21-6-11 6"/>',
  balloon:'<ellipse cx="32" cy="23" rx="17" ry="20"/><path d="m32 43-4 6h8Zm0 6c-10 5 9 6 0 12M23 13c-4 3-5 5-5 9M41 14q4 7 2 12"/>',
  heart:'<path d="M32 53C-8 28 10-1 32 18 54-1 72 28 32 53Z" fill="currentColor" fill-opacity=".06"/><path d="M13 24q0-9 10-7M42 39l-10 8"/>',
  flower:'<path d="M32 29C9 18 21 0 32 18 43 0 55 18 35 29 59 20 68 40 44 40 63 54 45 67 34 45 32 69 11 64 22 43-2 52-2 30 22 31 3 14 20 4 32 29Z"/><circle cx="32" cy="34" r="7"/><circle cx="32" cy="34" r="2"/><path d="m23 23 4 5m14-6-5 6m10 8-7-1M22 46l5-6m9 7-2-7" opacity=".55"/>',
  firework:'<circle cx="32" cy="30" r="5"/><path d="M32 7v12m0 22v12M9 30h12m22 0h12M15 13l9 9m16 16 9 9M15 47l9-9m16-16 9-9M32 2v1m0 54v2M4 30h1m54 0h1M9 7l2 2m42 42 2 2M9 53l2-2M53 9l2-2"/><path d="m23 9 2 6m14 30 2 6M11 39l6-2m30-14 6-2M11 21l6 2m30 14 6 2M23 51l2-6M39 15l2-6" opacity=".65"/>',
  clock:'<circle cx="32" cy="32" r="25"/><circle cx="32" cy="32" r="20"/><path d="M32 15v4m0 26v4M15 32h4m26 0h4M32 32V21m0 11 8-13m-22 0 2 2m24-2-2 2M18 45l2-2m24 2-2-2"/><circle cx="32" cy="32" r="2" fill="currentColor"/>',
  pearl:'<circle cx="32" cy="32" r="20"/><path d="m32 17 4 11 11 4-11 4-4 11-4-11-11-4 11-4Z"/>'
 };
 const palettes={base:['star','pearl'],halloween:['pumpkin','bat','ghost','moon'],christmas:['tree','gift','snow','star','bow'],birthday:['cake','teddy','balloon','bow','star'],mother:['flower','heart','bow','pearl'],newyear:['firework','clock','star','bow']};
 function svg(name){return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" data-motif="'+name+'" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'+(shapes[name]||shapes.star)+'</svg>';}
 function iconUrl(name){return 'url("data:image/svg+xml,'+encodeURIComponent(svg(name).replaceAll('currentColor','#9b7838'))+'")';}
 function random(seed){let n=seed||1;return ()=>{n=(n*16807)%2147483647;return (n-1)/2147483646;};}
 function garlandMarkup(config,motifs,id='header-gold-wire',count=9){
  const names=config.active?motifs:['star','moon'],rng=random(config.seed+523);
  const wire='<svg class="header-garland-wire" viewBox="0 0 1200 60" preserveAspectRatio="none" aria-hidden="true"><defs><linearGradient id="header-gold-wire"><stop stop-color="#9b7130"/><stop offset=".27" stop-color="#e5c97b"/><stop offset=".53" stop-color="#aa7d2d"/><stop offset=".78" stop-color="#e1c16a"/><stop offset="1" stop-color="#a07730"/></linearGradient></defs><path d="M0 8Q120 44 240 8Q360 44 480 8Q600 44 720 8Q840 44 960 8Q1080 44 1200 8" fill="none" stroke="url(#header-gold-wire)" stroke-width="1.7"/><path d="M0 11Q120 47 240 11Q360 47 480 11Q600 47 720 11Q840 47 960 11Q1080 47 1200 11" fill="none" stroke="#d8bd7f" stroke-opacity=".42" stroke-width=".65"/></svg>';
  return (wire+Array.from({length:count},(_,i)=>{
   const x=count===9?5.5+i*11.125:8+i*21;const t=((x/100*1200)%240)/240,y=8+72*t*(1-t);
   const size=26+Math.round(rng()*7),drop=6+Math.round(rng()*6),tilt=-3+rng()*6;
   return '<span class="header-garland-hanger" style="--x:'+x+'%;--y:'+y+'px;--charm-size:'+size+'px;--drop:'+drop+'px;--tilt:'+tilt+'deg;--delay:'+(-rng()*14)+'s"><span class="header-garland-thread"></span><span class="header-garland-charm">'+svg(names[(i+config.variant)%names.length])+'</span></span>';
  }).join('')).replaceAll('header-gold-wire',id);
 }
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
  const garland=$('#header-garland');if(garland)garland.innerHTML=garlandMarkup(config,motifs);
  const bannerGarland=$('#banner-garland');if(bannerGarland)bannerGarland.innerHTML=garlandMarkup(config,motifs,'banner-gold-wire',5);
  const shell=$('#shell');
  if(shell){
   shell.style.setProperty('--season-primary',iconUrl(motifs[0]));
   shell.style.setProperty('--season-secondary',iconUrl(motifs[1]||motifs[0]));
   shell.style.setProperty('--season-tertiary',iconUrl(motifs[2]||motifs[0]));
  }
  const ornaments=$('#season-ornaments');if(ornaments)ornaments.innerHTML=config.active?Array.from({length:4},(_,i)=>'<span class="season-ornament" style="--x:'+(i%2?94:3)+'%;--y:'+(14+i*23)+'%;--size:'+(34+rng()*24)+'px;--tilt:'+(-12+rng()*24)+'deg">'+svg(motifs[(i+config.variant)%motifs.length])+'</span>').join(''):'';
  const glitter=$('.welcome-glitter');if(glitter){
   const particles=Array.from({length:28},()=>'<i style="--x:'+(rng()*100)+'%;--y:'+(rng()*100)+'%;--size:'+(1+rng()*3)+'px;--drift:'+(-22+rng()*44)+'px;--duration:'+(7+rng()*8)+'s;--delay:'+(-rng()*15)+'s"></i>').join('');
   const marks=Array.from({length:config.active?5:2},(_,i)=>'<span class="welcome-motif" style="--x:'+(9+rng()*80)+'%;--y:'+(9+rng()*78)+'%;--size:'+(24+rng()*25)+'px;--tilt:'+(-18+rng()*36)+'deg">'+svg(motifs[(i+config.variant)%motifs.length])+'</span>').join('');
   glitter.innerHTML=particles+marks;
  }
 }
 // Calendar rules stay internal; no configuration panel is rendered.
 let welcomePlayed=false;
 async function welcome(){
  const overlay=$('#panel-welcome');
  if(welcomePlayed||!overlay||!current)return;
  welcomePlayed=true;
  const logo=$('#panel-welcome-logo');
  // Decode before revealing so a slow image never pops into a fading animation.
  if(logo?.decode){try{await Promise.race([logo.decode(),new Promise(resolve=>setTimeout(resolve,600))]);}catch{}}
  // Always show entry glitter; a slow or failed logo uses the store-name fallback.
  overlay.classList.toggle('logo-fallback',!!(logo&&(!logo.complete||!logo.naturalWidth)));
  const config=current,rng=random(config.seed+97),motifs=palettes[config.key]||palettes.base;
  const marks=$('.panel-welcome-motifs'),particles=$('.panel-welcome-glitter');
  if(marks)marks.innerHTML=Array.from({length:config.active?6:3},(_,i)=>'<span class="panel-welcome-motif" style="--x:'+([19,76,13,81,28,67][i])+'%;--y:'+([25,26,61,63,79,80][i])+'%;--size:'+(32+rng()*22)+'px;--tilt:'+(-12+rng()*24)+'deg;--drift:'+(-8+rng()*16)+'px">'+svg(motifs[i%motifs.length])+'</span>').join('');
  if(particles)particles.innerHTML=Array.from({length:32},()=>'<i style="--x:'+(12+rng()*76)+'%;--y:'+(14+rng()*72)+'%;--size:'+(1+rng()*3)+'px;--drift:'+(-22+rng()*44)+'px;--delay:'+(-rng()*7)+'s"></i>').join('');
  const greeting=$('.panel-welcome-greeting');if(greeting)greeting.textContent=config.active?config.greeting:'';
  let fallback;
  const finish=()=>{overlay.classList.add('hidden');overlay.classList.remove('is-playing');overlay.classList.remove('logo-fallback');if(marks)marks.innerHTML='';if(particles)particles.innerHTML='';overlay.removeEventListener('animationend',ended);clearTimeout(fallback);};
  const ended=event=>{if(event.target===overlay&&event.animationName==='cindy-panel-reveal')finish();};
  overlay.addEventListener('animationend',ended);
  overlay.classList.remove('hidden');overlay.classList.add('is-playing');
  // Cleanup occurs after the envelope reaches zero opacity; never at a child particle's end.
  fallback=setTimeout(finish,3800);
 }
 window.CindySeasons={apply,welcome};
 try{apply(JSON.parse(document.body.dataset.seasonConfig||'null'));}catch{}
 const video=$('#welcome-video'),film=$('.auth-film');
 if(video&&film){
  // Keep the original full presentation playing on every loop. Never replace it at 2.9s.
  const reveal=()=>{film.dataset.phase='brand';};
  const playing=()=>{if(!reduced())film.dataset.phase='intro';};
  video.loop=true;
  video.addEventListener('playing',playing);
  video.addEventListener('timeupdate',()=>{if(video.currentTime>.1&&!video.paused)playing();});
  video.addEventListener('error',reveal);
  if(reduced()){video.autoplay=false;video.pause();reveal();}
  else video.play().catch(reveal);
  // The animated logo is a fallback only while playback is unavailable.
  setTimeout(()=>{if(reduced()||video.paused||video.currentTime<.1)reveal();},4200);
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



