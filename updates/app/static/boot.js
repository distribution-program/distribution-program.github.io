/* Distribution Program boot: login, menus, theme, live status. Designed & developed by Eng. Kirollos William (c) 2026 */
"use strict";

function refreshCurrent() {
  if(typeof DELIVERY_REFRESH!=="undefined"&&DELIVERY_REFRESH){if(!$("#modal-root .overlay"))void DELIVERY_REFRESH();return;}
  if(S.cur==="home"&&!document.querySelector(".delivery-window")){buildHome();return;}
  if(typeof detGrid!=="undefined"&&detGrid?.editing)return;
  const k = S.cur;
  if (k === "details" || k.startsWith("s:")) fillDetails();
  else if (k.startsWith("rep:")) fillRoute();
  else if (k === "rgr") fillRgr();
  else if (k === "wh") { whShow(); piShow(); }
}

/* ---------------- login ---------------- */
let LG_USERS = [];
async function switchUser() {
  await fetch("/api/logout", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
  LG_USERS = ["Admi1", "Guest"].filter(x => x !== "Guest");
  $("#lg-err").textContent = ""; $("#lg-pass").value = "";
  showLogin();
}
function showLogin() {
  $("#app").classList.add("hidden");
  $("#login").classList.remove("hidden");
}
function initLogin() {
  const u = autoCombo({ getvals: () => LG_USERS, fullList: true, placeholder: "User" });
  $("#lg-user").appendChild(u.input.parentElement);
  u.input.style.width = "100%";
  const go = async () => {
    $("#lg-err").textContent = "";
    try {
      const r = await fetch("/api/login", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user: u.val().trim(), pw: $("#lg-pass").value }) }).then(r => r.json());
      if (r.ok) { $("#lg-pass").value = ""; boot(); }
      else $("#lg-err").textContent = r.msg || "Wrong user or password";
    } catch (e) { $("#lg-err").textContent = "Connection problem"; }
  };
  $("#lg-go").onclick = go;
  $("#lg-pass").addEventListener("keydown", e => { if (e.key === "Enter") go(); });
}

/* ---------------- boot after login ---------------- */
async function boot() {
  const st = await fetch("/api/state").then(r => r.json());
  if (!st.ok) return showLogin();
  Object.assign(S, {
    user: st.user, permissions:st.permissions, isAdmin:st.is_admin, fbTools:st.fb_tools,  testMode: st.test_mode, trialLimit: st.trial_limit, customerMode: !!st.customer_mode, financeEnabled:st.finance_enabled,financeSync:st.finance_sync, cols: st.cols, base: st.base, editable: st.editable, locked: st.locked,
    statuses: st.statuses, lists: st.lists, cdMap: st.cd_map, listFields: st.list_fields,
    dateCols: new Set(st.date_cols), rgrCols: st.rgr_cols, repCols: st.rep_cols,
    exempt: new Set(st.exempt), bulkFields: st.bulk_fields, required: st.required,
    forwardTo: st.forward_to, invoiceType: st.invoice_type, paymentTerms: st.payment_terms, listNames: st.list_names,
  });
  document.body.className = st.mode === "dark" ? "dark" : "light";
  $("#userlbl").textContent = st.trial_limit ? (st.user + (st.lic && st.lic.licensed ? " | Licensed" : " | Trial")) : st.user + (st.connected_test?.replica ? " · REPLICA" : " · MAIN");
  document.querySelector('#connected-test-banner')?.remove();

  document.title = `${st.connected_test?.replica ? "REPLICA" : "MAIN"} | ${st.test_mode && !(st.lic && st.lic.licensed) ? "ISOLATED TRIAL | " : ""}${st.title} - ${st.user}`;
  if (st.test_mode) {
    const banner = el("div", null, st.trial_limit ? "TRIAL VERSION: " + st.trial_limit + " operations in total (each add, edit, delete or PDF print click). Data stays on this PC. Use Quit to stop." : st.trial_printing ? "PRINT-ENABLED ISOLATED TRIAL: dummy data only. Real Windows default-printer output is enabled and uses paper/ink. Firebase, real shared folders and restore stay disabled. Use Quit to stop." : "ISOLATED TRIAL: dummy data only. Firebase, real shared folders, restore and printers are disabled. Use Quit to stop this trial. Normal work uses the MAIN or REPLICA program and your existing profile.");
    banner.style.cssText = "background:#fff0b3;color:#392c00;padding:2px 10px;font-weight:700;font-size:11px;line-height:1.3;text-align:center;white-space:nowrap;overflow:hidden;text-overflow:ellipsis";
    
  }
  let visual={};try{visual=JSON.parse(localStorage.getItem('v36_visual_options')||'{}');}catch(e){}
  document.querySelector('.live-bars').style.display=visual.bars===false?'none':'';{const rb=document.getElementById('receive-bar');if(rb)rb.style.display=visual.bars===false?'none':''}
  $("#t-back").style.display=visual.back===false?'none':'';
  $("#foot-left").textContent = `${st.title}   ${st.version}${st.test_mode && !(st.lic && st.lic.licensed) ? (st.trial_limit ? " | TRIAL VERSION" : " | ISOLATED TRIAL - NOT COMPANY DATA") : ""}`;
  $("#foot-right").textContent = st.credit + "   |   " + st.signature;
  initV54Chrome();notifyRefresh();
  await initDrafts();
  buildSidebar();
  buildHome();
  if (!window._inited) {
    initDetails(); initRgr(); initNew(); initReport(); initHo(); initWh(); initMenus();
    window._inited = true;
  }
  $("#login").classList.add("hidden");
  $("#app").classList.remove("hidden");
  if (st.test_mode) {
    
  }
  { const sw = $("#t-switch"); if (sw) { sw.classList.toggle("hidden", !st.trial_limit); sw.onclick = switchUser; } }
  DATA_V = -1;
  go("home");
  restoreNewDraft();showDraftRecovery();
}

