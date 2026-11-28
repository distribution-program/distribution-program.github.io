/* Distribution Program views (1/2): state, sidebar, navigation, details/search, RGR. */
"use strict";
const S = {            // server-provided constants + runtime state
  cols: [], editable: new Set(), locked: new Set(), statuses: [], lists: {}, listFields: {},
  dateCols: new Set(), cdMap: {}, user: "", cur: "home", flt: null, exempt: new Set(),
};
const SIDE_COLORS = {
  light: { home: "#94a3b8", search: "#3b82f6", new: "#22c55e", und: "#f97316", details: "#8b5cf6",
           rep: "#ec4899", wh: "#06b6d4", rgr: "#eab308" },
  dark: { home: "#64748b", search: "#60a5fa", new: "#4ade80", und: "#fb923c", details: "#a78bfa",
          rep: "#f472b6", wh: "#22d3ee", rgr: "#facc15" },
};
const norm = s => String(s || "").replace(/[\u200e\u200f]/g, "").trim().replace(/\s+/g, " ").toLowerCase();
const districtsFor = cust => S.cdMap[norm(cust)] || S.lists.district || [];
function listFor(col, cust) {
  if (col === "District") return districtsFor(cust || curCust || "");
  const k = S.listFields[col];
  return k ? (S.lists[k] || []) : null;
}
let curCust = "";      // customer of the row being edited / the form

/* ---------------- sidebar ---------------- */
function buildSidebar() {
  const sb = $("#sidebar");
  sb.innerHTML = "";
  const mode = document.body.classList.contains("dark") ? "dark" : "light";
  const C = SIDE_COLORS[mode];
  const items = [
    ["home", "Home", C.home, "⌂"], ["search", "Search Invoice", C.search, "⌕"],
    ["new", "New Invoice", C.new, "✚"], ["und", "Undelivered", C.und, "◷"],
    ["details", "Invoice Details", C.details, "☰", S.statuses.map(s => ["s:" + s, s])],
    ["rep", "Invoice Report", C.rep, "▤", [["rep:Proposal", "Proposal Report"], ["rep:inprocess", "In Process Report"],
                                      ["ho", "Invoice to Head Office"]]],
    ["wh", "Warehouse Report", C.wh, "▦"], ["rgr", "RGR Not Costed", C.rgr, "⚠"],
  ];
  for (const [id, label, color, icon, kids] of items) {
    const g = el("div");
    const b = el("button", "snode");
    b.dataset.k = id;
    b.style.borderInlineStartColor = color;
    const ic = el("span", "sicon", icon);
    ic.style.color = color;
    b.appendChild(ic);
    const lab = el("span", "slab", label);   // el() translates + remembers English
    b.appendChild(lab);
    if (kids) {
      const ar = el("span", "arrow", "▸");
      b.appendChild(ar);
      const box = el("div", "sgroup hidden");
      for (const [kid, klabel] of kids) {
        const kb = el("button", "snode child", klabel);
        kb.dataset.k = kid;
        kb.style.borderInlineStartColor = color;
        kb.onclick = () => go(kid);
        box.appendChild(kb);
      }
      g.append(b, box);
      b.onclick = () => { box.classList.toggle("hidden"); ar.textContent = box.classList.contains("hidden") ? "▸" : "▾"; };
    } else {
      b.onclick = () => go(id);
      g.appendChild(b);
    }
    sb.appendChild(g);
  }
}
function markSide(k) {
  document.querySelectorAll(".snode").forEach(b => {
    const on = b.dataset.k === k;
    b.classList.toggle("on", on);
    if (on) {
      const grp = b.closest(".sgroup");
      if (grp) { grp.classList.remove("hidden"); const ar = grp.previousElementSibling.querySelector(".arrow"); if (ar) ar.textContent = "▾"; }
    }
  });
}

/* ---------------- navigation ---------------- */
const VIEWS = { home: "v-home", details: "v-details", new: "v-new", rep: "v-report", ho: "v-ho",
                wh: "v-wh", rgr: "v-rgr" };
