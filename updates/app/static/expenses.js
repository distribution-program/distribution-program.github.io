/* Source-only local expense candidate. Does not change invoice views or cloud data. */
"use strict";
function expButton(label, fn, accent=false) {
  const b=el('button', 'btn'+(accent?' accent':''), label); b.onclick=fn; return b;
}
function expField(host, label, name, value='', type='text', choices=null) {
  const box=el('div','fld');box.appendChild(el('label',null,label));
  const input=el(choices?'select':'input','in');input.dataset.exp=name;
  if(choices) for(const v of choices){const o=el('option',null,v);o.value=v;input.appendChild(o);}
  else input.type=type;
  input.value=value||(choices?choices[0]:'');box.appendChild(input);host.appendChild(box);return input;
}
async function expenseLedger() {
 if(!S.financeEnabled)return msgBox("Expenses", "The finance protocol candidate is enabled only in the isolated fictional profile. Live use is not released.",true);
 const r=await api('/api/exp/ledger');if(!r.ok)return msgBox('Expenses',r.msg||'Could not load.',true);
 const c=el('div');c.appendChild(el('h2',null,'Expenses'));
 const note=el('p','hint',S.testMode?'FICTIONAL TEST PROFILE. Saved locally and included in the same Backup / Load backup flow. No live sync. Not for live accounts.':'Saved locally first. Approved finance sync sends revisions to the server; each other PC must receive them. Included in Backup / Load backup.');note.style.color='#b45309';c.appendChild(note);
 const fs=r.finance_sync||{};c.appendChild(el('p','hint',fs.enabled&&!S.testMode?`Finance server: ${fs.error?'PENDING / '+fs.error:fs.ready?'caught up to sequence '+fs.checkpoint:'checking'} | Pending upload: ${fs.pending||0}. Other-PC receipt is not confirmed here.`:'Live finance sync is not enabled.'));
 c.appendChild(el('h3',null,`Total cash: ${r.balance===null?'UNKNOWN':r.balance} ${r.currency||'(currency not set)'}`));
 c.appendChild(el('p','hint',r.opening_balance===null?'Enter an opening balance and date in Expense settings. The balance is calculated, never edited.':`Opening balance ${r.opening_balance} from ${r.opening_effective}. One shared cash total; driver and vehicle are labels only.`));
 if(r.negative_from){const n=el('p',null,'Negative cash balance from '+r.negative_from+'. Check entries.');n.style.color='#b91c1c';c.appendChild(n);}
 const act=r.entries.filter(e=>!e.voided),sum=k=>act.filter(e=>e.kind===k).reduce((a,e)=>a+(parseFloat(e.amount)||0),0);
 const cards=el('div');cards.style.cssText='display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin:12px 0';
 for(const [t,v] of [['Cash received',sum('receipt').toFixed(2)],['Expenses',sum('expense').toFixed(2)],['Cash returned',sum('return').toFixed(2)],['Entries',act.length+(r.entries.length>act.length?' (+'+(r.entries.length-act.length)+' voided)':'')],['Last entry',act.length?act[act.length-1].entry_date:'-']]){const k=el('div');k.style.cssText='border:1px solid var(--line);border-radius:10px;padding:12px;background:var(--panel,#fff)';const a=el('div','hint',t),b=el('div',null,v);b.style.cssText='font-size:22px;font-weight:700;margin-top:4px';k.append(a,b);cards.appendChild(k)}c.appendChild(cards);
 const toolbar=el('div','mrow');c.appendChild(toolbar);
 if(r.provisional){const warning=el('p',null,'UNRESOLVED CONFLICT: total cash is unknown until reviewed.');warning.style.color='#b91c1c';c.appendChild(warning);}
 const wrap=el('div');wrap.style.cssText='max-height:calc(100vh - 430px);min-height:240px;overflow:auto';c.appendChild(wrap);
 const table=el('table','gtab'),head=el('tr');for(const s of ['Date','Kind / category','Amount','Driver / vehicle','Odometer / fuel','Cash after','Actions'])head.appendChild(el('th',null,s));table.style.cssText='table-layout:fixed;width:100%';table.appendChild(head);
 for(const e of r.entries.slice().reverse()){
  const row=el('tr');const fuel=(()=>{if(!e.odometer)return '';const prev=e.previous_odometer,dist=e.odometer_distance,lit=e.liters_receipt||e.liters_calc;let t='Odometer before: '+(prev===null||prev===undefined?'none (first reading)':prev+' km')+'\nOdometer after: '+e.odometer+' km\nKm driven: '+(dist?dist+' km':'not confirmed');if(lit){t+='\nLiters bought: '+lit+' L @ '+e.fuel_price;if(dist&&Number(lit)>0)t+='\nConsumption: '+(Number(dist)/Number(lit)).toFixed(2)+' km per liter ('+(Number(lit)/Number(dist)*100).toFixed(1)+' L per 100 km)';}return t;})();
  for(const v of [e.entry_date,e.kind+' / '+e.category,e.amount,(e.driver||'-')+' / '+(e.vehicle||'-')+' | Place: '+(e.place||'-')+' | Method: '+(e.payment_method||'-'),fuel,e.balance_after===null?'UNKNOWN':e.balance_after]){const td=el('td',null,v);td.style.cssText='white-space:pre-line;overflow-wrap:anywhere;vertical-align:top';row.appendChild(td);}
  if(e.negative_balance)row.style.color='#b91c1c';const act=el('td');act.style.whiteSpace='normal';act.append(expButton('Edit',()=>expenseEntry(e,refresh)),expButton('Void',()=>expenseVoid(e,refresh)),expButton('History',()=>expenseHistory(e.entry_id)));row.appendChild(act);table.appendChild(row);
 }
 if(!r.entries.length)c.appendChild(el('p','hint','No entries yet. Add cash received, an expense, or cash returned.'));
 wrap.appendChild(table);c.appendChild(el('p','hint','Consumption assumes the tank was filled full at the previous fill and at this one. Liters = amount / price (or liters on receipt). Km driven = odometer after minus odometer before, same vehicle.'));
 const w=deliveryWindow('Cash > Expenses',cashMenu);w.body.appendChild(c);const m={close:w.close};const refresh=()=>{m.close();expenseLedger();};
 toolbar.append(expButton('Add entry',()=>expenseEntry(null,refresh),true),expButton('Expense settings',()=>expenseSettings(refresh)),expButton('Review conflicts',()=>financeConflicts(refresh)),expButton('Refresh',refresh));
}
function expenseSettings(done) {
 const c=el('div');c.appendChild(el('h2',null,'Expense settings'));
 c.appendChild(el('p','hint','Settings keep their dated history. A new opening balance resets the calculation from its effective date; it is not a cash receipt. Fuel price changes never rewrite old entries.'));
 const g=el('div','mgrid');c.appendChild(g);
 const key=expField(g,'Setting','key','fuel_price','text',['fuel_price','opening_balance','currency']);
 const val=expField(g,'Value','value','20.50');const defaults={fuel_price:'20.50',currency:'EGP',opening_balance:''};key.onchange=()=>{val.value=defaults[key.value]??''};c.insertBefore(el('p','hint','Fuel price per liter starts at 20.50 EGP (built-in). Change it here: the new price applies from the date you choose and old entries are never rewritten.'),g);const date=expField(g,'Effective from (YYYY-MM-DD)','effective_from',new Date().toLocaleDateString('en-CA'),'date');
 const requestId=crypto.randomUUID();const buttons=el('div','mrow');c.appendChild(buttons);const m=modal(c,'600px');
 buttons.append(expButton('Cancel',m.close),expButton('Save setting',async()=>{
  if(key.value==='opening_balance'&&!await askBox('Opening balance','This resets the calculated cash balance from the effective date. Save this opening balance?'))return;
  const r=await api('/api/exp/setting',{key:key.value,value:val.value,effective_from:date.value,request_id:requestId});if(!r.ok)return msgBox('Expense settings',r.msg,true);m.close();done();
 },true));
}
function expenseEntry(entry,done) {
 const e=entry||{},c=el('div');c.appendChild(el('h2',null,entry?'Edit entry (new revision)':'Add cash / expense entry'));
 c.appendChild(el('p','hint','Receipt adds cash; expense and cash returned reduce cash. Driver and vehicle do not create separate balances.'));
 const g=el('div','mgrid');c.appendChild(g);const fields={};
 const add=(label,key,type='text',choices=null)=>fields[key]=expField(g,label,key,e[key]||(key==='entry_date'?new Date().toLocaleDateString('en-CA'):''),type,choices);
 add('Kind','kind','text',['expense','receipt','return']);add('Date','entry_date','date');add('Amount','amount');add('Category (Fuel for fuel entries)','category');add('Driver','driver');add('Vehicle','vehicle');add('Odometer (km)','odometer');
 const previousKm=el('p','hint','Previous km: choose a vehicle.');g.appendChild(previousKm);previousKm.style.cssText='grid-column:1 / -1;font-weight:600';
 const updateKm=async()=>{const r=await api('/api/exp/ledger');const rows=(r.entries||[]).filter(x=>x.vehicle===fields.vehicle.value.trim()&&x.entry_id!==e.entry_id&&x.entry_date<=fields.entry_date.value&&String(x.odometer||'').trim());rows.sort((a,b)=>a.entry_date.localeCompare(b.entry_date)||a.at-b.at);const old=rows.length?rows[rows.length-1].odometer:null;const now=Number(fields.odometer.value);previousKm.textContent=old===null?'Previous km: no earlier reading for this vehicle.':'Previous km: '+old+' km'+(fields.odometer.value?(now>Number(old)?' | Distance: '+(now-Number(old))+' km':' | Check: new km must exceed previous reading for a valid distance.'):'');};
 for(const i of [fields.vehicle,fields.entry_date,fields.odometer])i.addEventListener('input',updateKm);updateKm();add('Place / merchant','place');add('Payment method','payment_method');fields.payment_method.value='Cash';fields.payment_method.readOnly=true;add('Receipt / reference','receipt_ref');add('How / why (notes)','note');
 const fuel=el('div');fuel.style.cssText='border-top:1px solid var(--line);margin-top:12px;padding-top:12px';fuel.appendChild(el('h3',null,'Fuel details'));const fg=el('div','mgrid');fuel.appendChild(fg);c.appendChild(fuel);
 for(const [label,key]of [['Price per liter (blank = dated Settings price)','fuel_price'],['Liters on receipt (optional)','liters_receipt']])fields[key]=expField(fg,label,key,e[key]||'');
 const accept=el('input');accept.type='checkbox';accept.disabled=true;const al=el('label');al.append(accept,el('span',null,' I confirm use of the Settings price effective on the entry date if price is blank.'));fuel.appendChild(al);
 fields.entry_date.onchange=()=>{accept.checked=false;accept.disabled=true;};
 fuel.appendChild(el('p','hint','Vehicle and odometer are required for fuel. The price is saved per entry. Liters bought are not fuel burned.'));
 let reason=null;if(entry)reason=expField(c,'Reason for change (required)','reason');
 const request=crypto.randomUUID();const row=el('div','mrow');c.appendChild(row);const m=modal(c,'780px');m.ov.dataset.dismiss='no';
 const cancel=async()=>{if(await askBox('Discard entry','Close without saving these entry fields?'))m.close();};m.ov._homeExit=()=>{cancel();return false;};
 row.append(expButton('Cancel',cancel),expButton(entry?'Save revision':'Save entry',async()=>{
  const v=Object.fromEntries(Object.entries(fields).map(([k,i])=>[k,i.value]));v.accept_default=accept.checked;
  const r=await api(entry?'/api/exp/edit':'/api/exp/add',{entry:v,entry_id:e.entry_id,expected:e.revision_ids,request_id:request,reason:reason?reason.value:''});
  if(!r.ok){if((r.msg||'').includes('Settings price')&&(r.msg||'').includes('Confirm')){accept.disabled=false;al.lastChild.textContent=' '+r.msg;accept.checked=false;}return msgBox('Expense entry',r.msg||'Not saved.',true);}m.close();done();
 },true));
}
function expenseVoid(e,done){
 const c=el('div');c.appendChild(el('h2',null,'Void entry'));c.appendChild(el('p',null,`${e.entry_date}: ${e.kind} ${e.amount}. A void revision keeps the original history.`));const reason=expField(c,'Reason (required)','reason');const row=el('div','mrow');c.appendChild(row);const m=modal(c,'500px');row.append(expButton('Cancel',m.close),expButton('Void entry',async()=>{const r=await api('/api/exp/void',{entry_id:e.entry_id,expected:e.revision_ids,request_id:crypto.randomUUID(),reason:reason.value});if(!r.ok)return msgBox('Void entry',r.msg,true);m.close();done();}));
}
async function expenseHistory(id){const r=await api('/api/exp/history',{entry_id:id});if(!r.ok)return msgBox('Entry history',r.msg,true);const c=el('div');c.appendChild(el('h2',null,'Entry revision history'));for(const e of r.revisions)c.appendChild(el('p',null,`Revision ${e.rev||e.operation.slice(0,8)}: ${e.entry_date}, ${e.kind}, ${e.amount}, ${e.category}, ${e.driver||'-'} / ${e.vehicle||'-'}${e.voided?' [VOIDED]':''}. By ${e.by_user}: ${e.reason}`));const m=modal(c,'700px');c.appendChild(expButton('Close',m.close));}