/* ---------------- menus / dialogs ---------------- */
function initMenus() {
  document.querySelectorAll("[data-go]").forEach(b => b.onclick = () => go(b.dataset.go));
  $("#t-menu").onclick = () => $("#sidebar").classList.toggle("hidden");
  $("#t-home").onclick = returnHome;
  $("#usage-settings").onclick = async () => {
    const st=await fetch('/api/status').then(x=>x.json()),p=st.project_usage,box=el('div');box.appendChild(el('h2',null,'Project usage'));
    box.appendChild(el('p','hint','Automatic: reads Cloud Monitoring every 5 minutes with your existing key, if permitted. Nothing to enter. Whole project includes MAIN + REPLICA and other clients. Can lag 4 minutes or longer; may differ from Firebase console and billing. No guaranteed percentage accuracy.'));
    box.appendChild(el('p','hint',p.error||'Monitoring access available.'));
    const y=p.data?.yesterday;box.appendChild(el('p','hint',y?`Yesterday (${y.day}, Pacific): Reads ${y.reads}, Writes ${y.writes}, Deletes ${y.deletes}. Separate from today.`:'Yesterday: unavailable.'));
    box.appendChild(el('p','hint','Manual fallback only: use whole-number Reads/Writes/Deletes from Firebase Usage for TODAY since midnight Pacific, not Last 24 hours. Enter the source as-of time with timezone. Never add yesterday. This baseline plus later activity on this device misses other devices and is only an estimate.'));
    const form=el('div','usage-form'),inputs={};for(const key of ['reads','writes','deletes','as_of']){const label=el('label',null,key==='as_of'?'Source as-of (ISO + timezone)':key);const input=el('input','in');input.placeholder=key==='as_of'?'2026-11-24T14:00:00+02:00':'whole-number count';if(p.manual?.[key])input.value=key==='as_of'?new Date(p.manual[key]*1000).toISOString():p.manual[key];label.appendChild(input);form.appendChild(label);inputs[key]=input;}box.appendChild(form);
    const save=el('button','btn accent','Save manual baseline'),close=el('button','btn','Close');box.append(save,close);const m=modal(box,'900px');close.onclick=m.close;save.onclick=async()=>{const values=Object.fromEntries(Object.entries(inputs).map(([k,v])=>[k,v.value]));const answer=await api('/api/usage/baseline',values);if(!answer.ok)return msgBox('Not saved',answer.msg,true);m.close();};
  };
  if($("#receive-history")) $("#receive-history").onclick = async () => {
    const r=await fetch("/api/status").then(x=>x.json());const box=el("div");box.appendChild(el("h2",null,"Receive history"));
    box.appendChild(el("p","hint","Latest 50 successful receive batches on this device. Empty checks and initial sync are not changes. No history exists before this version was installed."));
    plainTable(box,["Received","Source","Add","Edit","Delete"],(r.received.history||[]).map(x=>[new Date(x.at*1000).toLocaleString(),x.source,x.new,x.updated,x.deleted]));
    const close=el("button","btn","Close");box.appendChild(close);const m=modal(box,"850px");close.onclick=m.close;
  };
  $("#t-back").onclick = async () => {
    for(const ov of [...document.querySelectorAll("#modal-root > .overlay")].reverse())if(ov._homeExit&&!(await ov._homeExit()))return;
    const previous=NAV_HISTORY.pop();if(!previous)return;
    NAV_BACK=true;try{go(previous);}finally{NAV_BACK=false;}
  };

  $("#t-back").after($("#t-home"));
  $("#home-rail")?.remove();
  const syncButton=$("#t-refresh");if(syncButton){syncButton.textContent="Sync Now (F5)";syncButton.dataset.en="Sync Now (F5)";}
  $("#t-shortcut").onclick = async () => { const r = await api("/api/desktop/shortcut"); msgBox("Desktop icon", r.msg || "", !r.ok); };
  $("#t-quit").onclick = async () => {
    if(FULL_IMPORT_BUSY||SIMPLE_IMPORT_BUSY)return msgBox("Quit","An import is still running. Wait for its result before closing.",true);
    if([...document.querySelectorAll(".overlay")].some(n=>n._unsavedChanges?.()))return msgBox("Quit","This plan has unsaved marks/status choices. Save it, or return Home and explicitly discard it, before Quit.",true);
    document.activeElement?.blur();await new Promise(r=>setTimeout(r,500));await draftQueue;
    if(!(await askBox("Sync and Quit","Save complete invoices before quitting. New/classification input recovery stays local and is not a completed synced invoice. Run Sync Now, then stop only after pending publication finishes?")))return;
    const c=el("div");c.appendChild(el("h2",null,"Sync and Quit"));const text=el("p","hint","Checking pending data...");c.appendChild(text);const wait=modal(c,"560px");wait.ov.dataset.dismiss="no";
    let result=await api("/api/app/exit/start");
    while(result.state==="running"){text.textContent=result.msg;await new Promise(r=>setTimeout(r,500));result=await api("/api/app/exit/status");}
    wait.close();
    if(result.state==="trial_local_only"){if(!(await askBox("Trial only",result.msg+" Stop this isolated trial?")))return;}
    else if(result.state!=="ready")return msgBox("Program stays open",result.msg||"Sync completion not confirmed.",true);
    const r=await api("/api/app/quit");if(r.ok)document.body.replaceChildren(el("div","stopped",T("Distribution Program stopped. You can close this window. Open the desktop icon to start again.")));
  };
  $("#t-refresh").onclick = doSync;
  $("#t-theme").onclick = async () => {
    const dark = !document.body.classList.contains("dark");
    document.body.className = dark ? "dark" : "light";
    buildSidebar(); markSide(S.cur);
    await api("/api/theme", { mode: dark ? "dark" : "light" });
  };
  document.querySelectorAll("[data-menu]").forEach(b => b.onclick = e => {
    e.stopPropagation();
    const m = $("#" + b.dataset.menu);
    const was = m.classList.contains("hidden");
    document.querySelectorAll(".menu").forEach(x => x.classList.add("hidden"));
    if (was) m.classList.remove("hidden");
  });
  document.addEventListener("click", () => document.querySelectorAll(".menu").forEach(x => x.classList.add("hidden")));
  document.querySelectorAll("[data-act]").forEach(b => b.onclick = () => doAct(b.dataset.act));
  $("#t-settings").onclick = settingsModal;
  document.addEventListener("keydown", e => {
    if (e.key === "F5") { e.preventDefault(); doSync(); }
  });
}
async function doSync() {
  const r = await api("/api/sync"); toast("Sync requested (F5). Waiting for the cloud...");
  let st = {};
  for (let i = 0; i < 90; i++) {
    await new Promise(x => setTimeout(x, 1000));
    st = await api("/api/sync/status");
    if (!st.configured) { toast("Cloud is not connected on this PC."); return; }
    if (st.pull_seq > r.seq) { toast("Cloud read finished at " + new Date(st.pulled_at * 1000).toLocaleTimeString() + (st.pull_kept_local ? `. ${st.pull_kept_local} invoice(s) were left as on this PC (unsent or newer local edit).` : ".") + (st.pending ? ` ${st.pending} local change(s) not uploaded yet.` : "")); return; }
  }
  toast("Cloud did not answer yet" + (st.error ? " (" + st.error + ")" : "") + ". Local data is unchanged. It retries automatically.");
}