const NAV_HISTORY=[];
let NAV_BACK=false;
function go(k) {
  if(typeof canOpen==='function'&&!canOpen(k)){msgBox('Access denied','This Home button is not allowed for your user.',true);return;}
  k = { search: "details", und: "s:Undelivered" }[k] || k;
  if(S.cur && S.cur!==k && !NAV_BACK) NAV_HISTORY.push(S.cur);
  S.cur = k;
  if($("#t-back"))$("#t-back").disabled=!NAV_HISTORY.length;
  let title = k.startsWith("s:") ? T("Invoice Details") + " > " + T(k.slice(2)) :
    k.startsWith("rep:") ? T("Invoice Report") + " > " + T(k === "rep:Proposal" ? "Proposal Report" : "In Process Report") :
    T(({home:"Home",details:"Invoice Details",new:"New Invoice",ho:"Invoice to Head Office",wh:"Warehouse Report",rgr:"RGR Not Costed"})[k] || "Home");
  let heading=$("#section-location");
  if(!heading){heading=el("h1","section-location");heading.id="section-location";$("#v-home").parentElement.prepend(heading);}
  heading.textContent=title;heading.classList.toggle("hidden",k==="home"||k.startsWith("group:"));
  for (const v of Object.values(VIEWS)) $("#" + v).classList.add("hidden");
  if (k.startsWith("group:")) {
    buildHome(Number(k.slice(6)));$("#v-home").classList.remove("hidden");
  } else if (k === "details" || k.startsWith("s:")) {
    S.flt = k === "details" ? null : k.slice(2);
    resetFilters(FLT, S.flt);
    $("#v-details").classList.remove("hidden");
    fillDetails();
    markSide(k === "details" ? (lastDetailsKey = "details") : k);
  } else if (k.startsWith("rep:")) {
    S.repStatus = k.slice(4);
    $("#rep-title").textContent = k === "rep:Proposal" ? "Proposal Report" : "In Process Report";
    $("#v-report").classList.remove("hidden");
    resetRoute();
    markSide(k);
  } else {
    const key = { ho: "ho", wh: "wh", rgr: "rgr", new: "new", home: "home" }[k];
    $("#" + VIEWS[key]).classList.remove("hidden");
    if (key === "home") buildHome();
    if (key === "rgr") fillRgr();
    if (key === "wh") { whShow(); piShow(); }
    markSide(k);
  }
}
let lastDetailsKey = "details";

/* ---------------- filters (shared by details + RGR) ---------------- */
function makeFilters(container, refill) {
  const F = {};
  container.innerHTML = "";
  const mk = (lab, node) => { container.appendChild(el("label", null, lab)); container.appendChild(node); };
  F.sq = el("input", "in"); F.sq.size = 16;
  mk("Invoice / Sales Order:", F.sq);
  F.cust = autoCombo({ getvals: () => S.lists.customers || [], fullList: true });
  F.cust.input.style.width = "240px";
  mk("Customer:", F.cust);
  F.dv = el("input", "in"); F.dv.size = 11; F.dv.placeholder = "dd/mm/yyyy";
  mk("Date (dd/mm/yyyy, mm/yyyy, yyyy):", F.dv);
  const rec = el("label"); rec.style.fontWeight = "600";
  F.recent = el("input"); F.recent.type = "checkbox";
  rec.append(F.recent, el("span", "slab", " Last 5 days (undated included)"));
  container.appendChild(rec);
  F.cfc = el("select", "in");
  F.cfc.append(el("option", null, ""), ...S.cols.map(c => el("option", null, c)));
  mk("Filter column:", F.cfc);
  F.cfv = el("input", "in"); F.cfv.size = 14;
  container.appendChild(F.cfv);
  const blab=el("label");blab.style.fontWeight="600";F.cfb=el("input");F.cfb.type="checkbox";blab.append(F.cfb,el("span","slab"," Blank only"));blab.title="Show only rows where the chosen column is empty";container.appendChild(blab);
  container.appendChild(el("span", "hint", "(or click a title)"));
  let t = null;
  const deb = () => { clearTimeout(t); t = setTimeout(refill, 700); };
  for (const n of [F.sq, F.dv, F.cfv]) n.addEventListener("input", deb);
  F.cfb.onchange=()=>{F.cfv.disabled=F.cfb.checked;if(F.cfb.checked)F.cfv.value="";refill()};
  F.cfc.addEventListener("change", deb);
  F.cust.input.addEventListener("input", deb);
  F.sq.addEventListener("keydown", e => { if (e.key === "Enter") refill(); });
  F.recent.onchange = refill;
  F.districts=new Set();const district=el("button","btn","Districts (all)");container.append(district);
  district.onclick=()=>{const c=el('div');c.append(el('h2',null,'Districts'));const search=el('input','in');search.placeholder='Find District';c.append(search);const list=el('div');list.style.cssText='max-height:45vh;overflow:auto;margin:14px 0';c.append(list);const chosen=new Set(F.districts);const paint=()=>{list.replaceChildren();for(const name of S.lists.district||[]){if(!norm(name).includes(norm(search.value)))continue;const label=el('label');label.style.cssText='display:block;padding:8px';const cb=el('input');cb.type='checkbox';cb.checked=chosen.has(name);cb.onchange=()=>cb.checked?chosen.add(name):chosen.delete(name);label.append(cb,el('span',null,' '+name));list.append(label)}};search.oninput=paint;paint();const all=el('button','btn','Clear selection'),clearSearch=el('button','btn','Clear search'),apply=el('button','btn accent','Apply'),cancel=el('button','btn','Cancel');c.append(all,clearSearch,apply,cancel);clearSearch.onclick=()=>{search.value='';paint()};const m=modal(c,'500px');all.onclick=()=>{chosen.clear();paint()};cancel.onclick=m.close;apply.onclick=()=>{F.districts=chosen;district.textContent=chosen.size?'Districts ('+chosen.size+' selected)':'Districts (all)';m.close();refill()};};
  F.clear=()=>{clearTimeout(t);F.sq.value='';F.cust.set('');F.dv.value='';F.recent.checked=false;F.cfc.value='';F.cfv.value='';F.cfb.checked=false;F.cfv.disabled=false;F.districts.clear();district.textContent='Districts (all)';refill()};const clear=el('button','btn','Clear search');clear.onclick=F.clear;container.append(clear);
  F.vals = () => ({ districts:[...F.districts], sq: F.sq.value, cust: F.cust.val(), dv: F.dv.value, recent: F.recent.checked,
                    cfc: F.cfc.value, cfv: F.cfv.value, cfb: F.cfb.checked });
  return F;
}
function resetFilters(F, flt) {
  if(F.districts)F.districts.clear();
  F.sq.value = ""; F.cust.set(""); F.cfv.value = ""; F.cfc.value = ""; if(F.cfb){F.cfb.checked=false;F.cfv.disabled=false}
  const d = new Date();
  F.dv.value = (flt && !S.exempt.has(flt)) ? String(d.getMonth() + 1).padStart(2, "0") + "/" + d.getFullYear() : "";
  F.recent.checked = flt === "Undelivered";
}

