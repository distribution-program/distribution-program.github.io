/* Button layout (per user, per PC): move, hide and group existing buttons. It never changes what a button does. */
(function(){
const SKIP=new Set(['t-back','t-menu','t-settings','lay-more']);
const KEY=()=>'dp_layout_v1:'+(S.testMode?'trial:':'work:')+S.user;
const blank=()=>({home:{order:[],hidden:[],groups:[]},bar:{order:[],hidden:[],more:[]},size:2});
function load(){try{const c=JSON.parse(localStorage.getItem(KEY())||'null');if(c&&c.home&&c.bar){c.home.order=c.home.order||[];c.home.hidden=c.home.hidden||[];c.home.groups=c.home.groups||[];c.bar.order=c.bar.order||[];c.bar.hidden=c.bar.hidden||[];c.bar.more=c.bar.more||[];c.size=(typeof c.size==='number'&&c.size>=0&&c.size<=4)?c.size:2;return c}}catch(e){}return blank()}
function save(c){try{localStorage.setItem(KEY(),JSON.stringify(c))}catch(e){}}
const lab=b=>{const n=[...b.childNodes].find(x=>x.nodeType===3&&x.textContent.trim());return (n?n.textContent:b.textContent).trim()};
const LAY={el:{},def:[],order:[]};
const BAR={el:{},def:[]};
(function(){const s=document.createElement('style');s.textContent='.lay-hide{display:none!important}#lay-more-pop{position:fixed;z-index:300;display:none;flex-direction:column;gap:6px;padding:8px;background:var(--panel);border:1px solid var(--line);border-radius:8px;box-shadow:0 8px 28px #0003;min-width:170px}#lay-more-pop .tb{width:100%;text-align:left}.lay-row{display:flex;align-items:center;gap:8px;padding:6px 8px;border:1px solid var(--line);border-radius:6px;margin:4px 0;flex-wrap:wrap}.lay-row .nm{flex:1;min-width:150px;font-weight:600}.lay-row .btn{padding:4px 10px}.lay-sub{margin-inline-start:26px}.lay-row select,.lay-row input{width:auto!important;min-width:150px}.lay-row input{min-width:140px}';document.head.appendChild(s)})();

/* ---------- Button size (one control for every button) ---------- */
const SIZES=[[0.8,'XS'],[0.9,'S'],[1,'M (normal)'],[1.15,'L'],[1.3,'XL']];
function applySize(){
 const k=SIZES[load().size][0];let st=document.getElementById('lay-size');if(!st){st=document.createElement('style');st.id='lay-size';document.head.appendChild(st)}
 if(k===1){st.textContent='';return}
 const cols=k<=0.8?4:k>=1.3?2:3;
 st.textContent='button:not(#home-grid > .nav-main){zoom:'+k+'}#home-grid{grid-template-columns:repeat('+cols+',minmax(0,1fr))!important}#home-grid .nav-main{min-height:'+Math.round(135*k)+'px!important;font-size:'+Math.round(21*k)+'px!important;padding:'+Math.round(24*k)+'px!important}#home-grid .home-description{font-size:'+Math.round(14*k)+'px!important}';
}
window.applyLayoutSize=applySize;
/* ---------- Home tiles ---------- */
window.applyHomeLayout=function(){
 applySize();const g=document.getElementById('home-grid');if(!g)return;const cfg=load().home;
 LAY.el={};LAY.def=[];
 [...g.children].filter(x=>x.tagName==='BUTTON').forEach(b=>{const k=lab(b);b.dataset.lk=k;LAY.el[k]=b;LAY.def.push(k)});
 const inGroup=new Set();cfg.groups.forEach(gr=>gr.items.forEach(k=>inGroup.add(k)));
 const nested=new Set();cfg.groups.forEach(gr=>{if(gr.owner&&LAY.el[gr.owner]&&!inGroup.has(gr.owner)&&gr.owner!==undefined){nested.add(gr.id);const ob=LAY.el[gr.owner];if(!ob.__orig)ob.__orig=ob.onclick;ob.onclick=()=>openFolder(gr.id);const n=gr.items.filter(k=>LAY.el[k]).length;if(!ob.querySelector('.lay-nest')){const t=el('span','lay-nest','\u25B8 +'+n+' more');t.style.cssText='display:block;font-size:13px;font-weight:600;margin-top:8px;opacity:.9';ob.append(t)}}});
 cfg.groups.filter(gr=>!nested.has(gr.id)).forEach(gr=>{const n=gr.items.filter(k=>LAY.el[k]).length;const b=el('button','nav-main','\u25B8 '+gr.name);b.style.setProperty('--tile-color','#64748b');b.dataset.lk='g:'+gr.id;
  const d=el('span','home-description',n+' button'+(n===1?'':'s'));d.style.cssText='display:block;font-size:13px;font-weight:400;margin-top:10px';b.append(d);
  b.style.cssText+=';min-height:145px;padding:18px 16px;display:flex;flex-direction:column;justify-content:center;align-items:center';b.onclick=()=>openFolder(gr.id);LAY.el['g:'+gr.id]=b});
 const order=[],seen=new Set();
 for(const k of cfg.order)if(LAY.el[k]&&!seen.has(k)){seen.add(k);order.push(k)}
 for(const k of [...LAY.def,...cfg.groups.filter(x=>!nested.has(x.id)).map(x=>'g:'+x.id)])if(!seen.has(k)){seen.add(k);order.push(k)}
 LAY.order=order;
 for(const k of order){const b=LAY.el[k];if(inGroup.has(k)||cfg.hidden.includes(k)){if(b.parentNode===g)g.removeChild(b)}else g.appendChild(b)}
};
function openFolder(id){
 const gr=load().home.groups.find(x=>x.id===id);if(!gr)return;
 const c=el('div');c.append(el('h2',null,gr.name));const grid=el('div','home-grid');
 if(gr.owner&&LAY.el[gr.owner]&&LAY.el[gr.owner].__orig){const ob=LAY.el[gr.owner];const t=el('button','nav-main',gr.owner);t.style.cssText=ob.style.cssText;t.style.setProperty('--tile-color',ob.style.getPropertyValue('--tile-color')||'#0369a1');t.onclick=()=>ob.__orig();const d=el('span','home-description','Open the page');d.style.cssText='display:block;font-size:13px;font-weight:400;margin-top:10px';t.append(d);grid.append(t)}
 for(const k of gr.items){const b=LAY.el[k];if(b)grid.append(b)}
 if(!grid.children.length)c.append(el('p','hint','This group is empty. Add buttons to it from Settings > Customize buttons.'));
 c.append(grid);const cl=el('button','btn','Close');cl.style.marginTop='14px';c.append(cl);
 const w=modal(c,'900px');cl.onclick=w.close;grid.addEventListener('click',()=>setTimeout(w.close,0));
}

/* ---------- Top bar ---------- */
function barButtons(){
 const tb=document.querySelector('.topbar');if(!tb)return [];
 const pop=document.getElementById('lay-more-pop');
 const all=[...tb.querySelectorAll(':scope > button'),...(pop?pop.querySelectorAll('button'):[])].filter(b=>!SKIP.has(b.id));
 all.forEach(b=>{b.dataset.lk=b.id||lab(b);BAR.el[b.dataset.lk]=b});return all;
}
function barOrder(cfg){
 const keys=barButtons().map(b=>b.dataset.lk);
 for(const k of keys)if(!BAR.def.includes(k))BAR.def.push(k);
 const base=cfg.order.length?cfg.order:BAR.def,out=[];
 for(const k of base)if(BAR.el[k]&&!out.includes(k))out.push(k);
 for(const k of BAR.def)if(BAR.el[k]&&!out.includes(k))out.push(k);
 return out;
}
let APPLYING=false,OBS=null,TM=0;
window.applyTopbarLayout=function(){
 applySize();const tb=document.querySelector('.topbar');if(!tb||APPLYING)return;APPLYING=true;
 try{
  const cfg=load().bar,anchor=document.getElementById('t-settings');if(!anchor)return;
  const order=barOrder(cfg);let more=document.getElementById('lay-more'),pop=document.getElementById('lay-more-pop');
  const hasMore=order.some(k=>cfg.more.includes(k)&&!cfg.hidden.includes(k));
  if(hasMore&&!more){more=el('button','tb ghost','More \u25BE');more.id='lay-more';tb.insertBefore(more,anchor);
   pop=el('div');pop.id='lay-more-pop';document.body.appendChild(pop);
   more.onclick=e=>{e.stopPropagation();if(pop.style.display==='flex'){pop.style.display='none';return}const r=more.getBoundingClientRect();pop.style.top=(r.bottom+4)+'px';pop.style.right=Math.max(6,window.innerWidth-r.right)+'px';pop.style.display='flex'};
   pop.addEventListener('click',()=>{pop.style.display='none'});document.addEventListener('click',()=>{pop.style.display='none'})}
  for(const k of order){const b=BAR.el[k];if(!b)continue;
   const hid=cfg.hidden.includes(k),inMore=!hid&&cfg.more.includes(k);b.classList.toggle('lay-hide',hid);
   if(inMore&&pop){pop.appendChild(b);b.classList.remove('ghost');b.classList.add('ghost')}
   else if(!inMore){tb.insertBefore(b,more&&more.parentNode===tb?more:anchor)}}
  if(more){if(hasMore){tb.insertBefore(more,anchor)}else{more.remove();if(pop)pop.remove()}}
  tb.appendChild(anchor);
 }finally{if(OBS)OBS.takeRecords();APPLYING=false}
 if(!OBS){OBS=new MutationObserver(()=>{if(APPLYING)return;clearTimeout(TM);TM=setTimeout(window.applyTopbarLayout,60)});OBS.observe(tb,{childList:true})}
};

/* ---------- Editor ---------- */
function mini(t,fn,dis){const b=el('button','btn',t);b.disabled=!!dis;b.onclick=fn;return b}
function homeTop(cfg){const inG=new Set();cfg.groups.forEach(gr=>gr.items.forEach(k=>inG.add(k)));return LAY.order.filter(k=>!inG.has(k))}
function layoutEditor(){
 if(!LAY.order.length&&typeof buildHome==='function')buildHome();
 barOrder(load().bar);
 const c=el('div');const w=modal(c,'820px');
 const commit=(cfg,rebuild)=>{save(cfg);if(rebuild!==false&&typeof buildHome==='function')buildHome();window.applyTopbarLayout();draw()};
 function draw(){
  const cfg=load();c.replaceChildren();
  c.append(el('h2',null,'Customize buttons'));
  c.append(el('p','hint','Move, hide or group the buttons on Home and on the top bar. Only the place of a button changes. Every button keeps doing the same thing, and nothing is deleted. This is saved for your user on this PC. Settings can never be hidden.'));
  /* Button size */
  c.appendChild(el('h3',null,'Button size (all buttons)')).style.cssText='margin:14px 0 6px;font-size:14px;color:var(--accent)';
  {const r=el('div','lay-row');const sm=el('span','nm','Smaller');const sl=el('input');sl.type='range';sl.min=0;sl.max=4;sl.step=1;sl.value=cfg.size;sl.style.cssText='flex:1;min-width:200px';const bg=el('span','nm','Bigger');const cur=el('b',null,SIZES[cfg.size][1]);cur.style.minWidth='80px';
   sl.oninput=()=>{const c2=load();c2.size=Number(sl.value);save(c2);applySize();cur.textContent=SIZES[c2.size][1]};
   r.append(sm,sl,bg,cur);c.append(r);c.append(el('p','hint','Makes every button smaller or bigger: Home buttons, top bar and the buttons inside pages. Saved for your user on this PC. Reset puts it back to Normal.'))}
  /* Home board */
  c.appendChild(el('h3',null,'Home buttons')).style.cssText='margin:14px 0 6px;font-size:14px;color:var(--accent)';
  c.append(el('p','hint','Every button is listed. Next to each button: "Move to" sends it to On Home, Hidden or a group. The arrow puts it inside another button (any level), or Hidden, or back On Home. Dragging and "Move here" still work. A button with buttons inside opens a small window on Home, with its own page as the first tile.'));
  const sel=window.__laySel;
  const inG=new Set();cfg.home.groups.forEach(g=>g.items.forEach(x=>inG.add(x)));
  const PAR=cfg.home.parent||{};
  const kids=x=>Object.keys(PAR).filter(y=>PAR[y]===x&&LAY.el[y]);
  const desc=x=>{let r=[];kids(x).forEach(y=>{r.push(y,...desc(y))});return r};
  const homeKeys=LAY.order.filter(k=>!inG.has(k)&&!cfg.home.hidden.includes(k)&&!PAR[k]);
  const applyTo=(k,dest)=>{const c2=load();c2.home.order=[...LAY.order];c2.home.parent=c2.home.parent||{};c2.home.groups.forEach(g=>{g.items=g.items.filter(x=>x!==k)});c2.home.hidden=c2.home.hidden.filter(x=>x!==k);delete c2.home.parent[k];if(dest==='hidden')c2.home.hidden.push(k);else if(dest.startsWith('grp:')){const gg=c2.home.groups.find(x=>x.id===dest.slice(4));if(gg)gg.items.push(k)}else if(dest!=='home')c2.home.parent[k]=dest;window.__laySel=null;commit(c2)};
  const openMenu=(ar,k,mode)=>{document.querySelectorAll('.lay-menu').forEach(x=>x.remove());const m=el('div','lay-menu');const r=ar.getBoundingClientRect();m.style.cssText='position:fixed;z-index:99999;background:#fff;color:#0f172a;border:1px solid #94a3b8;border-radius:10px;box-shadow:0 8px 24px rgba(0,0,0,.25);padding:6px;max-height:340px;overflow:auto;min-width:220px;font-size:13px;left:'+Math.min(r.left,innerWidth-250)+'px;top:'+Math.min(r.bottom+4,innerHeight-360)+'px';
   const cur=PAR[k]||(cfg.home.hidden.includes(k)?'hidden':'home');const mg=cfg.home.groups.find(x=>x.items.includes(k));
   const item=(t,d,bold)=>{const i=el('div',null,(cur===d?'\u2713 ':'')+t);i.style.cssText='padding:7px 10px;border-radius:6px;cursor:pointer;'+(bold?'font-weight:700;':'')+(cur===d?'background:#e0f2fe;':'');i.onmouseenter=()=>{if(cur!==d)i.style.background='#f1f5f9'};i.onmouseleave=()=>{if(cur!==d)i.style.background=''};i.onclick=()=>{m.remove();applyTo(k,d)};m.append(i)};
   if(mode==='move'){const h0=el('div',null,'Move to:');h0.style.cssText='padding:4px 10px;font-size:11px;color:#64748b';m.append(h0);item('On Home','home',1);item('Hidden','hidden',1);cfg.home.groups.forEach(gg=>item('Group: '+gg.name,'grp:'+gg.id));document.body.append(m);setTimeout(()=>{const f=ev=>{if(!m.contains(ev.target)){m.remove();document.removeEventListener('mousedown',f)}};document.addEventListener('mousedown',f)},0);return}
   item('On Home','home',1);item('Hidden','hidden',1);const h=el('div',null,'Put inside:');h.style.cssText='padding:6px 10px 2px;font-size:11px;color:#64748b;border-top:1px solid #e2e8f0;margin-top:4px';m.append(h);
   const bad=new Set([k,...desc(k)]);LAY.order.filter(x=>!x.startsWith('g:')&&!bad.has(x)).forEach(x=>item(x,x));
   document.body.append(m);setTimeout(()=>{const f=ev=>{if(!m.contains(ev.target)){m.remove();document.removeEventListener('mousedown',f)}};document.addEventListener('mousedown',f)},0)};
  const addArrow=(ch,k)=>{const t=ch.textContent;ch.textContent='';ch.style.display='flex';ch.style.alignItems='center';ch.style.justifyContent='space-between';const lb=el('span',null,t);const ar=el('span',null,'\u25BE');ar.title='Move or put inside another button';ar.style.cssText='margin-left:8px;padding:0 8px;border-left:1px solid rgba(100,116,139,.45);cursor:pointer;font-weight:700;font-size:15px';ar.onclick=e=>{e.stopPropagation();openMenu(ar,k)};const mv=el('span',null,'Move to');mv.style.cssText='margin-left:8px;padding:2px 7px;border:1px solid #64748b;border-radius:6px;cursor:pointer;font-size:11px;font-weight:600';mv.onclick=e=>{e.stopPropagation();openMenu(mv,k,'move')};const rt=el('span');rt.style.cssText='display:flex;align-items:center';rt.append(mv,ar);ch.append(lb,rt)};
  const hiddenKeys=cfg.home.hidden.filter(k=>LAY.el[k]);
  const doMove=(k,target,before)=>{const c2=load();if(c2.home.parent)delete c2.home.parent[k];c2.home.order=[...LAY.order];
   c2.home.groups.forEach(g=>{g.items=g.items.filter(x=>x!==k)});c2.home.hidden=c2.home.hidden.filter(x=>x!==k);
   if(target==='home'){c2.home.order=c2.home.order.filter(x=>x!==k);const i=before?c2.home.order.indexOf(before):-1;if(i<0)c2.home.order.push(k);else c2.home.order.splice(i,0,k)}
   else if(target==='hidden'){c2.home.hidden.push(k)}
   else{const g=c2.home.groups.find(x=>x.id===target);const i=before?g.items.indexOf(before):-1;if(i<0)g.items.push(k);else g.items.splice(i,0,k)}
   window.__laySel=null;commit(c2)};
  const board=el('div');board.style.cssText='display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:10px;align-items:start';
  const col=(id,title,keys,sub)=>{const bx=el('div');bx.style.cssText='border:1px solid var(--line);border-radius:10px;padding:8px;min-height:120px;background:var(--panel)';
   const hd=el('div');hd.style.cssText='display:flex;align-items:center;gap:6px;margin-bottom:6px;font-weight:700';
   if(sub&&sub.gr){const inp=el('input','in');inp.value=sub.gr.name;inp.style.cssText='flex:1;min-width:0';inp.onchange=()=>{const c2=load();const g2=c2.home.groups.find(x=>x.id===sub.gr.id);g2.name=(inp.value||'').trim()||g2.name;commit(c2)};hd.append(el('span',null,'\u25B8'),inp);
    hd.append(mini('\u2715',async()=>{if(await askBox('Remove group','Remove this group? Its buttons go back to Home.')){const c2=load();c2.home.groups=c2.home.groups.filter(x=>x.id!==sub.gr.id);c2.home.order=c2.home.order.filter(x=>x!=='g:'+sub.gr.id);commit(c2)}}))}
   else hd.append(el('span',null,title+' ('+keys.filter(k=>!k.startsWith('g:')).length+')'));
   bx.append(hd);
   if(false&&sub&&sub.gr){const r2=el('div');r2.style.cssText='display:flex;gap:6px;align-items:center;margin-bottom:6px;font-size:12px';r2.append(el('span',null,'Shown as:'));const so=el('select','in');so.style.cssText='flex:1;min-width:0';so.append(new Option('Its own tile','')); homeKeys.filter(x=>!x.startsWith('g:')).forEach(x=>so.append(new Option('Inside button: '+x,x)));so.value=(sub.gr.owner&&homeKeys.includes(sub.gr.owner))?sub.gr.owner:'';so.onchange=()=>{const c2=load();c2.home.order=[...LAY.order];const g2=c2.home.groups.find(x=>x.id===sub.gr.id);g2.owner=so.value||'';commit(c2)};r2.append(so);bx.append(r2)}
   const mh=mini(sel?'Move here':'Move here',()=>{if(sel)doMove(sel,id)},!sel);mh.style.cssText='width:100%;margin-bottom:6px';bx.append(mh);
   bx.ondragover=e=>{e.preventDefault();bx.style.outline='2px dashed var(--accent)'};bx.ondragleave=()=>{bx.style.outline=''};
   bx.ondrop=e=>{e.preventDefault();bx.style.outline='';const k=e.dataTransfer.getData('text/plain');if(k&&!k.startsWith('g:'))doMove(k,id)};
   keys.forEach(k=>{const isG=k.startsWith('g:');const lbl=isG?'\u25B8 '+((cfg.home.groups.find(x=>'g:'+x.id===k)||{}).name||''):k;
    const ch=el('div');ch.textContent=lbl;ch.draggable=!isG;ch.style.cssText='padding:7px 9px;margin:4px 0;border:1px solid var(--line);border-radius:8px;cursor:'+(isG?'default':'grab')+';background:'+(sel===k?'var(--accent)':isG?'#e2e8f0':'#fff')+';color:'+(sel===k?'#fff':'inherit')+';font-size:13px';
    if(isG)ch.style.display='none';
    ch.ondragstart=e=>{e.dataTransfer.setData('text/plain',k)};
    ch.ondragover=e=>{e.preventDefault()};
    ch.ondrop=e=>{e.preventDefault();e.stopPropagation();bx.style.outline='';const d=e.dataTransfer.getData('text/plain');if(d&&d!==k&&!d.startsWith('g:'))doMove(d,id,k)};
    if(!isG)ch.onclick=()=>{window.__laySel=(sel===k?null:k);draw()};
    if(!isG)addArrow(ch,k);bx.append(ch);
    if(!isG&&!(sub&&sub.gr)){const rc=(x,d)=>kids(x).forEach(y=>{const cc=el('div');cc.textContent='\u21B3 '+y;cc.style.cssText='padding:6px 9px;margin:3px 0 3px '+(d*16)+'px;border:1px dashed #38bdf8;border-radius:8px;background:#f0f9ff;font-size:12px;color:#0f172a';addArrow(cc,y);bx.append(cc);rc(y,d+1)});rc(k,1)}});
   if(!keys.length)bx.append(el('div','hint','Empty. Drop buttons here.'));
   return bx};
  board.append(col('home','On Home',homeKeys));
  cfg.home.groups.forEach(g=>board.append(col(g.id,g.name,g.items.filter(k=>LAY.el[k]),{gr:g})));
  board.append(col('hidden','Hidden',hiddenKeys));
  c.append(board);
  const ng=el('div','lay-row');ng.style.marginTop='10px';const gi=el('input','in');gi.placeholder='New group name';gi.style.flex='1';
  const addG=n=>{const c2=load();c2.home.order=[...LAY.order];c2.home.groups.push({id:'g'+Date.now().toString(36)+Math.floor(Math.random()*99),name:n,items:[]});commit(c2)};
  ng.append(gi,mini('Add group',()=>addG((gi.value||'').trim()||('Group '+(cfg.home.groups.length+1)))));
  [['Reports'],['Cash'],['Warehouse']].forEach(([n])=>{if(!cfg.home.groups.some(g=>g.name===n))ng.append(mini('+ '+n,()=>addG(n)))});
  c.append(ng);
  /* Top bar */
  c.appendChild(el('h3',null,'Top bar buttons')).style.cssText='margin:18px 0 6px;font-size:14px;color:var(--accent)';
  const order=barOrder(cfg.bar);
  order.forEach((k,i)=>{const b=BAR.el[k];const r=el('div','lay-row');r.append(el('span','nm',(b&&lab(b))||k));
   const mv=d=>{const c2=load();const o=barOrder(c2.bar);const j=i+d;if(j<0||j>=o.length)return;[o[i],o[j]]=[o[j],o[i]];c2.bar.order=o;commit(c2,false)};
   r.append(mini('\u25B2',()=>mv(-1),i===0),mini('\u25BC',()=>mv(1),i===order.length-1));
   const s=el('select','in');s.append(new Option('Show on the bar','show'),new Option('Inside the More menu','more'),new Option('Hidden','hide'));
   s.value=cfg.bar.hidden.includes(k)?'hide':cfg.bar.more.includes(k)?'more':'show';
   s.onchange=()=>{const c2=load();c2.bar.order=barOrder(c2.bar);c2.bar.hidden=c2.bar.hidden.filter(x=>x!==k);c2.bar.more=c2.bar.more.filter(x=>x!==k);if(s.value==='hide')c2.bar.hidden.push(k);if(s.value==='more')c2.bar.more.push(k);commit(c2,false)};
   r.append(s);c.append(r)});
  const row=el('div','toolbar');row.style.marginTop='16px';
  const rs=el('button','btn','Reset to default layout');rs.onclick=async()=>{if(await askBox('Reset layout','Put every button back in its original place?')){save(blank());if(typeof buildHome==='function')buildHome();window.applyTopbarLayout();draw()}};
  const dn=el('button','btn accent','Done');dn.onclick=w.close;row.append(rs,dn);c.append(row);
 }
 draw();
}
window.layoutEditor=layoutEditor;

/* nesting by arrow (any level) */
(function(){const orig=window.applyHomeLayout;
 window.applyHomeLayout=function(){orig();const g=document.getElementById('home-grid');if(!g)return;const par=(load().home.parent)||{};const owners=new Map();
  Object.keys(par).forEach(k=>{const p=par[k];if(LAY.el[k]&&LAY.el[p]){owners.set(p,(owners.get(p)||0)+1);if(LAY.el[k].parentNode===g)g.removeChild(LAY.el[k])}});
  Object.keys(LAY.el).forEach(k=>{const b=LAY.el[k];if(!b||k.startsWith('g:'))return;if(!owners.has(k)){const o=b.querySelector('.lay-nest2');if(o)o.remove();if(b.__orig2){b.onclick=b.__orig2;b.__orig2=null}}});
  owners.forEach((n,p)=>{const ob=LAY.el[p];if(!ob.__orig2)ob.__orig2=ob.onclick;ob.__orig=ob.__orig2;ob.onclick=()=>openNest(p);let t=ob.querySelector('.lay-nest2');if(!t){t=el('span','lay-nest2');t.style.cssText='display:block;font-size:13px;font-weight:600;margin-top:8px;opacity:.9';ob.append(t)}t.textContent='\u25B8 +'+n+' more'})};
})();
function origTiles(p){try{const i=NAV_GROUPS.findIndex(x=>x[0]===p);if(i<0)return null;const color=NAV_GROUPS[i][1];const items=i===3?[["Invoice Details","details"],...S.statuses.map(x=>[x,"s:"+x])]:NAV_GROUPS[i][2];if(items.length<2)return null;return items.map(([label,key],n)=>{const b=el('button','nav-subtile',label);b.style.setProperty('--tile-color',TILE_COLORS[n%TILE_COLORS.length]);b.onclick=()=>go(key);return b})}catch(e){return null}}
function openNest(p){const par=load().home.parent||{};const gi=NAV_GROUPS.findIndex(x=>x[0]===p);if(gi>=0&&origTiles(p)){go('group:'+gi);const pg=document.getElementById('home-grid');if(pg){Object.keys(par).filter(k=>par[k]===p&&LAY.el[k]).forEach(k=>pg.append(LAY.el[k]));return}}const c=el('div');c.append(el('h2',null,p));const grid=el('div','home-grid');const ob=LAY.el[p];
 const t=el('button','nav-main',p);t.style.cssText=ob.style.cssText;t.style.setProperty('--tile-color',ob.style.getPropertyValue('--tile-color')||'#0369a1');t.onclick=()=>ob.__orig2();const d=el('span','home-description','Open the page');d.style.cssText='display:block;font-size:13px;font-weight:400;margin-top:10px';t.append(d);const ot=origTiles(p);if(ot)ot.forEach(x=>grid.append(x));else grid.append(t);
 Object.keys(par).filter(k=>par[k]===p&&LAY.el[k]).forEach(k=>grid.append(LAY.el[k]));
 c.append(grid);const cl=el('button','btn','Close');cl.style.marginTop='14px';c.append(cl);const w=modal(c,'900px');cl.onclick=w.close;grid.addEventListener('click',()=>setTimeout(w.close,0))}
})();