async function cashReview() {
 const r=await api("/api/review/cash");if(!r.ok)return msgBox("Cash review",r.msg||"Could not load.",true);
 const c=el("div");c.appendChild(el("h2",null,"Cash invoices: manual collection marks"));
 c.appendChild(el("p","hint",`${r.candidates} cash invoices, all types and statuses. Full invoice row through Payment Terms. Scroll horizontally for every column.`));
 const warn=el("p","hint",!S.financeEnabled?"Read-only receipt review. Collection marking is not activated.":S.testMode?"FICTIONAL PROFILE ONLY: marks are saved locally with revision history and included in Backup / Load backup. No live sync yet. Marks do not post cash or change invoices.":"Collection marks retain revision history, sync through the approved finance service and are included in Backup / Load backup. Marks do not post cash or change invoices. Server confirmation does not prove another PC received them.");warn.style.color="#b45309";c.appendChild(warn);
 if(!S.financeEnabled)c.appendChild(el("p","hint","Receipt review is read-only. Manual Collected / Not yet marks are unavailable until finance sync is activated."));
 const reviewButton=el("button","btn","Missing / unclear receipt references ("+r.to_review+")");
 reviewButton.onclick=()=>{const detail=el("div");detail.append(el("h2",null,"Cash receipt reference review"),el("p","hint","All cash invoices, any type or status. Receipt wording is only a possible reference, never proof of payment. This review changes nothing."));const list=el("div");list.style.cssText="max-height:52vh;overflow-y:auto;overflow-x:hidden";detail.append(list);const table=el("table","gtab");table.style.cssText="width:100%;table-layout:fixed";const heads=el("tr");for(const label of ["Invoice Number","Date","Reason to review","Remarks"])heads.append(el("th",null,label));table.append(heads);for(const row of r.rows||[]){const tr=el("tr");for(const value of [row.invoice,row.date,row.reason,row.remarks]){const td=el("td",null,value);td.style.cssText="white-space:normal;overflow-wrap:anywhere";tr.append(td);}table.append(tr);}list.append(table);if(r.to_review>(r.rows||[]).length)detail.append(el("p","hint","Showing "+r.rows.length+" of "+r.to_review+" references needing review. More results exist; narrow the source data for a complete review."));const back=el("button","btn","Back");detail.append(back);const box=modal(detail,"95vw");back.onclick=box.close;};c.append(reviewButton);
 const wrap=el("div");wrap.style.cssText="max-height:60vh;overflow:auto;direction:ltr";c.appendChild(wrap);
 const t=el("table","gtab");t.classList.add("cash-compact");t.style.cssText="width:max-content;direction:ltr";const h=el("tr");for(const col of ["Collection / manual choice",...r.table_columns]){const th=el("th",null,col==="Collection / manual choice"?"Collection":col);if(col==="Collection / manual choice")th.style.cssText="position:sticky;left:0;background:var(--panel);z-index:2;width:1px;white-space:nowrap";h.appendChild(th);}t.appendChild(h);
 for(const x of r.table_rows||[]){const tr=el("tr");for(const v of x.values)tr.appendChild(el("td",null,v));
  const td=el("td");td.style.cssText="position:sticky;left:0;background:var(--panel);z-index:1;width:1px;white-space:nowrap;border-left:2px solid var(--line)";let mark=x.manual_mark||{state:"unmarked",heads:[]};const requestIds={};const state=el("span",null,"");state.style.cssText="font-size:11px;margin-right:4px";td.appendChild(state);
  for(const [label,value]of [["Collected","Collected"],["Not yet","Not yet"]]){const btn=el("button","btn accent",label);btn.style.cssText="display:inline-block;font-size:11px;padding:1px 7px;min-height:21px;margin:0 2px;line-height:17px;vertical-align:middle";btn.disabled=!S.financeEnabled;btn.onclick=async()=>{const chosen=value==="Collected"?"collected":"not_yet";if(!requestIds[chosen])requestIds[chosen]=crypto.randomUUID();const result=await api("/api/finance/mark",{uid:x.uid,state:chosen,expected:mark.heads,request_id:requestIds[chosen]});if(!result.ok)return msgBox("Collection mark",result.msg||"Not saved.",true);for(const k of Object.keys(requestIds))delete requestIds[k];await refreshMark();};td.appendChild(btn);}async function refreshMark(){const data=await api("/api/review/cash");const updated=data.table_rows.find(row=>row.uid===x.uid);mark=updated.manual_mark;paint();}
  function paint(){td.querySelectorAll("button").forEach(b=>{const chosen=b.textContent==="Collected"?"collected":"not_yet";b.style.opacity=mark.state==="unmarked"?"1":mark.state===chosen?"1":"0.45";b.setAttribute("aria-pressed",mark.state===chosen?"true":"false");});td.title=mark.state;state.textContent=mark.state==="conflict"?"CONFLICT":"";}paint();tr.insertBefore(td,tr.firstChild);t.appendChild(tr);
 }
 wrap.appendChild(t);const b=el("button","btn","Close");c.appendChild(b);const m=modal(c,"1260px");b.onclick=m.close;
}

