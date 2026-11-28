"use strict";
function initV54Chrome(){if(!$('#connection-lamp')){const lamp=el('span');lamp.id='connection-lamp';$('.live-label').after(lamp)}$('#receive-summary').textContent='';$('.bar-tail').textContent='';if(!$('#sync-floating')){const x=el('div');x.id='sync-floating';x.setAttribute('aria-live','polite');document.body.append(x)}installClearSearch();installClearEverywhere();updateConnectionLamp(null)}
function updateConnectionLamp(c){const lamp=$('#connection-lamp');if(!lamp)return;lamp.classList.toggle('connected',!!c?.connected);lamp.title=c?.reason||'Connection not confirmed';lamp.setAttribute('aria-label',c?.connected?'Firebase connected':'Firebase disconnected')}
let tickerSeq=null,tickerSession=null,tickerQueue=[],tickerActive=0;
let notifySeq=-1;function syncTicker(received){const events=received?.events||[];const m=events.reduce((n,x)=>Math.max(n,x.seq),0);if(m!==notifySeq){notifySeq=m;notifyRefresh()}}
function drainTicker(){}
function otherMenu(){if(!canOpen('other'))return msgBox('Access denied','Other is not allowed.',true);const w=deliveryWindow('Other',()=>go('home'));w.body.append(el('h2',null,'Other'));const g=el('div');g.style.cssText='display:grid;grid-template-columns:1fr 1fr;gap:22px;margin-top:24px';for(const [name,desc,fn,color]of [['Conflict','Review invoice and expense conflicts.',conflictMenu,'#b91c1c']]){const b=el('button','nav-main',name);b.style.cssText='--tile-color:'+color+';min-height:170px';const d=el('span','home-description',desc);d.style.cssText='display:block;font-size:14px;font-weight:400;margin-top:14px';b.append(d);b.onclick=()=>{w.close();fn()};g.append(b)}w.body.append(g)}
function conflictMenu(){const w=deliveryWindow('Other > Conflict',otherMenu);w.body.append(el('h2',null,'Conflict'));const g=el('div');g.style.cssText='display:grid;grid-template-columns:1fr 1fr;gap:22px;margin-top:24px';for(const [name,desc,fn]of [['Conflict Invoices','Review preserved invoice and list sync differences.',invoiceConflicts],['Conflict Expenses','Review cash collection, expense and settings conflicts.',()=>financeConflicts(conflictMenu)]]){const b=el('button','nav-main',name);b.style.cssText='--tile-color:#b91c1c;min-height:170px';const d=el('span','home-description',desc);d.style.cssText='display:block;font-size:14px;font-weight:400;margin-top:14px';b.append(d);b.onclick=fn;g.append(b)}w.body.append(g);w.foot.textContent='No conflicts are resolved automatically. Existing history is preserved.'}
const CONFLICT_INFO={
 invoice_equal_timestamp:['Two PCs saved this invoice at the same moment with different content. The program kept the incoming version and saved the other one here.','Was (this PC before)','Became (now in the program)',true],
 deleted_invoice:['This PC had a change that was not sent yet, and another PC deleted the invoice. The deletion was applied and your unsent version is saved here.','Was (unsent change on this PC)','Became (deleted)',true],
 invoice:['A newer version of this invoice was already in the cloud. The cloud version was kept and the version this PC tried to send is saved here.','Was (sent from this PC)','Became (cloud version, now in the program)',true],
 lan_before_delete:['A delete arrived from the shared folder. This is the last version before it was deleted.','Was (before delete)','Became (deleted)',true],
 lan_previous_version:['A newer version arrived from the shared folder and replaced this one.','Was (previous version)','Became (now in the program)',true],
 lan_incoming_not_applied:['A version arrived from the shared folder but was not applied because this PC already had the same or a newer version.','Now in the program (kept)','Arrived but not applied',false],
 lan_blocked_by_delete:['A version arrived from the shared folder for an invoice that is deleted here. It was not applied.','Now in the program (deleted)','Arrived but not applied',false]};