/* ---------------- details / search ---------------- */
let FLT, detGrid;
function initDetails() {
  FLT = makeFilters($("#det-filters"), fillDetails);
  detGrid = new Grid($("#det-grid"), {
    cols: S.cols, vis: visibleColIdx(S.cols), editable: new Set(S.editable), locked: new Set(S.locked),
    statusList: S.statuses, dateCols: S.dateCols,
    listFor: col => listFor(col, cellCust()),
    onEdit: editField, onHead: c => { FLT.cfc.value = c; FLT.cfv.focus(); },
    extra: [{ label: "Edit invoice (all fields)", fn: editAllFields }, { label: "Edit selected (bulk)", fn: bulkEdit }, { label: "Delete selected", fn: delDetails }],
    refresh: fillDetails,
  });
  $("#det-editall").onclick = editAllFields;
  $("#det-bulk").onclick = bulkEdit;
  $("#det-del").onclick = delDetails;
  $("#det-print").onclick = () => printResults("details");
  $("#det-savepdf").onclick = () => printResults("details", true);
}
function cellCust() {
  if (detGrid && detGrid.cell) return detGrid.rows[detGrid.cell.r].v[S.cols.indexOf("Customer Name")];
  return "";
}
async function editField(uid, col, val, reason) {
  const r = await api("/api/edit", { uid, name: col, value: val, reason });
  if (r.ok && !detGrid?.editing) refreshCurrent();
  return r;
}
let detailQuerySeq=0;
async function fillDetails() {
  const seq=++detailQuerySeq;
  const p = await apiQ("/api/query/details", { flt: S.flt, f: FLT.vals() });
  if(seq!==detailQuerySeq)return;
  detGrid.vis = visibleColIdx(S.cols);
  detGrid.setRows(p.rows);
  $("#det-cnt").textContent = `${p.total} invoices` +
    (p.total > p.shown ? `  (showing the newest ${p.shown} - use search / date to narrow)` : "");
}
function editAllFields() {
  const selected = detGrid.selected();
  if (selected.length !== 1) return msgBox("Edit invoice", "Select one invoice first.");
  const record = detGrid.rows.find(r => r.uid === selected[0]);
  if (!record) return;
  const content = el("div"); content.appendChild(el("h2", null, "Edit invoice (all fields)"));
  content.appendChild(el("p", "hint", "All 34 fields stay editable here, even when hidden in the table. Changing ID or Invoice Number updates this invoice; it does not create another one."));
  const form = el("div", "form-grid");
  form.style.cssText = "display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;max-height:60vh;overflow:auto;padding:8px";
  const inputs = {}, original = {};
  for (const name of DEFAULT_COLS) {
    const field = el("div", "fld"); field.appendChild(el("label", null, name));
    const combo = name !== "Invoice Status" && S.listFields[name] ? autoCombo({autoNearest:name==="Customer Name",getvals:()=>listFor(name,inputs["Customer Name"]?.value||record.v[S.cols.indexOf("Customer Name")])}) : null;
    const input = combo ? combo.input : el(name === "Invoice Status" ? "select" : "input", "in"); input.dataset.field = name;
    const value = record.v[S.cols.indexOf(name)] || "";
    if (name === "Invoice Status") {
      // Preserve an imported legacy value until changed, but only offer known stages.
      if (!S.statuses.includes(value)) { const old = el("option", null, value); old.value = value; old.disabled = true; input.appendChild(old); }
      for (const status of S.statuses) { const option = el("option", null, status); option.value = status; input.appendChild(option); }
    }
    input.value = value;
    original[name] = input.value; inputs[name] = input;
    field.appendChild(combo || input); form.appendChild(field);
  }
  content.appendChild(form);
  const recovery=draftRead("edit:"+record.uid);
  if(recovery)for(const [name,value]of Object.entries(recovery))if(inputs[name])inputs[name].value=value;
  const autoHint=recoveredHint(content,"Changes save locally as you type. Invalid values stay as recoverable input, not invoice changes.");
  let autoTimer,autoQueue=Promise.resolve(),closing=false;
  const allValues=()=>Object.fromEntries(DEFAULT_COLS.map(n=>[n,inputs[n].value]));
  const pendingValues=()=>Object.fromEntries(DEFAULT_COLS.filter(n=>inputs[n].value!==original[n]).map(n=>[n,inputs[n].value]));
  const autoSave=()=>{
    clearTimeout(autoTimer);const values=allValues();draftWrite("edit:"+record.uid,pendingValues());
    autoQueue=autoQueue.catch(()=>{}).then(async()=>{
      const changes={};for(const name of DEFAULT_COLS)if(values[name]!==original[name])changes[name]=values[name];
      if(changes["Invoice Status"]==="Cancelled"&&original["Invoice Status"]!=="Cancelled")delete changes["Invoice Status"];
      if(!Object.keys(changes).length)return;
      const a=await api("/api/edit/all",{uid:record.uid,changes});
      if(a.ok){Object.assign(original,changes);const pending=pendingValues();Object.keys(pending).length?draftWrite("edit:"+record.uid,pending):draftDrop("edit:"+record.uid);autoHint.textContent="Saved locally. Valid changes queued for sync. Cancellation still needs its reason.";}
      else autoHint.textContent="Input recovered locally; not applied: "+(a.msg||"Complete valid fields.");
    });return autoQueue;
  };
  form.addEventListener("input",()=>{draftWrite("edit:"+record.uid,pendingValues());autoHint.textContent="Input saved locally; applying valid changes...";clearTimeout(autoTimer);autoTimer=setTimeout(autoSave,250);});
  form.addEventListener("change",()=>{clearTimeout(autoTimer);autoSave();});
  const actions = el("div", "mrow"), cancel = el("button", "btn", "Close"), save = el("button", "btn accent", "Save changes");
  save.id = "edit-all-save"; actions.append(cancel, save); content.appendChild(actions);
  const { close, ov } = modal(content, "850px");ov.dataset.dismiss="no";
  cancel.onclick=async()=>{if(closing)return;closing=true;await autoSave();close();fillDetails();};
  save.onclick = async () => {
    clearTimeout(autoTimer);await autoSave();
    const changes = {};
    for (const name of DEFAULT_COLS) if (inputs[name].value !== original[name]) changes[name] = inputs[name].value;
    if (!Object.keys(changes).length) {draftDrop("edit:"+record.uid);close();await fillDetails();return;}
    let reason = "";
    if (changes["Invoice Status"] === "Cancelled" && original["Invoice Status"] !== "Cancelled") {
      reason = await promptBox("Cancelled invoice", "Why is this invoice cancelled?");
      if (reason === null || !reason.trim()) return;
    }
    save.disabled = true;
    try {
      const answer = await api("/api/edit/all", {uid: record.uid, changes, reason});
      if (answer.ok) { draftDrop("edit:"+record.uid);close(); await fillDetails(); }
      toast(answer.msg || "Saved", !answer.ok);
    } finally { save.disabled = false; }
  };
}