function doAct(a) {
  if (a === "users") return usersModal();
  if (a === "backup-now") return api("/api/backup/now").then(r => msgBox("Backup", r.msg || "", !r.ok));
  if (a === "backup-load") return loadBackup();
  if (a === "share") return shareModal();
  if (a === "sync") return doSync();
  if (a === "import-full") return importFull();
  if (a === "cash-review") return cashReview();
  if (a === "import-lists") return listsModal();
  if (a === "about") return msgBox("About", `${S.user ? "Distribution Program" : ""} ${$("#foot-left").textContent}\n${$("#foot-right").textContent}`);
}
async function loadBackup() {
  const f = await pickFile(".json");
  if (!f) return;
  const r = await api("/api/backup/load", { file: await fileB64(f) });
  msgBox("Backup", r.msg || "", !r.ok);
  refreshCurrent();
}
let SIMPLE_IMPORT_BUSY = false;
async function showImportReceipt(kind, title) {
  const answer = await api("/api/import/status", {kind}); const r = answer.receipt;
  msgBox(title, r ? `${r.started} | ${r.state}\n${r.result ? r.result.msg : "This import has not reported completion. Do not repeat it until its outcome is checked."}\nReference: ${r.request_id}` : "No import of this type has been recorded by this version.");
}
async function importReportExcel(title, kind, after) {
  if (SIMPLE_IMPORT_BUSY || FULL_IMPORT_BUSY) return;
  SIMPLE_IMPORT_BUSY = true;
  let progress = null;
  try {
    const f = await pickFile(".xlsx,.xlsm"); if (!f) return;
    clearTimeout(toastT); $("#toast").classList.add("hidden");
    const c = el("div"); c.appendChild(el("h2", null, title)); c.appendChild(el("p", "hint", f.name));
    c.appendChild(el("div", "import-progress"));
    c.appendChild(el("p", "hint", "Reading the workbook and saving locally. Keep this window open and do not repeat the import."));
    progress = modal(c, "560px"); progress.ov.dataset.dismiss="no";
    const request_id=Date.now().toString(36)+"_"+Math.random().toString(36).slice(2);
    const r=await api("/api/import/"+kind,{file:await fileB64(f),request_id});
    progress.close();progress=null;
    let note="";
    if(r.ok){ try { await after(); } catch(e) { note="\nThe import returned a result, but refreshing this view failed. Use Last import result before retrying."; } }
    msgBox(title + " result", (r.msg||"No result details returned.")+note+(r.request_id?"\nReference: "+r.request_id:""),!r.ok);
  } catch(e) {
    if(progress){progress.close();progress=null;}
    if(!e.auth)msgBox(title + " result", "The local program did not return a readable result. The outcome is NOT confirmed. Do not repeat the file yet. Check its last import result in Settings.",true);
  } finally {
    if(progress)progress.close();SIMPLE_IMPORT_BUSY=false;
    clearTimeout(toastT);$("#toast").classList.add("hidden");
  }
}
let FULL_IMPORT_BUSY = false;
async function lastFullImport() {
  const answer = await api("/api/import/full/status");
  const r = answer.receipt;
  msgBox("Last full import result", r ? `${r.started} | ${r.state}\n${r.result ? r.result.msg : "The last import has not reported completion. Do not repeat it until its outcome is checked."}\nReference: ${r.request_id}` : "No full import has been recorded by this version.");
}
function syncLine(st) {
  if (!st.configured) return "Cloud is not connected on this PC. Changes stay on this PC.";
  const bt = st.batch;
  const at = st.pushed_at ? " at " + new Date(st.pushed_at * 1000).toLocaleTimeString() : "";
  if (bt) {
    if (bt.total && bt.written === bt.total) return `Uploaded to the cloud (${bt.written} of ${bt.total} invoices)${at}. Another PC gets it when it presses F5 or while its app is connected. Not confirmed received.`;
    const parts = [];
    if (bt.waiting) parts.push(`${bt.waiting} still waiting to upload`);
    if (bt.server_newer) parts.push(`${bt.server_newer} NOT uploaded: the cloud already had a newer copy`);
    if (bt.deleted_elsewhere) parts.push(`${bt.deleted_elsewhere} NOT uploaded: deleted on another device`);
    if (bt.removed_locally) parts.push(`${bt.removed_locally} no longer on this PC`);
    return `Saved on this PC. Uploaded ${bt.written} of ${bt.total}. ` + parts.join("; ") + "." + (st.error ? " Last cloud problem: " + st.error + ". It retries." : "");
  }
  return st.pending > 0 ? `${st.pending} invoice(s) on this PC are not uploaded yet.` : "Nothing waiting to upload.";
}
async function waitUpload(box, batch, secs) {
  for (let i = 0; i < secs; i++) {
    const st = await api("/api/sync/status", {batch});
    box.textContent = syncLine(st);
    if (!st.configured || !st.batch || st.batch.waiting === 0) return st;
    await new Promise(r => setTimeout(r, 1000));
  }
}
const RED = "2px solid #d33";
function reviewDialog(item, st) {
  // Opens one invoice like the New Invoice screen. Red = needs a decision. Under it: what the Excel sheet says.
  return new Promise(res => {
    const c = el("div"); c.appendChild(el("h2", null, `Row ${item.row} | ${item.invoice}`));
    const isNew = item.kind === "new";
    c.appendChild(el("p", "hint", isNew ? "New invoice. Red fields have a problem. Correct the value, or skip this row." : "Invoice already in the program. Red fields differ from the Excel sheet. Nothing changes unless you choose Use Excel."));
    if (item.locked) c.appendChild(el("p", "hint", item.locked + " It cannot be updated until the upload finishes."));
    const cur = st.get(item.row) || (isNew ? {fields: {}, skip: false} : {changes: {}, reason: ""});
    const grid = el("div"); grid.style.cssText = "display:grid;grid-template-columns:1fr 1fr;gap:10px 16px;max-height:420px;overflow:auto;padding:4px";
    const inputs = {}, choices = {};
    const flagged = new Map(item.fields.map(f => [f.name, f]));
    const allf = (item.context || item.fields).map(x => flagged.get(x.name) || x);
    for (const f of allf) {
      const flag = flagged.has(f.name);
      const box = el("div"); box.appendChild(el("label", null, f.name));
      const inp = el("input"); inp.style.cssText = "width:100%;box-sizing:border-box";
      if (isNew) { inp.value = cur.fields[f.name] ?? f.value; inputs[f.name] = inp; if (!flag) inp.readOnly = true; }
      else { inp.value = f.current; inp.readOnly = true; }
      if (flag) inp.style.border = RED;
      box.appendChild(inp);
      if (flag) {
        const note = el("div", "hint"); note.style.cssText = "font-size:12px;color:#b00020";
        note.textContent = `Excel sheet says: ${f.excel === "" ? "(empty)" : f.excel}` + (f.problem ? "  |  " + f.problem : "");
        box.appendChild(note);
        if (!isNew) {
          if (f.protected) box.appendChild(el("div", "hint", "Protected: " + f.protected));
          else {
            const sel = el("select");
            for (const [v, t2] of [["keep", "Keep current"], ["excel", f.excel_blank ? "Use Excel (empties this field)" : "Use Excel value"]]) { const o = el("option", null, t2); o.value = v; sel.appendChild(o); }
            sel.value = f.name in cur.changes ? "excel" : "keep";
            if (f.problem || item.locked) { sel.disabled = true; }
            choices[f.name] = sel; box.appendChild(sel);
          }
        }
      }
      grid.appendChild(box);
    }
    c.appendChild(grid);
    let reason = null;
    if (!isNew && item.fields.some(f => f.name === "Invoice Status" && f.excel === "Cancelled")) {
      reason = el("input"); reason.placeholder = "Reason (needed if you choose Cancelled)"; reason.value = cur.reason || ""; reason.style.width = "100%"; c.appendChild(reason);
    }
    let skip = null;
    if (isNew) { const l = el("label"); skip = el("input"); skip.type = "checkbox"; skip.checked = !!cur.skip; l.appendChild(skip); l.appendChild(document.createTextNode(" Skip this row (do not import it)")); c.appendChild(l); }
    const bar = el("div"); bar.style.marginTop = "10px";
    const ok = el("button", "tb", "Remember my choices for this invoice (nothing is imported yet)"), no = el("button", "tb ghost", "Back");
    bar.appendChild(ok); bar.appendChild(no); c.appendChild(bar);
    const m = modal(c, "820px"); m.ov.dataset.dismiss = "no";
    ok.onclick = () => {
      if (isNew) {
        const fields = {}; for (const f of item.fields) if (inputs[f.name] && inputs[f.name].value !== f.value) fields[f.name] = inputs[f.name].value;
        st.set(item.row, {fields, skip: skip.checked, item});
      } else {
        const changes = {}, expect = {};
        for (const f of item.fields) if (choices[f.name] && choices[f.name].value === "excel") { changes[f.name] = f.excel; expect[f.name] = f.current; }
        if (Object.keys(changes).length) st.set(item.row, {changes, expect, reason: reason ? reason.value : "", item}); else st.delete(item.row);
      }
      m.close(); res(true);
    };
    no.onclick = async () => {
      let dirty = false;
      if (isNew) { for (const f of item.fields) if (inputs[f.name] && inputs[f.name].value !== (cur.fields[f.name] ?? f.value)) dirty = true; if (skip && skip.checked !== !!cur.skip) dirty = true; }
      else { for (const f of item.fields) if (choices[f.name] && (choices[f.name].value === "excel") !== (f.name in cur.changes)) dirty = true; }
      if (dirty && !(await askBox("Unsaved choices", "You changed this invoice but did not press Remember. Discard the changes?"))) return;
      m.close(); res(false);
    };
  });
}
function importBlocked(p, st) {
  // New rows with a problem cannot be imported until fixed or skipped. Nothing is imported implicitly.
  let blocked = 0;
  for (const it of p.review) {
    if (it.kind !== "new") continue;
    const v = st.get(it.row);
    if (v && v.skip) continue;
    const fixed = v ? it.fields.every(f => v.fields[f.name] !== undefined && v.fields[f.name] !== f.value) : false;
    if (!fixed) blocked++;
  }
  return blocked + (p.review_total > p.review.length ? 1 : 0);
}
function importSummaryLine(p, st) {
  let sk = 0, fixed = 0, u = 0, fc = 0;
  for (const v of st.values()) { if (v.item.kind === "new") { if (v.skip) sk++; else if (Object.keys(v.fields).length) fixed++; } else { u++; fc += Object.keys(v.changes).length; } }
  const bl = importBlocked(p, st);
  const newProb = p.review.filter(x => x.kind === "new").length;
  const clean = p.new - newProb;
  return `Ready to import: ${clean} clean new invoice(s) + ${fixed} corrected. Skipped by you: ${sk}. Still needing a fix or skip: ${bl}. Existing invoices: ${fc} field(s) on ${u} invoice(s), only the ones you chose.` + (bl ? " The import button stays off until every problem row is fixed or skipped." : "");
}
async function importFull() {
  if (FULL_IMPORT_BUSY || SIMPLE_IMPORT_BUSY) return;
  FULL_IMPORT_BUSY = true;
  let progress = null;
  try {
    const f = await pickFile(".xlsx,.xlsm");
    if (!f) return;
    const file = await fileB64(f);
    const c0 = el("div"); c0.appendChild(el("h2", null, "Checking the file")); c0.appendChild(el("p", "hint", f.name + " - preview only, nothing is saved or sent."));
    progress = modal(c0, "560px"); progress.ov.dataset.dismiss = "no";
    const p = await api("/api/import/preview", {file});
    progress.close(); progress = null;
    if (!p.ok) { msgBox("Import preview", p.msg || "Could not read the file.", true); return; }
    const st = new Map();
    const go = await new Promise(res => {
      const c = el("div"); c.appendChild(el("h2", null, "Import preview"));
      c.appendChild(el("p", "hint", `${f.name}: ${p.rows} rows. New invoices: ${p.new}. Already in the program: ${p.existing} (${p.same} identical). Empty rows: ${p.blank}.`));
      if (p.problem_total) {
        c.appendChild(el("h3", null, `Rows that will be skipped or need a look (${p.problem_total})`));
        const t = el("div"); t.style.cssText = "max-height:120px;overflow:auto;border:1px solid #ccd;padding:4px;font-size:12px";
        for (const x of p.problems) t.appendChild(el("div", null, `Row ${x.row}${x.invoice ? " | " + x.invoice : ""} | ${x.level === "skipped" ? "SKIPPED" : "CHECK"}: ${x.reason}`));
        c.appendChild(t);
      }
      c.appendChild(el("h3", null, `Invoices to review (${p.review_total}${p.review_total > p.review.length ? ", first " + p.review.length : ""}). Click one to open it.`));
      const list = el("div"); list.style.cssText = "max-height:260px;overflow:auto;border:1px solid #ccd;padding:4px;font-size:13px";
      const sum = el("p", "hint");
      const redraw = () => { sum.textContent = importSummaryLine(p, st); if (window.__impOk) window.__impOk.disabled = (!p.new && !p.review_total) || importBlocked(p, st) > 0; };
      for (const it of p.review) {
        const row = el("div"); row.style.cssText = "cursor:pointer;padding:3px 2px;border-bottom:1px solid #eee";
        const label = () => `${st.has(it.row) ? "[decided] " : ""}Row ${it.row} | ${it.invoice} | ${it.kind === "new" ? "NEW" : "EXISTING"} | ${it.fields.length} field(s): ${it.fields.slice(0, 4).map(x => x.name).join(", ")}${it.fields.length > 4 ? "..." : ""}`;
        row.textContent = label();
        row.onclick = async () => { await reviewDialog(it, st); row.textContent = label(); redraw(); };
        list.appendChild(row);
      }
      c.appendChild(list); c.appendChild(sum); redraw();
      if (p.pending_upload) c.appendChild(el("p", "hint", `${p.pending_upload} invoice(s) on this PC are still waiting to upload.`));
      const bar = el("div"); bar.style.marginTop = "10px";
      const ok = el("button", "tb", "Apply my choices and import"), no = el("button", "tb ghost", "Cancel");
      window.__impOk = ok; ok.id = "imp-apply"; redraw(); bar.appendChild(ok); bar.appendChild(no); c.appendChild(bar);
      const m = modal(c, "820px"); m.ov.dataset.dismiss = "no";
      ok.onclick = () => { m.close(); res(true); }; no.onclick = () => { m.close(); res(false); };
    });
    if (!go) return;
    const existing = [], new_fixes = {}, skip_rows = [];
    for (const [row, v] of st) {
      if (v.item.kind === "new") { if (v.skip) skip_rows.push(row); if (Object.keys(v.fields).length) new_fixes[row] = v.fields; }
      else existing.push({uid: v.item.uid, base: v.item.base, invoice: v.item.invoice, expect: v.expect, changes: v.changes, reason: v.reason});
    }
    clearTimeout(toastT); $("#toast").classList.add("hidden");
    const c2 = el("div"); c2.appendChild(el("h2", null, "Saving"));
    c2.appendChild(el("div", "import-progress"));
    c2.appendChild(el("p", "hint", "Keep this window open and do not repeat the import."));
    progress = modal(c2, "560px"); progress.ov.dataset.dismiss = "no";
    const request_id = Date.now().toString(36) + "_" + Math.random().toString(36).slice(2);
    const r = await api("/api/import/commit", {file, request_id, expect_new: p.new, existing, new_fixes, skip_rows});
    progress.close(); progress = null;
    const lines = [];
    if (r.msg) lines.push(r.msg);
    if (r.import_msg) lines.push(r.import_msg);
    if (existing.length) lines.push(`Changed ${r.updated_fields || 0} field(s) you chose on existing invoices.`);
    for (const x of (r.rejected_updates || []).slice(0, 15)) lines.push(`Not changed: ${x.invoice}: ${x.reason}`);
    const box = el("p", "hint"); box.textContent = r.sync ? syncLine(r.sync) : "";
    const cc = el("div"); cc.appendChild(el("h2", null, "Import result"));
    for (const l of lines) cc.appendChild(el("p", "hint", l));
    cc.appendChild(box); if (r.request_id) cc.appendChild(el("p", "hint", "Reference: " + r.request_id));
    const done = el("button", "tb", "Close"); cc.appendChild(done);
    const m2 = modal(cc, "560px"); done.onclick = () => m2.close();
    refreshCurrent();
    if (r.sync && r.batch) await waitUpload(box, r.batch, 60);
  } catch (e) {
    if (progress) { progress.close(); progress = null; }
    if (!e.auth) msgBox("Import result", "The local program did not return a readable result. The outcome is NOT confirmed. Do not import the same file again yet. Use Settings > Last full import result.", true);
  } finally {
    if (progress) progress.close();
    clearTimeout(toastT); $("#toast").classList.add("hidden");
    FULL_IMPORT_BUSY = false;
  }
}