async function invoiceConflicts(){const r=await api('/api/sync/conflicts');if(!r.ok)return msgBox('Conflict Invoices',r.msg||'Unavailable',true);const c=el('div');c.append(el('h2',null,'Conflict Invoices'),el('p','hint','Nothing is changed or deleted automatically. Each item shows what the invoice was, what it became and what happened.'));
 const skip=new Set(['updated','seq','sync_protocol']);const fmt=v=>v===undefined||v===null||v===''?'(empty)':String(v);const when=t=>t?new Date(t*1000).toLocaleString():'-';
 for(const x of r.conflicts||[]){const info=CONFLICT_INFO[x.kind]||['A preserved version was saved for review.','Preserved version','Now in the program',true];const pres=x.data||{},cur=x.current||{};const left=info[3]?pres:cur,right=info[3]?cur:pres;const rightGone=!(info[3]?x.current:x.data)&&true;
  const box=el('div');box.style.cssText='border:1px solid var(--line);border-radius:10px;padding:12px;margin:12px 0';
  const d=pres['Invoice Number']||cur['Invoice Number']||x.key,cu=pres['Customer Name']||cur['Customer Name']||'';
  box.append(el('h3',null,d+(cu?' | '+cu:'')));
  const what=el('p',null,'What happened: '+info[0]);what.style.fontWeight='600';box.append(what);
  box.append(el('p','hint','Recorded '+when(x.recorded)+' | Saved version last updated '+when(pres.updated)+(pres['Last Updated By']?' by '+pres['Last Updated By']:'')+' | Now in the program: '+(x.current?'updated '+when(cur.updated)+(cur['Last Updated By']?' by '+cur['Last Updated By']:''):'deleted')));
  const keys=[...new Set([...Object.keys(left),...Object.keys(right)])].filter(k=>!k.startsWith('_')&&!skip.has(k));let diff=keys.filter(k=>fmt(left[k])!==fmt(right[k]));if(info[3]&&!x.current&&diff.length>6)diff=['Invoice Number','Customer Name','Invoice Value','Invoice Status','Remarks','Last Updated By'].filter(k=>keys.includes(k));
  box.append(el('p',null,diff.length?(info[3]&&!x.current?'The whole invoice was deleted. Main fields of the saved version:':diff.length+' field(s) differ'):'The content is the same; only the timestamp or the sender differs.'));
  const t=el('table','gtab');t.style.width='100%';const hd=el('tr');for(const h of ['Field',info[1],info[2]])hd.append(el('th',null,h));t.append(hd);
  const rows=(all)=>{t.replaceChildren(hd);for(const k of all?keys:diff){const tr=el('tr');const f=el('th',null,k),a=el('td',null,x.current||info[3]?fmt(left[k]):fmt(left[k])),b=el('td',null,(info[3]&&!x.current)?'(deleted)':fmt(right[k]));f.style.textAlign='left';if(diff.includes(k)){a.style.cssText='background:#fee2e2;font-weight:700';b.style.cssText='background:#dcfce7;font-weight:700'}for(const z of [a,b])z.style.whiteSpace='normal';tr.append(f,a,b);t.append(tr)}};rows(false);
  const more=el('button','btn','Show all fields');let all=false;more.onclick=()=>{all=!all;rows(all);more.textContent=all?'Show only differences':'Show all fields'};box.append(t,more);
  {const bar=el('div');bar.style.cssText='display:flex;gap:10px;flex-wrap:wrap;margin-top:12px';const canKeep=!!x.current&&['invoice_equal_timestamp','invoice','lan_previous_version'].includes(x.kind);
   const done=async keep=>{const r2=await api('/api/sync/conflicts/resolve',{id:x.id,keep});if(!r2.ok)return msgBox('Conflict',r2.msg||'Not saved',true);w.close();toast(r2.msg);invoiceConflicts();if(typeof updateOtherIndicator==='function')updateOtherIndicator()};
   const kb=el('button','btn accent','Keep Became ('+info[2].replace(/^Became \(|\)$/g,'')+')'),kw=el('button','btn','Keep Was ('+info[1].replace(/^Was \(|\)$/g,'')+')');
   kb.onclick=()=>done('became');kw.onclick=async()=>{if(await askBox('Keep Was','Put the saved "Was" version of this invoice back in the program and send it to the other PCs?'))done('was')};
   if(canKeep)bar.append(kb,kw);const rj=el('button','btn danger',x.current&&!['list','list_equal_timestamp'].includes(x.kind)?'Reject (delete this invoice)':'Reject (remove this item)');rj.onclick=async()=>{if(await askBox('Reject',x.current&&!['list','list_equal_timestamp'].includes(x.kind)?'Reject this invoice? It is deleted completely from the program and from the cloud, on every PC. This cannot be undone.':'Remove this item from the list? No invoice is changed.'))done('reject')};bar.append(rj);box.append(bar)}
  c.append(box)}
 if(!r.conflicts?.length)c.append(el('p',null,'No sync conflicts.'));const close=el('button','btn','Close');c.append(close);const w=modal(c,'1100px');close.onclick=w.close}
