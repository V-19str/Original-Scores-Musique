/* Halo du hero : une bulle lumineuse unique qui se déforme vers le pointeur.
   Canvas 2D, rendu additif, sans dépendance. Se met en pause hors écran / onglet masqué. */
(function(){
  var hero=document.querySelector('#view-accueil .hero')||document.querySelector('.hero');
  var cvs=document.getElementById('hero-waves');
  if(!hero||!cvs)return;
  var ctx=cvs.getContext('2d');
  var reduce=window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches;
  var W=0,H=0,dpr=1,running=false,visible=true,raf=0;
  var mouse={x:.5,y:.5,tx:.5,ty:.5,power:0,tpower:0};
  function resize(){
    var r=hero.getBoundingClientRect();
    dpr=Math.min(window.devicePixelRatio||1,2);
    W=Math.max(1,r.width);H=Math.max(1,r.height);
    cvs.width=W*dpr;cvs.height=H*dpr;
    ctx.setTransform(dpr,0,0,dpr,0,0);
  }
  function setPointer(e){
    var r=hero.getBoundingClientRect();
    mouse.tx=(e.clientX-r.left)/r.width;
    mouse.ty=(e.clientY-r.top)/r.height;
    mouse.tpower=1;
  }
  hero.addEventListener('pointermove',setPointer,{passive:true});
  hero.addEventListener('pointerdown',setPointer,{passive:true});
  hero.addEventListener('pointerleave',function(){mouse.tpower=0;},{passive:true});
  function draw(t){
    raf=0;
    if(!running)return;
    t=t/1000;
    mouse.x+=(mouse.tx-mouse.x)*.06;
    mouse.y+=(mouse.ty-mouse.y)*.06;
    mouse.power+=(mouse.tpower-mouse.power)*.05;
    ctx.clearRect(0,0,W,H);
    // une seule bulle, centrée, qui se penche vers le pointeur
    var base=Math.min(W,H)*(W<700?.40:.34);
    var cx=W/2+(mouse.x-.5)*W*.10*mouse.power;
    var cy=H*.46+(mouse.y-.5)*H*.10*mouse.power;
    var N=120,pts=[];
    for(var i=0;i<N;i++){
      var a=i/N*Math.PI*2;
      var da=Math.atan2(Math.sin(a-Math.atan2(mouse.y*H-cy,mouse.x*W-cx)),Math.cos(a-Math.atan2(mouse.y*H-cy,mouse.x*W-cx)));
      var bulge=Math.exp(-da*da*2.2)*mouse.power*.09;   // gonfle côté pointeur
      var r=base*(1+.018*Math.sin(a*2+t*.9)+.014*Math.sin(a*3-t*.7)+bulge+.012*Math.sin(t*.6));
      pts.push(cx+Math.cos(a)*r,cy+Math.sin(a)*r);
    }
    function path(){ctx.beginPath();ctx.moveTo(pts[0],pts[1]);for(var k=2;k<pts.length;k+=2)ctx.lineTo(pts[k],pts[k+1]);ctx.closePath();}
    ctx.globalCompositeOperation='lighter';
    var g=ctx.createLinearGradient(cx-base,cy-base,cx+base,cy+base);
    g.addColorStop(0,'rgba(255,150,40,1)');g.addColorStop(.5,'rgba(255,85,0,1)');g.addColorStop(1,'rgba(229,57,53,1)');
    // halo diffus, puis anneau net
    var passes=[[base*.22,.05],[base*.10,.09],[base*.04,.22],[3,.95]];
    for(var p=0;p<passes.length;p++){
      path();ctx.strokeStyle=g;ctx.globalAlpha=Math.min(1,passes[p][1]*(.85+.3*mouse.power));
      ctx.lineWidth=passes[p][0];ctx.stroke();
    }
    ctx.globalAlpha=1;
    // léger reflet intérieur
    var rg=ctx.createRadialGradient(cx,cy,base*.55,cx,cy,base);
    rg.addColorStop(0,'rgba(255,85,0,0)');rg.addColorStop(1,'rgba(255,85,0,.10)');
    path();ctx.fillStyle=rg;ctx.fill();
    ctx.globalCompositeOperation='source-over';
    raf=requestAnimationFrame(draw);
  }
  function start(){ if(running||reduce&&false)return; running=true; if(!raf)raf=requestAnimationFrame(draw); }
  function stop(){ running=false; if(raf){cancelAnimationFrame(raf);raf=0;} }
  function sync(){ (visible&&!document.hidden)?start():stop(); }
  document.addEventListener('visibilitychange',sync);
  if('IntersectionObserver' in window){
    new IntersectionObserver(function(es){visible=es[0].isIntersecting;sync();},{threshold:0}).observe(hero);
  }
  window.addEventListener('resize',resize);
  resize();
  if(reduce){ // une seule image fixe, sans animation
    mouse.power=0;running=true;draw(0);running=false;
  }else sync();
})();