function shareModal() {
  const c = el("div");
  c.appendChild(el("h2", null, "Shared folder"));
  const f = el("div", "fld");
  f.appendChild(el("label", null, "Network folder path (example: Z:\\Shared)"));
  const inp = el("input", "in");
  f.appendChild(inp); c.appendChild(f);
  const hint = el("div", "hint"); c.appendChild(hint);
  api("/api/share/get").then(r => { inp.value = r.share || ""; if (r.trial) { inp.disabled = true; inp.placeholder = "Not available in the trial"; br.disabled = ok.disabled = true; hint.textContent = "Not available in the trial: the trial works on this PC only, no shared folder."; } });
  const row = el("div", "mrow");
  const br = el("button", "btn", "Browse..."), cn = el("button", "btn", "Cancel"), ok = el("button", "btn accent", "Save");
  row.append(br, cn, ok); c.appendChild(row);
  const { close } = modal(c, "520px");
  br.onclick = async () => { const r = await api("/api/share/pick"); if (r.path) inp.value = r.path; else hint.textContent = "No folder chosen. You can also type or paste the path in the box above (example Z:\\Shared), then press Save."; };
  cn.onclick = close;
  ok.onclick = async () => { const r = await api("/api/share/set", { path: inp.value.trim() }); close(); msgBox("Shared folder", r.msg || "", !r.ok); };
}
function usersModal() {
  const c = el("div");
  c.appendChild(el("h2", null, "Users"));
  const lb = el("div", "listbox");
  c.appendChild(lb);
  const row = el("div", "mrow");
  const permissions=el("button","btn accent","Permissions");row.append(permissions);
  const add = el("button", "btn", "Add user"), ch = el("button", "btn", "Change password"),
        del = el("button", "btn danger", "Delete user"), cl = el("button", "btn", "Close");
  row.append(add, ch, del, cl); c.appendChild(row);
  const { close } = modal(c, "440px");
  let sel = null;
  const load = async () => {
    const st = await fetch("/api/state").then(r => r.json());
    lb.innerHTML = "";
    st.users.forEach(n => {
      const d = el("div", null, n);
      if (n === sel) d.classList.add("on");
      d.onclick = () => { sel = n; lb.querySelectorAll("div").forEach(x => x.classList.toggle("on", x.textContent === n)); };
      lb.appendChild(d);
    });
  };
  const guard = async () => { if (!S.isAdmin) { msgBox("Users", "Only ADMIN can manage users."); return false; } return true; };
  add.onclick = async () => {
    if (!(await guard())) return;
    const n = await promptBox("New user", "User name (English):");
    if (!n || !n.trim()) return;
    const p = await promptBox("New user", "Password:", true);
    if (!p) return;
    const adm = S.trialLimit ? await askBox("New user", "Make this user an administrator (can manage users and settings)?") : false;
    const r = await api("/api/users/add", { name: n.trim(), pw: p, admin: adm });
    if (!r.ok) msgBox("Users", r.msg, true); else if (r.first) msgBox("Users", r.msg);
    load();
  };
  ch.onclick = async () => {
    if (!(await guard()) || !sel) return;
    const p = await promptBox("Password", `New password for ${sel}:`, true);
    if (!p) return;
    const r = await api("/api/users/chpw", { name: sel, pw: p });
    if (!r.ok) msgBox("Users", r.msg, true);
  };
  del.onclick = async () => {
    if (!(await guard()) || !sel || sel === "ADMIN") return;
    if (await askBox("Delete", `Delete user ${sel}?`)) { await api("/api/users/del", { name: sel }); sel = null; load(); }
  };
  permissions.onclick=()=>{if(sel)userPermissions(sel);else msgBox("Permissions","Choose a user first.")};
  cl.onclick = close;
  load();
}
function listsModal() {
  const st = S;
  const c = el("div");
  c.appendChild(el("h2", null, "Import list (one item per line)"));
  const sel = el("select", "in");
  st.listNames.forEach(n => sel.appendChild(el("option", null, n)));
  c.appendChild(sel);
  c.appendChild(el("div", "hint", "customer_district: paste two Excel columns (Customer Name, District)"));
  const ta = el("textarea", "in");
  ta.style.marginTop = "8px";
  c.appendChild(ta);
  const row = el("div", "mrow");
  const cl = el("button", "btn", "Close"), sv = el("button", "btn accent", "Save");
  row.append(cl, sv); c.appendChild(row);
  const { close } = modal(c, "640px");
  cl.onclick = close;
  sv.onclick = async () => {
    const r = await api("/api/import/lists", { name: sel.value, text: ta.value });
    msgBox("Import list", r.msg || "", !r.ok);
    if (r.ok) { ta.value = ""; const st2 = await fetch("/api/state").then(x => x.json()); S.lists = st2.lists; S.cdMap = st2.cd_map; }
  };
}