async function updateOtherIndicator(invoiceCount){const button=$('#home-other');if(!button)return;try{if(invoiceCount===undefined){const r=await api('/api/sync/conflicts');invoiceCount=(r.conflicts||[]).length}const r=S.financeEnabled?await api('/api/finance/conflicts'):{conflicts:[]};const n=invoiceCount+(r.conflicts||[]).length;button.querySelector('.needs-action')?.remove();if(n)button.append(el('span','needs-action','Needs action'))}catch(e){/* no invented conflict status */}}

function districtBatchEditor(ids,data,done){if(!ids.length)return;const rows=data.districts.flatMap(d=>d.customers.flatMap(c=>c.rows)).filter(r=>ids.includes(r.uid));const c=el('div');c.append(el('h2',null,'Edit '+ids.length+' selected invoices'),el('p','hint','Only the selected matching Undelivered invoices are changed. Blank fields stay unchanged.'));const grid=el('div','mgrid'),inputs={};for(const [label,key]of [['Invoice Status','Invoice Status'],['Car No','Car No'],['Driver Name','Driver name'],['Rep Name','Distribution Rep'],['Distributed Date','Distributed Date'],['Line','Line']]){const f=el('div','fld');f.append(el('label',null,label));let input;if(key==='Invoice Status'){input=el('select','in');for(const [value,text]of [['','Unchanged'],['inprocess','In Process'],['Proposal','Proposal'],['Undelivered','Undelivered']]){const o=el('option',null,text);o.value=value;input.append(o)}}else input=el('input','in');inputs[key]=input;f.append(input);grid.append(f)}c.append(grid);const cancel=el('button','btn','Cancel'),save=el('button','btn accent','Apply to selected invoices');c.append(cancel,save);const m=modal(c,'780px');cancel.onclick=m.close;save.onclick=async()=>{const changes=Object.fromEntries(Object.entries(inputs).map(([k,v])=>[k,v.value.trim()]).filter(([k,v])=>v));if(!Object.keys(changes).length)return;if(!await askBox('Confirm batch edit','Apply these fields to '+ids.length+' selected Undelivered invoices? Blank fields remain unchanged.'))return;save.disabled=true;try{const r=await api('/api/delivery/batch',{uids:ids,expected:Object.fromEntries(rows.map(r=>[r.uid,r.updated])),changes});if(!r.ok)return msgBox('Not saved',r.msg,true);m.close();await done();toast(r.msg)}finally{save.disabled=false}}}