async function financeConflicts(done){
 const r=await api('/api/finance/conflicts');if(!r.ok)return msgBox('Conflicts',r.msg||'Unavailable',true);
 const c=el('div');c.append(el('h2',null,'Conflict Expenses'),el('p','hint','Nothing is changed or deleted automatically. Each item shows what the entry was, what it became and what happened. Every version stays in history.'));
 const fmt=v=>v===undefined||v===null||v===''?'(empty)':String(v);const when=t=>t?new Date(t*1000).toLocaleString():'-';
 let m=null;
 const FIELDS=v=>v.key?[['Setting',v.key],['Value',v.value],['Effective',v.effective_from]]:v.state!==undefined&&!v.kind?[['Choice',v.state]]:[['Date',v.entry_date],['Kind',v.kind],['Amount',v.amount],['Category',v.category],['Driver',v.driver],['Vehicle',v.vehicle],['Place',v.place],['Payment method',v.payment_method],['State',v.voided?'VOIDED':'Active'],['Note',v.note],['Reason',v.reason]];
 for(const conflict of r.conflicts){
  const vs=[...conflict.versions].sort((x,y)=>(x.value.at||0)-(y.value.at||0));const was=vs[0],became=vs[vs.length-1];
  const kind=conflict.entity.startsWith('mark:')?'Collection mark':conflict.entity.startsWith('setting:')?'Expense settings':'Expense entry';
  const box=el('div');box.style.cssText='border:1px solid var(--line);border-radius:10px;padding:12px;margin:12px 0';
  const bv=became.value;box.append(el('h3',null,kind+(bv.category?' | '+bv.category:'')+(bv.entry_date?' | '+bv.entry_date:'')));
  const what=el('p',null,'What happened: Two PCs changed this '+kind.toLowerCase()+' at the same time from the same earlier version. Both versions are saved here. The cash total stays unknown until you choose.');what.style.fontWeight='600';box.append(what);
  box.append(el('p','hint','Was: by '+was.actor+' | Became: by '+became.actor+(bv.at?' | latest saved '+when(bv.at):'')));
  const keys=[...new Set([...FIELDS(was.value),...FIELDS(became.value)].map(x=>x[0]))];const gv=(o,k)=>{const f=FIELDS(o.value).find(x=>x[0]===k);return f?fmt(f[1]):'(empty)'};
  const diff=keys.filter(k=>gv(was,k)!==gv(became,k));
  box.append(el('p',null,diff.length?diff.length+' field(s) differ':'The content is the same; only the sender differs.'));
  const t=el('table','gtab');t.style.width='100%';const hd=el('tr');for(const h of ['Field','Was (other version)','Became (latest version)'])hd.append(el('th',null,h));
  const rows=all=>{t.replaceChildren(hd);for(const k of all?keys:diff){const tr=el('tr');const f=el('th',null,k),a=el('td',null,gv(was,k)),b2=el('td',null,gv(became,k));f.style.textAlign='left';if(diff.includes(k)){a.style.cssText='background:#fee2e2;font-weight:700';b2.style.cssText='background:#dcfce7;font-weight:700'}for(const z of [a,b2])z.style.whiteSpace='normal';tr.append(f,a,b2);t.append(tr)}};rows(false);
  const more=el('button','btn','Show all fields');let all=false;more.onclick=()=>{all=!all;rows(all);more.textContent=all?'Show only differences':'Show all fields'};box.append(t,more);
  const bar=el('div');bar.style.cssText='display:flex;gap:10px;flex-wrap:wrap;margin-top:12px';
  const pick=async(o,msg)=>{if(!await askBox('Resolve conflict',msg))return;const result=await api('/api/finance/resolve',{entity:conflict.entity,pick:o.id,expected:conflict.heads,request_id:crypto.randomUUID()});if(!result.ok)return msgBox('Conflict',result.msg,true);m.close();financeConflicts(done)};
  const amt=o=>o.value.amount?' ('+o.value.amount+')':'';
  const kb=el('button','btn accent','Keep Became'+amt(became)),kw=el('button','btn','Keep Was'+amt(was));
  kb.onclick=()=>pick(became,'Keep the Became version? The other version stays in history.');kw.onclick=()=>pick(was,'Keep the Was version? The other version stays in history.');
  const sk=el('button','btn','Skip');sk.dataset.conflictSkip=conflict.entity;sk.onclick=()=>{box.replaceChildren(el('h3',null,'Conflict skipped for now'),el('p','hint','Both versions remain unchanged. Reopen to decide later.'))};
  const isEntry=kind==='Expense entry';const rj=el('button','btn danger',isEntry?'Reject (void this entry)':'Reject');rj.disabled=!isEntry||!!conflict.pending_parent;if(!isEntry)rj.title='Not available for settings and collection marks. Use Keep Became, Keep Was or Skip.';
  rj.onclick=async()=>{if(!await askBox('Reject','Reject this entry? It is marked VOIDED and is not counted in cash. Every version stays in history.'))return;const result=await api('/api/finance/reject',{entity:conflict.entity,expected:conflict.heads,request_id:crypto.randomUUID()});if(!result.ok)return msgBox('Conflict',result.msg||'Not saved',true);m.close();financeConflicts(done)};
  if(conflict.pending_parent)box.append(el('p',null,'Waiting for missing revisions. Restore or receive them before resolving.'));else bar.append(kb,kw);
  bar.append(rj,sk);box.append(bar);c.append(box)}
 if(!r.conflicts.length)c.append(el('p',null,'No conflicts.'));
 const cl=el('button','btn','Close');c.append(cl);m=modal(c,'1100px');cl.onclick=m.close;
}