/* ---------------- settings panel (central place; the top menus also keep working) ---------------- */
function columnsPicker(showOrder, order) {
  const sel = new Set(order);
  const c = el("div");
  c.appendChild(el("h2", null, T("Table columns")));
  c.appendChild(el("div", "hint", T("Hiding a column only changes this screen on this PC. Nothing is deleted: hidden columns stay saved, searchable and printable.")));
  const bar = el("div", "toolbar"); bar.style.margin = "6px 0";
  const cnt = el("span", "hint"); cnt.style.marginInlineStart = "auto";
  const boxes = [];
  const upd = () => { cnt.textContent = sel.size + " / " + showOrder.length + " " + T("selected"); };
  const bAll = el("button", "btn", T("Select all")), bNone = el("button", "btn", T("Clear all")), bDef = el("button", "btn", T("Restore default view"));
  bAll.onclick = () => { showOrder.forEach(n => sel.add(n)); paint(); upd(); };
  bNone.onclick = () => { sel.clear(); paint(); upd(); };
  bDef.onclick = () => { const d = DETAIL_COLS.filter(x => S.cols.includes(x)); sel.clear(); d.forEach(n => sel.add(n)); const def = canonicalColsDefault(S.cols); showOrder.splice(0, showOrder.length, ...def); paint(); upd(); };
  [bAll, bNone, bDef, cnt].forEach(x => bar.appendChild(x));
  c.appendChild(bar);
  const grid = el("div"); grid.style.cssText = "display:flex;flex-direction:column;gap:2px;max-height:56vh;overflow:auto;border:1px solid var(--line);border-radius:8px;padding:8px";
  c.appendChild(el("div", "hint", T("Use the arrows to move a column. The order is saved on this PC and used in every table.")));
  const paint = () => {
    grid.innerHTML = ""; boxes.length = 0;
    showOrder.forEach((name, i) => {
      const lab = el("div"); lab.style.cssText = "display:flex;align-items:center;gap:8px;padding:3px 4px;border-bottom:1px solid #eef2f7";
      const cb = el("input"); cb.type = "checkbox"; cb.checked = sel.has(name);
      cb.onchange = () => { cb.checked ? sel.add(name) : sel.delete(name); upd(); };
      boxes.push(cb);
      const nm = el("span", null, (i + 1) + ".  " + T(name)); nm.style.flex = "1";
      const mv = (d, txt) => { const bt = el("button", "btn", txt); bt.style.cssText = "padding:1px 10px;min-width:34px"; bt.disabled = i + d < 0 || i + d >= showOrder.length;
        bt.onclick = () => { const x = showOrder[i]; showOrder[i] = showOrder[i + d]; showOrder[i + d] = x; paint(); }; return bt; };
      lab.append(cb, nm, mv(-1, "\u2191"), mv(1, "\u2193")); grid.appendChild(lab);
    });
  };
  paint();
  c.appendChild(grid);
  const row = el("div", "mrow");
  const save = el("button", "btn accent", T("Save")), cancel = el("button", "btn", T("Cancel"));
  row.appendChild(cancel); row.appendChild(save); c.appendChild(row);
  upd();
  const { close } = modal(c, "820px");
  cancel.onclick = close;
  save.onclick = () => { PREFS.cols = showOrder.filter(n => sel.has(n)); PREFS.order = showOrder.slice(); savePrefs(); refreshCurrent(); close(); };
}

