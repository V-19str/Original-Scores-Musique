/* Halo lumineux du hero : des ondes lumineuses qui se déforment autour du pointeur.
   Canvas 2D, rendu additif, sans dépendance. Se met en pause hors écran / onglet masqué. */
(function(){
  var hero=document.querySelector('#view-accueil .hero')||document.querySelector('.hero');
  var cvs=document.getElementById('hero-waves');
  if(!hero||!cvs)return;
  var ctx=cvs.getContext('2d');
  var reduce=window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches;
  var W=0,H=0,dpr=1,running=false,visible=true,raf=0;
  var mouse={x:.5,y:.5,tx:.5,ty:.5,power:0,tpower:0};
  var LINES=[
    {y:.30,amp:.11,freq:1.3,speed:.35,hue:'255,85,0',  w:2.2},
    {y:.55,amp:.14,freq:1.0,speed:-.28,hue:'229,57,53', w:2.6},
    {y:.78,amp:.10,freq:1.6,speed:.42,hue:'255,150,40',w:1.8}
  ];
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
    // lissage du pointeur : l'onde « suit » avec de l'inertie
    mouse.x+=(mouse.tx-mouse.x)*.08;
    mouse.y+=(mouse.ty-mouse.y)*.08;
    mouse.power+=(mouse.tpower-mouse.power)*.05;
    ctx.clearRect(0,0,W,H);
    ctx.globalCompositeOperation='lighter';
    ctx.lineCap='round';ctx.lineJoin='round';
    var step=Math.max(6,Math.round(W/160));
    for(var li=0;li<LINES.length;li++){
      var L=LINES[li];
      var baseY=L.y*H;
      // la ligne est attirée vers la hauteur du pointeur
      var pull=mouse.power*.45;
      var cy=baseY+(mouse.y*H-baseY)*pull*Math.exp(-Math.pow((L.y-mouse.y)*2.2,2));
      var pts=[];
      for(var x=-step;x<=W+step;x+=step){
        var nx=x/W;
        var d=nx-mouse.x;
        var env=Math.exp(-d*d*9)*mouse.power;           // bosse gaussienne autour du pointeur
        var f=L.freq*(1+env*1.6);                         // l'onde se resserre près du pointeur
        var a=L.amp*H*(1+env*1.5);                        // et gonfle
        var ph=t*L.speed*Math.PI*2+li*1.7+d*env*6;        // phase décalée = la forme « glisse »
        var y=cy+Math.sin(nx*Math.PI*2*f+ph)*a
                 +Math.sin(nx*Math.PI*2*f*2.3-ph*.7)*a*.22;
        pts.push(x,y);
      }
      // halo large puis trait fin lumineux
      var passes=[[L.w*14,.05],[L.w*6,.10],[L.w*2.4,.35],[L.w,.95]];
      for(var p=0;p<passes.length;p++){
        ctx.beginPath();
        ctx.moveTo(pts[0],pts[1]);
        for(var i=2;i<pts.length;i+=2)ctx.lineTo(pts[i],pts[i+1]);
        ctx.strokeStyle='rgba('+L.hue+','+(passes[p][1]*(.75+.25*mouse.power))+')';
        ctx.lineWidth=passes[p][0];
        ctx.stroke();
      }
    }
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