function installClearSearch(){
 const add=(host,run)=>{if(!host||host.querySelector('[data-clear-search]'))return;const b=el('button','btn','Clear search');b.dataset.clearSearch='1';b.onclick=run;host.append(b)};
 setTimeout(()=>{
  add($('#rep-bar'),()=>{RB.date.value='';RB.drv.set('');RB.car.set('');RB.line.value='';fillRoute()});
  add($('#ho-form'),()=>{for(const x of [HO.from,HO.to,HO.fw,HO.ty,HO.pt])if(x)x.value=''});
  const pi=$('#pi-q');if(pi)add(pi.parentElement,()=>{pi.value='';$('#pi-date').value='';piShow()});
 },0);
}

const HOME_PERMISSION_KEYS=['search','new','und','details','reports','wh','rgr'];
function viewPermission(k){if(k==='home')return null;if(k.startsWith('group:'))return HOME_PERMISSION_KEYS[Number(k.slice(6))];if(k==='s:Undelivered'||k==='und')return 'und';if(k.startsWith('s:'))return 'details';return {'rep:inprocess':'inprocess','rep:Proposal':'proposal','ho':'reports','rep':'reports','review':'plans' }[k]||k}
function canOpen(k){const key=viewPermission(k);return !key||S.isAdmin||!Array.isArray(S.permissions)||S.permissions.includes(key)}
function applyHomePermissions(){for(const b of $('#home-grid').querySelectorAll('button')){const key=b.dataset.category!==undefined?'group:'+b.dataset.category:b.dataset.shortcut||b.dataset.destination||(b.id==='home-other'?'other':b.id==='t-review'?'plans':b.id==='t-drvdel'?'drvdel':b.dataset.delivery?'delivery':null);if(!key)continue;b.disabled=!canOpen(key);b.title=b.disabled?'Not allowed for your user':'';b.style.opacity=b.disabled?'.4':''}}
async function userPermissions(name){const r=await api('/api/users/permissions/get',{name});if(!r.ok)return msgBox('Permissions',r.msg,true);const c=el('div');c.append(el('h2',null,'Users & permissions: '+name),el('p','hint','Checked = can open. Existing users keep all access until ADMIN changes their permissions.'));const grid=el('div');grid.style.cssText='display:grid;grid-template-columns:1fr 1fr;gap:12px 22px;margin:18px 0';const boxes={};for(const [key,label]of r.buttons){const row=el('label');row.style.cssText='display:flex;gap:10px;align-items:center;padding:12px;border:1px solid var(--line);border-radius:7px';const cb=el('input');cb.type='checkbox';cb.checked=r.allowed.includes(key);cb.disabled=r.admin;cb.style.cssText='width:18px;height:18px';boxes[key]=cb;row.append(cb,el('span',null,label));grid.append(row)}c.append(grid);if(r.admin)c.append(el('p','hint','ADMIN keeps all permissions to prevent lockout.'));const cancel=el('button','btn','Cancel'),save=el('button','btn accent','Save permissions');save.disabled=r.admin;c.append(cancel,save);const m=modal(c,'900px');cancel.onclick=m.close;save.onclick=async()=>{save.disabled=true;try{const allowed=Object.keys(boxes).filter(k=>boxes[k].checked),a=await api('/api/users/permissions/set',{name,allowed,revision:r.revision});if(!a.ok)return msgBox('Not saved',a.msg,true);m.close();toast(a.msg)}finally{save.disabled=false}}}

