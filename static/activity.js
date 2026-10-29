/* Three-hour inactivity gate; ordinary reloads preserve an active workspace. */
(function(){
 const key='cindyLastActivity',limit=3*60*60*1000;let active=false,onExpire=null,lastWrite=0;
 function saved(){try{return Number(localStorage.getItem(key))||0}catch{return lastWrite}}
 function expired(){const last=saved();return last>0&&Date.now()-last>limit}
 function mark(){const now=Date.now();if(now-lastWrite<1000)return;lastWrite=now;try{localStorage.setItem(key,String(now))}catch{}}
 function check(){if(active&&expired()){active=false;onExpire?.();return true}return false}
 function movement(){if(!active||document.hidden||check())return;mark()}
 for(const event of ['pointerdown','pointermove','keydown','scroll','touchstart'])document.addEventListener(event,movement,{passive:true});
 document.addEventListener('visibilitychange',()=>{if(!document.hidden)check()});
 window.addEventListener('focus',check);setInterval(check,30000);
 window.CindyActivity={expired,start(callback){onExpire=callback;active=true;mark()},stop(){active=false},reset(){lastWrite=0;mark()}};
})();