function settingsModal() {
  const c = el("div");
  c.appendChild(el("h2", null, "Settings"));
  const sec = (title, rows) => {
    c.appendChild(el("h3", null, title)).style.cssText = "margin:14px 0 6px;font-size:14px;color:var(--accent)";
    const g = el("div", "toolbar");
    g.style.margin = "0";
    rows.forEach(([label, fn, cls]) => { const b = el("button", "btn " + (cls || ""), label); b.onclick = fn; g.appendChild(b); });
    c.appendChild(g);
  };
  if (S.isAdmin) {
    c.appendChild(el("h3", null, "Program update")).style.cssText = "margin:14px 0 6px;font-size:14px;color:var(--accent)";
    const ui = el("div", "hint"); ui.textContent = "Current version: ...";
    api("/api/update/status", {}).then(r => { if (r && r.ok && ui.textContent.startsWith("Current version")) ui.textContent = "Current version: " + r.version + (r.installed ? " (update " + r.installed + ")" : "") + "."; }).catch(() => {});
    const ub = el("button", "btn accent", "Check for updates");
    const rb = el("button", "btn", "Restore previous version"); rb.style.marginLeft = "8px";
    const bar = el("div", "toolbar"); bar.style.margin = "0";
    let found = null;
    const say = (h) => { ui.innerHTML = ""; ui.appendChild(document.createTextNode(h)); };
    ub.onclick = async () => {
      if (found) {
        if (!(await askBox("Distribution Program", "Update to " + found.version + " now? The program saves and syncs first, replaces " + found.changed.length + " file(s), then restarts by itself. Connection files are not touched. If anything fails, the old version comes back automatically."))) return;
        ub.disabled = true; say("Saving and syncing before the update...");
        try {
          let st = await api("/api/app/exit/start", {});
          for (let i = 0; i < 180 && !["ready", "trial_local_only", "failed"].includes(st.state); i++) { await new Promise(r => setTimeout(r, 500)); st = await api("/api/app/exit/status", {}); }
          if (st.state === "failed") { say("Update not started: " + (st.msg || "sync did not finish") + " Nothing changed."); ub.disabled = false; return; }
          say("Downloading and installing...");
          const r = await api("/api/update/apply", {});
          if (!r.ok) { say(r.msg || "Update failed. Old version kept."); ub.disabled = false; ub.textContent = "Check for updates"; found = null; return; }
          say("Update " + r.version + " installed. Restarting in a few seconds. Reopen the window if it does not appear.");
          await api("/api/update/restart", {});
        } catch (e) { say("Update stopped: " + e + ". Nothing was changed unless this page says installed."); ub.disabled = false; }
        return;
      }
      ub.disabled = true; say("Checking...");
      try {
        const r = await api("/api/update/check", {});
        ub.disabled = false;
        if (!r.ok) { say(r.msg || "Could not check."); return; }
        if (!r.available) { say("You have the latest version (" + r.version + ")."); return; }
        found = r; ub.textContent = "Update now (the program restarts)";
        say("New version available: " + r.version + ". Changed files: " + r.changed.length + " (about " + Math.max(1, Math.round(r.total_size / 1024)) + " KB). " + (r.notes || "") + " Connection files are not touched. A backup of the current files is saved first.");
      } catch (e) { ub.disabled = false; say("Could not check: " + e); }
    };
    rb.onclick = async () => {
      if (!(await askBox("Distribution Program", "Restore the files from before the last update? The program will restart."))) return;
      const r = await api("/api/update/rollback", {});
      if (!r.ok) { say(r.msg || "Restore failed."); return; }
      say("Previous version restored. Restarting...");
      await api("/api/update/restart", {});
    };
    bar.appendChild(ub); bar.appendChild(rb);
    c.appendChild(ui); c.appendChild(bar);
  }
  sec("Appearance", [[document.body.classList.contains("dark") ? "Switch to Light" : "Switch to Dark",
    () => { $("#t-theme").click(); close(); }]]);
  sec("Buttons", [["Customize buttons...", () => { close(); layoutEditor(); }]]);
  if (window.fbToolsSection) window.fbToolsSection(c, sec);
  // language: English default, Arabic with right-to-left layout
  const lg = el("div", "toolbar"); lg.style.margin = "4px 0 0";
  const bEn = el("button", "btn" + (PREFS.lang === "en" ? " accent" : ""), "English");
  const bAr = el("button", "btn" + (PREFS.lang === "ar" ? " accent" : ""), "العربية");
  bEn.onclick = () => { setLang("en"); close(); settingsModal(); };
  bAr.onclick = () => { setLang("ar"); close(); settingsModal(); };
  lg.appendChild(bEn); lg.appendChild(bAr);
  c.appendChild(el("h3", null, T("Language"))).style.cssText = "margin:14px 0 6px;font-size:14px;color:var(--accent)";
  c.appendChild(lg);
  // font size + table density
  const fs = el("div", "toolbar"); fs.style.margin = "0";
  [["s", "Small"], ["m", "Medium"], ["l", "Large"]].forEach(([k, lab]) => {
    const b = el("button", "btn" + (PREFS.fs === k ? " accent" : ""), T(lab));
    b.onclick = () => { PREFS.fs = k; savePrefs(); applyAppearance(); close(); settingsModal(); };
    fs.appendChild(b);
  });
  c.appendChild(el("h3", null, T("Font size"))).style.cssText = "margin:14px 0 6px;font-size:14px;color:var(--accent)";
  c.appendChild(fs);
  const dn = el("div", "toolbar"); dn.style.margin = "0";
  [["compact", "Compact"], ["cozy", "Comfortable"]].forEach(([k, lab]) => {
    const b = el("button", "btn" + (PREFS.dens === k ? " accent" : ""), T(lab));
    b.onclick = () => { PREFS.dens = k; savePrefs(); applyAppearance(); close(); settingsModal(); };
    dn.appendChild(b);
  });
  c.appendChild(el("h3", null, T("Table density"))).style.cssText = "margin:14px 0 6px;font-size:14px;color:var(--accent)";
  c.appendChild(dn);
  // grid columns: show/hide is view-only - data, search, reports and exports always keep everything
  const order = (PREFS.cols === null ? DETAIL_COLS : PREFS.cols).filter(x => S.cols.includes(x));
  const showOrder = canonicalCols(S.cols);
  c.appendChild(el("h3", null, T("Table columns") + " (" + showOrder.length + ")")).style.cssText = "margin:14px 0 6px;font-size:14px;color:var(--accent)";
  c.appendChild(el("div", "hint", T("Hiding a column only changes this screen on this PC. Nothing is deleted: hidden columns stay saved, searchable and printable.") + " " + T("Scroll inside the list to see them all.")));
  const colBtn = el("button", "btn accent", T("Choose table columns") + "  (" + order.length + " / " + showOrder.length + ")");
  colBtn.onclick = () => columnsPicker(showOrder, order);
  c.appendChild(colBtn);
  const rst = el("button", "btn", T("Restore default view"));
  rst.onclick = () => { PREFS.cols = null; PREFS.order = null; savePrefs(); refreshCurrent(); close(); settingsModal(); };
  rst.style.marginTop = "6px"; rst.style.marginInlineStart = "10px"; c.appendChild(rst);
  sec("Import diagnostics", [["Last full import result", () => { close(); lastFullImport(); }],
    ["Last warehouse import result", () => { close(); showImportReceipt("wh", "Last warehouse import result"); }],
    ["Last printed-invoice import result", () => { close(); showImportReceipt("pi", "Last printed-invoice import result"); }]]);
  sec("Connection", [["Shared network folder...", () => { close(); shareModal(); }],
    ["Sync now (F5)", () => { doSync(); }],
    ["Review sync conflicts", () => {close(); conflictMenu();}]]);
  const stBox = el("div", "hint");
  stBox.style.cssText = "background:var(--head);border:1px solid var(--line);border-radius:8px;padding:8px 12px;line-height:1.7";
  stBox.textContent = "…";
  c.appendChild(stBox);
  fetch("/api/status").then(x => x.json()).then(r => {
    stBox.textContent = `${r.lan || ""}\n${r.cloud || ""}\n${T("Backup")}: ${r.last_backup || "-"}`;
  }).catch(() => { stBox.textContent = ""; });
  sec("Backup & data", [["Backup new data now", async () => { const r = await api("/api/backup/now"); msgBox("Backup", r.msg || "", !r.ok); }],
    ["Load a backup file...", () => { close(); loadBackup(); }],
    ["Import full data (Excel)", () => { close(); importFull(); }],
    
    ["Import lists", () => { close(); listsModal(); }]]);
  if (S.isAdmin && (!S.trialLimit || S.customerMode)) sec("Administration", [["Manage users", () => { close(); usersModal(); }]]);
  sec("About", [["About Distribution Program", () => msgBox("About",
    `${$("#foot-left").textContent}\n${$("#foot-right").textContent}`)]]);
  const row = el("div", "mrow");
  const cl = el("button", "btn", "Close");
  row.appendChild(cl); c.appendChild(row);
  const { close } = modal(c, "560px");
  cl.onclick = close;
}