function cashMenu(){if(!canOpen('other'))return msgBox('Access denied','Cash is not allowed.',true);const w=deliveryWindow('Cash',()=>go('home'));w.body.append(el('h2',null,'Cash'));const g=el('div');g.style.cssText='display:grid;grid-template-columns:1fr 1fr;gap:22px;margin-top:24px';for(const [name,desc,fn,color]of [['Cash Invoice Collection','Cash invoices waiting for collection. Collected removes the row.',cashCollection,'#0369a1'],['Expenses','Cash received, expenses and cash returned.',expenseLedger,'#b45309']]){const b=el('button','nav-main',name);b.style.cssText='--tile-color:'+color+';min-height:170px';const d=el('span','home-description',desc);d.style.cssText='display:block;font-size:14px;font-weight:400;margin-top:14px';b.append(d);b.onclick=()=>{w.close();fn()};g.append(b)}w.body.append(g)}
async function cashCollection(){
 const w=deliveryWindow('Cash > Cash Invoice Collection',cashMenu);w.body.textContent='Loading...';
 const search=el('input','in');search.placeholder='Search invoice, customer or remarks';search.style.flex='1';const clear=el('button','btn','Clear search');clear.dataset.clearSearch='1';const show=el('input');show.type='checkbox';const showLab=el('label');showLab.append(show,el('span',null,' Show collected'));const refresh=el('button','btn','Refresh'),count=el('span','cnt');w.bar.append(search,clear,showLab,refresh,count);
 let data=null;
 async function load(){const r=await api('/api/review/cash');if(!r.ok){w.body.textContent=r.msg||'Could not load.';return}data=r;draw()}
 function stateOf(x){return (x.manual_mark||{state:'unmarked'}).state}
 function draw(){
  const q=search.value.trim().toLowerCase();w.body.textContent='';
  const rows=(data.table_rows||[]).filter(x=>(show.checked||stateOf(x)!=='collected')&&(!q||x.values.join(' ').toLowerCase().includes(q)));
  count.textContent=rows.length+' cash invoices'+(show.checked?'':' (collected hidden)');
  if(!S.financeEnabled)w.body.append(el('p','hint','Read-only. Collection marking is not activated.'));
  const wrap=el('div');wrap.style.cssText='overflow:auto;height:100%;direction:ltr';const t=el('table','gtab');t.classList.add('cash-compact');t.style.cssText='width:max-content;direction:ltr';const h=el('tr');h.append(Object.assign(el('th',null,'Collection'),{}));for(const col of data.table_columns)h.append(el('th',null,col));t.append(h);
  for(const x of rows){const tr=el('tr'),td=el('td');td.style.cssText='position:sticky;left:0;background:var(--panel);z-index:1;white-space:nowrap;border-left:2px solid var(--line)';let mark=x.manual_mark||{state:'unmarked',heads:[]};const ids={};const st=el('span',null,'');st.style.cssText='font-size:11px;margin-right:4px';td.append(st);
   for(const [label,chosen]of [['Collected','collected'],['Not yet','not_yet']]){const btn=el('button','btn accent',label);btn.style.cssText='display:inline-block;font-size:11px;padding:1px 7px;min-height:21px;margin:0 2px;line-height:17px;vertical-align:middle';btn.disabled=!S.financeEnabled;btn.onclick=async()=>{if(!ids[chosen])ids[chosen]=crypto.randomUUID();btn.disabled=true;const res=await api('/api/finance/mark',{uid:x.uid,state:chosen,expected:mark.heads,request_id:ids[chosen]});btn.disabled=!S.financeEnabled;if(!res.ok)return msgBox('Collection mark',res.msg||'Not saved.',true);for(const k of Object.keys(ids))delete ids[k];const fresh=await api('/api/review/cash');data=fresh;if(chosen==='collected'&&!show.checked){tr.remove();count.textContent=(w.body.querySelectorAll('tbody tr, tr').length-1)+' cash invoices (collected hidden)';draw()}else draw()};td.append(btn)}
   st.textContent=mark.state==='conflict'?'CONFLICT':(mark.state==='collected'?'collected':'');tr.append(td);for(const v of x.values)tr.append(el('td',null,v));t.append(tr)}
  wrap.append(t);if(!rows.length)w.body.append(el('p','hint','No cash invoices waiting for collection.'));w.body.append(wrap)}
 search.oninput=()=>data&&draw();clear.onclick=()=>{search.value='';show.checked=false;data&&draw()};show.onchange=()=>data&&draw();refresh.onclick=load;await load();
}
function installClearEverywhere(){
 const add=bar=>{if(!bar||bar.querySelector('[data-clear-search]'))return;const inputs=[...bar.querySelectorAll('input.in:not([type=checkbox])')];if(!inputs.length)return;const b=el('button','btn','Clear search');b.dataset.clearSearch='1';b.onclick=()=>{for(const i of bar.querySelectorAll('input.in:not([type=checkbox])')){i.value='';i.dispatchEvent(new Event('input',{bubbles:true}))}};bar.append(b)};
 const scan=()=>{for(const bar of document.querySelectorAll('.delivery-bar,.delivery-window .toolbar,#modal-root .toolbar'))add(bar);for(const i of document.querySelectorAll('#paper-check-number')){const host=i.parentElement;if(host&&!host.querySelector('[data-clear-search]')){const b=el('button','btn','Clear search');b.dataset.clearSearch='1';b.onclick=()=>{i.value='';i.dispatchEvent(new Event('input',{bubbles:true}));i.focus()};host.append(b)}}};
 new MutationObserver(scan).observe(document.body,{childList:true,subtree:true});scan();
}