async function delDetails() {
  const ids = detGrid.selected();
  if (!ids.length) return;
  if (await askBox("Delete", `Delete ${ids.length} invoice(s) permanently?`)) {
    const r = await api("/api/delete", { uids: ids });
    toast(r.msg || "Deleted", !r.ok);
    fillDetails();
  }
}
function printResults(view, saveOnly) {
  const f = view === "rgr" ? FR.vals() : FLT.vals();
  api("/api/pdf/list", { view, flt: view === "rgr" ? null : S.flt, f, save_only: !!saveOnly,
    title: view === "rgr" ? "RGR Not Costed" : "Invoice Search" })
    .then(r => toast(r.msg || "", !r.ok));
}

/* ---------------- bulk edit ---------------- */
function bulkEdit() {
  const ids = detGrid.selected();
  if (!ids.length) return msgBox("Bulk edit", "Select invoices first (Ctrl+click or Shift+click).");
  const FL = S.bulkFields;
  const c = el("div");
  c.appendChild(el("h2", null, `Edit ${ids.length} invoices`));
  c.appendChild(el("div", "hint", `Applies to ${ids.length} selected invoices. Empty field = unchanged.`));
  const g = el("div", "mgrid");
  const ws = {};
  for (const col of FL) {
    const f = el("div", "fld");
    f.appendChild(el("label", null, col));
    let w;
    if (col === "Invoice Status") w = autoCombo({ getvals: () => [""].concat(S.statuses), readonlyList: false });
    else if (listFor(col)) w = autoCombo({ getvals: () => listFor(col) });
    else w = { input: el("input", "in"), val() { return this.input.value; } };
    f.appendChild(w.isAc ? w.input.parentElement : w.input);
    ws[col] = w;
    g.appendChild(f);
  }
  c.appendChild(g);
  const row = el("div", "mrow");
  const cn = el("button", "btn", "Cancel"), ok = el("button", "btn accent", "Apply to selected");
  row.append(cn, ok); c.appendChild(row);
  const { close } = modal(c, "760px");
  cn.onclick = close;
  ok.onclick = async () => {
    const ch = {};
    for (const col of FL) { const v = ws[col].val().trim(); if (v) ch[col] = v; }
    let reason = "";
    if (ch["Invoice Status"] === "Cancelled") {
      reason = await promptBox("Cancelled invoice", "Why is this invoice cancelled?");
      if (reason === null || !reason.trim()) return;
    }
    const r = await api("/api/bulk", { uids: ids, changes: ch, reason: reason.trim() });
    if (r.ok) { close(); fillDetails(); }
    toast(r.msg || "", !r.ok);
    if (r.ok && ["Distributed Date", "Car No", "Driver name"].some(k => ch[k])) districtReminder(ids);
  };
}