function renderFirebaseUsage(r){
 const p=r.project_usage,u=r.usage,automatic=p?.data?.today;
 const counts=(v,limits)=>[['Reads','reads'],['Writes','writes'],['Deletes','deletes']].map(([label,key])=>`${label} ${Number(v[key]).toLocaleString()} / ${Number(limits[key]).toLocaleString()} (${(100*v[key]/limits[key]).toFixed(2)}%)`).join(' | ');
 const real=automatic&&!automatic.empty&&automatic.as_of;
 const tag=$('#usage-bar .estimate-tag');if(tag)tag.textContent='Whole project · Google Cloud Monitoring';
 if(real){
  $('#usage-summary').textContent=counts(automatic,p.limits);
  const age=Math.max(0,Math.round((Date.now()/1000-automatic.as_of)/60));
  $('#project-usage-summary').textContent=`MAIN + REPLICA + other clients | ${automatic.day} Pacific quota day | Source as of ${new Date(automatic.as_of*1000).toLocaleString()} (${age} min ago)${p.error?' | Last refresh failed, showing last data':''}`;
 }else{
  $('#usage-summary').textContent='Real project totals unavailable. No device estimate substituted.';
  $('#project-usage-summary').textContent=(p?.error||'No Monitoring samples yet')+' | Existing account needs Monitoring read access.';
 }
 $('#usage-bar').title='Reads/writes/deletes reported by Google Cloud Monitoring, whole Firebase project. Delayed samples, not exact billing. Updates every5minutes. Does not separate MAIN from REPLICA.';
 $('#project-usage-bar').classList.toggle('warn',!!p?.error||!real);
 $('#project-usage-bar').title=p?.source||'Cloud Monitoring source unavailable';
 if(u)$('#usage-bar').title+=` Device-only estimate, not project totals: Reads ${u.reads}, Writes ${u.writes}, Deletes ${u.deletes}.`;
}

/* ---------------- status polling ---------------- */
async function poll() {
  try {
    const r = await fetch("/api/status").then(x => x.json());
    LG_USERS = r.users || [];
    if(!r.logged) updateConnectionLamp(null);
    $("#lg-ver").textContent = r.version || "";
    $("#lg-credit").textContent = r.credit || "";
    $("#lg-sign").textContent = r.signature || "";
    if (r.logged && $("#app").classList.contains("hidden") && !$("#login").classList.contains("hidden")) {
      // already logged in (cookie) but UI shows login: skip; login flow owns the transition
    }
    if (r.logged && !$("#app").classList.contains("hidden")) {
      const stxt = [r.lan, r.cloud, r.sync_conflicts ? `${r.sync_conflicts} sync conflict(s) preserved - review in Other` : ""].filter(Boolean).join("   |   ");
      const rl = (r.received || {}).last;
      let rtxt = "";
      if (rl) rtxt = `Last receive (${rl.source}) ${new Date(rl.at * 1000).toLocaleTimeString()}: Add ${rl.new} | Edit ${rl.updated} | Delete ${rl.deleted}` + (rl.kept_local ? ` | ${rl.kept_local} kept on this PC (unsaved or newer here)` : "") + (rl.conflicts ? ` | ${rl.conflicts} conflict(s) kept for review` : "");
      $("#status").textContent = [stxt, rtxt].filter(Boolean).join("   |   ");
      $("#receive-summary").dataset.lastBatch=rl?`Last receive ${new Date(rl.at*1000).toLocaleTimeString()}   |   Add ${rl.new}   |   Edit ${rl.updated}   |   Delete ${rl.deleted}`:"Waiting for first received change";
      $("#receive-bar").title=stxt;
      updateConnectionLamp(r.connection);
      syncTicker(r.received);
      updateOtherIndicator(r.sync_conflicts);
      $("#status").title = $("#status").textContent;
      $("#status").classList.toggle("bad", /not reachable|not set up|unreachable|problem/i.test(stxt));
      if (r.v !== DATA_V) {
        const fresh = await fetch("/api/state").then(x => x.json());
        if (fresh.ok) {
          S.permissions=fresh.permissions;S.isAdmin=fresh.is_admin;applyHomePermissions();
          S.lists = fresh.lists; S.cdMap = fresh.cd_map;
          S.forwardTo = fresh.forward_to; S.invoiceType = fresh.invoice_type; S.paymentTerms = fresh.payment_terms;
          if (typeof HO !== "undefined") {
            for (const [node, vals] of [[HO.fw, S.forwardTo], [HO.ty, S.invoiceType], [HO.pt, S.paymentTerms]]) {
              if (!node) continue;
              const selected = node.value;
              const values = [...new Set(["", ...vals, ...(selected ? [selected] : [])])];
              node.replaceChildren(...values.map(v => { const o = document.createElement("option"); o.value = v; o.textContent = v; return o; }));
              node.value = selected;
            }
          }
        }
        refreshCurrent();
      }
      DATA_V = r.v;
    }
  } catch (e) { updateConnectionLamp(null); }
  setTimeout(poll, 2000);
}

/* ---------------- start ---------------- */
applyAppearance();
applyLang();
initLogin();
showLogin();
fetch("/api/status").then(r => r.json()).then(async r => {
  LG_USERS = r.users || [];
  $("#lg-ver").textContent = r.version; $("#lg-credit").textContent = r.credit; $("#lg-sign").textContent = r.signature;
  if (r.test_mode && r.trial_limit && r.customer_login) {
    $("#lg-ver").textContent = r.version;
  } else if (r.test_mode && r.trial_limit) {
    // Trial edition: no users, no login screen. Open straight into the program.
    $("#login").classList.add("hidden");
    if (!r.logged) { const answer = await api("/api/trial/start"); if (answer.ok) { await boot(); return; } }
  } else if (r.test_mode) {
    const card = document.querySelector(".login-card");
    card.querySelectorAll(".login-lab, #lg-user, #lg-pass, #lg-go").forEach(n => n.classList.add("hidden"));
    const hint = el("p", "hint", "Isolated dummy-data trial. No password needed. Your normal database is not opened.");
    const start = el("button", "btn big accent", "Start isolated trial");
    start.id = "trial-start";
    start.onclick = async () => { const answer = await api("/api/trial/start"); if (answer.ok) boot(); };
    card.insertBefore(hint, $("#lg-err")); card.insertBefore(start, $("#lg-err"));
  }
  if (r.logged) await boot();
}).catch(() => {});
poll();