// ---- v55 Notifications: top-bar button, +N badge, New / Earlier, read-only View. No floating toasts. ----
let NOTIFY_ROWS=[],NOTIFY_REFRESH=null;
async function notifyRefresh(){
 if(!$('#t-notify')){const b=el('button','tb','Notifications');b.id='t-notify';b.onclick=notifyCenter;const t=$('#t-settings');if(!t)return;t.parentNode.insertBefore(b,t)}
 const r=await api('/api/notify');if(!r.ok)return;NOTIFY_ROWS=r.events;
 const b=$('#t-notify');b.textContent='Notifications';b.querySelector('.nbadge')?.remove();
 if(r.unseen){const x=el('span','nbadge','+'+r.unseen);x.style.cssText='background:#2563eb;color:#fff;border-radius:10px;padding:1px 7px;margin-left:6px;font-size:12px;font-weight:700';b.append(x)}
 if(NOTIFY_REFRESH)NOTIFY_REFRESH();
}
const NMARK=new Set();let NLX=-1,NLY=-1,NLT=0,NARM=true;const NQUIET=160;
function notifyMark(ids){ids=ids.filter(i=>!NMARK.has(i));if(!ids.length)return;ids.forEach(i=>NMARK.add(i));api('/api/notify/seen',{ids}).then(()=>{ids.forEach(i=>NMARK.delete(i));notifyRefresh()},()=>ids.forEach(i=>NMARK.delete(i)))}
function notifyView(e){
 api('/api/notify/seen',{ids:[e.id]}).then(r=>{if(r.ok)notifyRefresh()});
 const c=el('div');c.append(el('h2',null,(e.operation==='Add'?'Added: ':'Edited: ')+e.invoice));
 const meta=el('p','hint',(e.operation==='Add'?'Entered by ':'Last updated by ')+(e.by||'not recorded')+' | '+new Date(e.at*1000).toLocaleString()+(e.entered_by&&e.operation==='Edit'?' | Entered by '+e.entered_by:''));c.append(meta);
 const t=el('table','gtab');t.style.width='100%';for(const [k,v] of Object.entries(e.details||{})){const tr=el('tr');const a=el('th',null,k),d=el('td',null,String(v));a.style.cssText='text-align:left;width:34%';d.style.cssText='white-space:normal;overflow-wrap:anywhere';tr.append(a,d);t.append(tr)}
 const wrap=el('div');wrap.style.cssText='max-height:60vh;overflow:auto';
 if(e.operation==='Edit'&&e.changes&&e.changes.length){const h=el('h3',null,'What changed');h.style.cssText='margin:10px 0 6px';wrap.append(h);const ct=el('table','gtab');ct.style.width='100%';const hr=el('tr');for(const x of ['Field','Was','Now']){const th=el('th',null,x);th.style.cssText='text-align:left';hr.append(th)}ct.append(hr);
  for(const ch of e.changes){const tr=el('tr');const a=el('th',null,ch.field),o=el('td',null,ch.old===''?'(empty)':String(ch.old)),n=el('td',null,ch.new===''?'(empty)':String(ch.new));a.style.cssText='text-align:left;width:30%';o.style.cssText='background:#fde8e8;color:#a40000';n.style.cssText='background:#e3f6e8;color:#0b6b2a;font-weight:700';tr.append(a,o,n);ct.append(tr)}wrap.append(ct);
  const h2=el('h3',null,'All fields');h2.style.cssText='margin:14px 0 6px';wrap.append(h2)}
 wrap.append(t);c.append(wrap);
 const m=modal(c,'760px');c.append(expButton('Close',m.close));
}
async function notifyCenter(){
 const w=deliveryWindow('Notifications',()=>go('home'));
 const draw=()=>{
  const hh=el('div');hh.style.cssText='display:flex;align-items:center;gap:14px;flex-wrap:wrap';hh.append(el('h2',null,'Notifications'));
  const mk=el('button','btn accent','Mark all as read');mk.onclick=()=>notifyMark(NOTIFY_ROWS.filter(x=>!x.seen).map(x=>x.id));hh.append(mk);
  hh.append(el('span','hint','Point at a notification to mark it read (one per mouse movement), or press Mark all as read.'));w.body.replaceChildren(hh);
  const fresh=NOTIFY_ROWS.filter(x=>!x.seen),old=NOTIFY_ROWS.filter(x=>x.seen);
  const section=(title,rows,isNew)=>{
   const h=el('h3',null,title);h.style.marginTop='18px';w.body.append(h);
   if(!rows.length){w.body.append(el('p','hint',isNew?'Nothing new.':'Nothing earlier.'));return}
   const t=el('table','gtab');t.style.width='100%';const hd=el('tr');for(const x of ['','Type','Invoice','Customer','By','Time',''])hd.append(el('th',null,x));t.append(hd);
   for(const e of rows){const tr=el('tr');if(isNew){const mark=ev=>{if(ev.type==='mousemove'){const n=performance.now(),quiet=n-NLT>=NQUIET;NLT=n;if(!NARM&&!quiet)return;if(ev.clientX===NLX&&ev.clientY===NLY)return;NLX=ev.clientX;NLY=ev.clientY}NARM=false;notifyMark([e.id])};tr.addEventListener('mousemove',mark);tr.addEventListener('click',mark)}const dot=el('td');dot.style.width='24px';if(isNew){const d=el('span');d.style.cssText='display:inline-block;width:12px;height:12px;border-radius:50%;background:#2563eb';d.title='New';dot.append(d)}
    const op=el('td',null,e.operation);op.style.fontWeight='700';
    const who=e.operation==='Delete'?'Deleted by '+(e.by||'not recorded'):(e.operation==='Add'?'Entered by ':'Updated by ')+(e.by||'not recorded');
    const act=el('td');if(e.operation!=='Delete')act.append(expButton('View',()=>notifyView(e)));
    const cells=[op,el('td',null,e.invoice),el('td',null,e.customer),el('td',null,who),el('td',null,new Date(e.at*1000).toLocaleString()),act];
    for(const c of cells){c.style.cssText+=';white-space:normal;overflow-wrap:anywhere;vertical-align:top'}
    tr.append(dot,...cells);t.append(tr)}
   w.body.append(t)};
  section('New',fresh,true);section('Earlier',old,false);
 };
 NOTIFY_REFRESH=draw;await notifyRefresh();draw();
 // Delete rows have no View: they become seen once the list has been shown.
 const dels=NOTIFY_ROWS.filter(x=>!x.seen&&x.operation==='Delete').map(x=>x.id);
 if(dels.length)setTimeout(()=>api('/api/notify/seen',{ids:dels}).then(()=>notifyRefresh()),4000);
 const close=w.close;w.close=()=>{NOTIFY_REFRESH=null;close()};
}