async function districtReminder(ids) {
  const r = await api("/api/district/remaining", { uids: ids });
  if (!r.ok || !r.districts.length) return;
  const skipped = new Set();
  const c = el("div"); c.appendChild(el("h2", null, "Left in the same district"));
  c.appendChild(el("p", "hint", "Each invoice is one row. Skip changes nothing. Choose a status and press Add, then enter vehicle, driver, line and Distributed Date before confirming."));
  for (const d of r.districts) {
    c.appendChild(el("h3", null, `${d.district}: you prepared ${d.prepared}, ${d.remaining.length} still waiting`));
    const box = el("div"); box.style.cssText = "max-height:200px;overflow:auto;border:1px solid #ccd;padding:4px;font-size:13px";
    for (const x of d.remaining) {
      const row = el("div"); row.style.cssText = "display:flex;gap:8px;align-items:center;padding:2px 0;border-bottom:1px solid #eee";
      const txt = el("span", null, `${x.customer} | ${x.invoice} | ${x.date}${x.age_days != null ? " | " + x.age_days + "d" : ""}`); txt.style.flex = "1";
      const status=el("select","in");status.style.width="150px";
      for(const name of S.statuses){const option=el("option",null,name);option.value=name;status.appendChild(option);}status.value="Undelivered";
      const reason=el("input","in");reason.placeholder="Reason if Cancelled";reason.style.width="150px";reason.style.display="none";status.onchange=()=>reason.style.display=status.value==="Cancelled"?"":"none";
      const add=el("button","btn accent","Add"),sk=el("button","btn","Skip");
      sk.onclick=()=>{skipped.add(x.uid);row.style.opacity="0.4";status.disabled=add.disabled=sk.disabled=true;};
      add.onclick=async()=>{if(status.value==="Undelivered")return toast("Choose the invoice status before Add.",true);
        const form=el("div");form.appendChild(el("h2",null,"Add invoice to dispatch"));form.appendChild(el("p",null,`${x.customer} | ${x.invoice} | ${status.value}`));
        form.appendChild(el("p","hint","Enter the dispatch details for this invoice. Nothing is saved until you confirm."));
        const grid=el("div","mgrid"),inputs={};form.appendChild(grid);
        for(const [field,label]of [["Car No","Vehicle (Car No)"],["Driver name","Driver name"],["Line","Line"],["Distributed Date","Distributed Date (DD/MM/YYYY)"]]){
          const f=el("div","fld"),i=el("input","in");i.dataset.districtField=field;i.placeholder=label;f.append(el("label",null,label),i);grid.appendChild(f);inputs[field]=i;
        }
        const actions=el("div","mrow"),cancel=el("button","btn","Cancel"),confirm=el("button","btn accent","Confirm Add");actions.append(cancel,confirm);form.appendChild(actions);
        const prompt=modal(form,"650px");prompt.ov.dataset.dismiss="no";cancel.onclick=prompt.close;
        confirm.onclick=async()=>{
          const changes={"Invoice Status":status.value};for(const field in inputs){const value=inputs[field].value.trim();if(!value){inputs[field].focus();return toast(field+" is required.",true);}changes[field]=value;}
          confirm.disabled=true;
          const rr=await api("/api/edit/all",{uid:x.uid,changes,reason:reason.value});
          if(!rr.ok){confirm.disabled=false;return toast(rr.need_reason?"Cancelled requires a reason.":rr.msg||"Not saved.",true);}
          prompt.close();row.style.opacity="0.4";status.disabled=add.disabled=sk.disabled=true;toast("Invoice status and dispatch details saved locally.");fillDetails();
        };
      };
      row.style.flexWrap="wrap";row.append(txt,status,reason,add,sk);box.appendChild(row);
    }
    c.appendChild(box);
  }
  const ok = el("button", "btn accent", "Close"); c.appendChild(ok); const m = modal(c, "1050px"); ok.onclick = m.close;
}

/* ---------------- RGR ---------------- */
let FR, rgrGrid;
function initRgr() {
  FR = makeFilters($("#rgr-filters"), fillRgr);
  rgrGrid = new Grid($("#rgr-grid"), {
    cols: S.rgrCols, editable: new Set(["Cost Date Required", "Cost Date", "Remarks"]),
    locked: new Set(), statusList: S.statuses, dateCols: S.dateCols,
    listFor: () => null, onEdit: editFieldRgr, onHead: c => { FR.cfc.value = c; FR.cfv.focus(); },
  });
  $("#rgr-del").onclick = async () => {
    const ids = rgrGrid.selected();
    if (ids.length && await askBox("Delete", `Delete ${ids.length} invoice(s) permanently?`)) {
      const r = await api("/api/delete", { uids: ids });
      toast(r.msg || "", !r.ok); fillRgr();
    }
  };
  $("#rgr-print").onclick = () => printResults("rgr");
}
async function editFieldRgr(uid, col, val, reason) {
  const r = await api("/api/edit", { uid, name: col, value: val, reason });
  if (r.ok) fillRgr();
  return r;
}
async function fillRgr() {
  const p = await apiQ("/api/query/rgr", { f: FR.vals() });
  const remarksIndex = rgrGrid.cols.indexOf("Remarks");
  const showRemarks = remarksIndex >= 0 && p.rows.some(r => String(r.v[remarksIndex] || "").trim());
  rgrGrid.vis = rgrGrid.cols.map((c,i) => i).filter(i => i !== remarksIndex || showRemarks);
  rgrGrid.setRows(p.rows);
  $("#rgr-cnt").textContent = `${p.total} invoices` +
    (p.total > p.shown ? `  (showing the newest ${p.shown})` : "");
}
