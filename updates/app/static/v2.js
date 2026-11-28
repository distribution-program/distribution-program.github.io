/* Distribution Program views (2/2): home, new invoice + import wizard, route reports, head office, warehouse. */
"use strict";

/* ---------------- home ---------------- */
const TILE_COLORS=["#2563eb","#7c3aed","#0f766e","#c2410c","#be185d","#0369a1","#4d7c0f","#a16207","#4338ca","#b91c1c","#047857","#6d28d9"];
const NAV_GROUPS = [
 ["Search Invoice", "#2563eb", [["Search Invoice", "search"]]],
 ["New Invoice", "#16a34a", [["New Invoice", "new"]]],
 ["Undelivered", "#ea580c", [["Undelivered", "und"]]],
 ["Invoice Details", "#0f766e", [["Invoice Details", "details"], ...[]]],
 ["Invoice Report", "#db2777", [["Proposal Report", "rep:Proposal"], ["In Process Report", "rep:inprocess"], ["Invoice to Head Office", "ho"]]],
 ["Warehouse Report", "#0891b2", [["Warehouse Report", "wh"]]],
 ["RGR Not Costed", "#475569", [["RGR Not Costed", "rgr"]]],
];
function buildHome(group=null) {
 const g=$("#home-grid");g.innerHTML="";
 const h=$("#v-home h1");h.textContent=T(group===null?"Home":NAV_GROUPS[group][0]);
 if(group===null){
  NAV_GROUPS.forEach(([title,color],i)=>{
   const b=el("button","nav-main",title);b.style.setProperty("--tile-color",color);b.dataset.category=i;
   b.onclick=()=>go("group:"+i);g.appendChild(b);
  });
  for(const [title,key,color] of [["In Process Report","rep:inprocess","#7c3aed"],["Proposal Report","rep:Proposal","#db2777"]]){const b=el("button","nav-main",title);b.style.setProperty("--tile-color",color);b.dataset.shortcut=key;b.onclick=()=>go(key);g.appendChild(b);}
  const reviewButton=el("button","nav-main","Plan Review");reviewButton.id="t-review";reviewButton.style.setProperty("--tile-color","#0369a1");reviewButton.onclick=reviewPlans;g.appendChild(reviewButton);if(typeof drvdelTile==="function")drvdelTile(g);
 }else{
  const [title,color,base]=NAV_GROUPS[group];
  const items=group===3?[["Invoice Details","details"],...S.statuses.map(s=>[s,"s:"+s])]:base;
  let tileIndex=0;for(const [label,key] of items){const b=el("button","nav-subtile",label);b.style.setProperty("--tile-color",TILE_COLORS[tileIndex++%TILE_COLORS.length]);b.dataset.destination=key;b.onclick=()=>go(key);g.appendChild(b);}
 }
 if(group===null){const cb=el('button','nav-main','Cash');cb.id='home-cash';cb.style.setProperty('--tile-color','#0369a1');cb.onclick=cashMenu;const cd=el('span','home-description','Cash invoice collection and Expenses.');cd.style.cssText='display:block;font-size:13px;font-weight:400;margin-top:10px';cb.append(cd);g.append(cb);const b=el('button','nav-main','Other');b.id='home-other';b.style.setProperty('--tile-color','#475569');b.onclick=otherMenu;const desc=el('span','home-description','Conflict review.');desc.style.cssText='display:block;font-size:13px;font-weight:400;margin-top:10px';b.append(desc);g.append(b);void updateOtherIndicator();}
 if(typeof decorateHomeDescriptions==='function')decorateHomeDescriptions();
 if(typeof applyHomePermissions==='function')applyHomePermissions();
 if(group===null&&typeof applyHomeLayout==='function')applyHomeLayout();
 if(typeof applyTopbarLayout==='function')applyTopbarLayout();
}

const DISPATCH_FIELDS=["Driver name","Car No","Line","Distribution Rep","Distributed Date"];
function dispatchControls(container,rec,onInput){
 const wrap=el("div","dispatch-wrap"),label=el("label","dispatch-toggle"),check=el("input");check.type="checkbox";check.dataset.dispatch="toggle";
 label.append(check,el("span","slab","Prepare dispatch now"));wrap.appendChild(label);
 const panel=el("div","mgrid hidden");panel.style.marginTop="12px";const widgets={};
 for(const name of DISPATCH_FIELDS){const f=el("div","fld");f.appendChild(el("label",null,name));let w;
  if(name==="Line"){const input=el("select","in");for(const v of ["","1","2","3","4","5"]){const o=el("option",null,v);o.value=v;input.appendChild(o);}w={input,val:()=>input.value};}
  else if(S.listFields[name])w=autoCombo({getvals:()=>listFor(name)});
  else {const input=el("input","in");w={input,val:()=>input.value};}
  w.input.value=rec[name]||"";w.input.dataset.dispatchField=name;f.appendChild(w.isAc?w:w.input);widgets[name]=w;panel.appendChild(f);
 }
 const f=el("div","fld");f.appendChild(el("label",null,"Invoice Status"));const stage=el("select","in");stage.dataset.dispatchField="Invoice Status";
 for(const v of ["","Proposal","inprocess"]){const o=el("option",null,v||"Choose stage");o.value=v;stage.appendChild(o);}stage.value=["Proposal","inprocess"].includes(rec["Invoice Status"])?rec["Invoice Status"]:"";f.appendChild(stage);panel.appendChild(f);
 check.checked=rec._dispatch_enabled===true;panel.classList.toggle("hidden",!check.checked);
 check.onchange=()=>{panel.classList.toggle("hidden",!check.checked);onInput&&onInput()};wrap.appendChild(panel);container.appendChild(wrap);
 const vals=()=>Object.fromEntries([...DISPATCH_FIELDS.map(n=>[n,widgets[n].val()]),["Invoice Status",stage.value]]);
 panel.addEventListener("input",()=>onInput&&onInput());panel.addEventListener("change",()=>onInput&&onInput());
 return {check,panel,vals,stage};
}

/* ---------------- new invoice ---------------- */
const NEWF = {};
function initNew() {
  const form = $("#new-form");
  form.innerHTML = "";
  for (const c of S.base.slice(1)) {
    const f = el("div", "fld");
    f.appendChild(el("label", null, c));
    let w;
    if (c === "Invoice Status") {
      w = autoCombo({ getvals: () => S.statuses, readonlyList: true });
    } else if (S.listFields[c]) {
      w = autoCombo({ autoNearest:c==="Customer Name",getvals: () => listFor(c, NEWF["Customer Name"] ? NEWF["Customer Name"].val() : ""),
                      fullList: c === "Customer Name" });
    } else {
      const inp = el("input", "in");
      w = { input: inp, val() { return this.input.value; }, set(v) { this.input.value = v; } };
    }
    const node = w.isAc ? w.input.parentElement : w.input;
    f.appendChild(node);
    form.appendChild(f);
    NEWF[c] = w;
  }
  const dispatchLabel=el("label","dispatch-toggle"),dispatchCheck=el("input");dispatchCheck.type="checkbox";dispatchCheck.id="new-dispatch-toggle";dispatchLabel.append(dispatchCheck,el("span","slab","Prepare dispatch now"));form.before(dispatchLabel);
  const dispatchNodes=DISPATCH_FIELDS.map(n=>NEWF[n].input.closest(".fld"));dispatchNodes.forEach(n=>n.classList.add("hidden"));
  const stageField=el("div","fld hidden");stageField.appendChild(el("label",null,"Dispatch stage"));const stageChoice=el("select","in");stageChoice.id="new-dispatch-stage";for(const v of ["","Proposal","inprocess"]){const o=el("option",null,v||"Choose stage");o.value=v;stageChoice.appendChild(o);}stageField.appendChild(stageChoice);form.appendChild(stageField);
  dispatchCheck.onchange=()=>{dispatchNodes.forEach(n=>n.classList.toggle("hidden",!dispatchCheck.checked));stageField.classList.toggle("hidden",!dispatchCheck.checked);saveNewDraft();};
  stageChoice.onchange=()=>{if(stageChoice.value)NEWF["Invoice Status"].set(stageChoice.value);saveNewDraft();};
  // changing the customer always changes the district; clearing the customer clears the district
  const cust = NEWF["Customer Name"], dist = NEWF["District"];
  let lastC = "";
  cust.input.addEventListener("input", () => {
    const t = cust.val().trim();
    if (t === lastC) return;
    lastC = t;
    const m = S.cdMap[norm(t)];
    if (!t) dist.set("");
    else if (m) dist.set(m.length === 1 ? m[0] : "");
  });
  cust.input.addEventListener("blur", () => {
    const t = cust.val().trim(), m = S.cdMap[norm(t)];
    if (t && !m) dist.set("");
  });
  $("#new-save").onclick = saveManual;
  $("#new-clear").onclick = clearForm;
  $("#new-import").onclick = importNew;
  for(const c of S.base.slice(1))NEWF[c].set(c==="Invoice Status"?"Undelivered":"");
  const hint=recoveredHint($("#new-form").parentElement,"Input is saved locally while typing. Complete Save invoice to add it to stages and sync.");hint.id="new-draft-state";
  $("#new-form").addEventListener("input",saveNewDraft);
  $("#new-form").addEventListener("change",saveNewDraft);
}
function saveNewDraft(){const fields={};for(const c of S.base.slice(1))fields[c]=NEWF[c].val();fields._dispatch_enabled=$("#new-dispatch-toggle")?.checked||false;fields._dispatch_stage=$("#new-dispatch-stage")?.value||"";draftWrite("new",fields);if($("#new-draft-state"))$("#new-draft-state").textContent="Input saved locally. Not yet a completed invoice or synced.";}
function restoreNewDraft(){const d=draftRead("new");if(d){for(const c of S.base.slice(1))NEWF[c].set(d[c]||"");const check=$("#new-dispatch-toggle");check.checked=d._dispatch_enabled===true;$("#new-dispatch-stage").value=d._dispatch_stage||"";check.onchange();}}
function showDraftRecovery(){
 const d=draftRead("classification");if(!d)return;
 const c=el("div");c.appendChild(el("h2",null,"Recover unfinished classification"));recoveredHint(c,"Your input was saved locally. It has not been added to invoice stages or synced.");
 const b=el("button","btn accent","Resume classification");c.appendChild(b);const m=modal(c,"560px");b.onclick=()=>{m.close();classifyWizard(d.recs,d.i,d.saved)};
}
function clearForm() {
  for (const c of S.base.slice(1)) NEWF[c].set(c === "Invoice Status" ? "Undelivered" : "");
  if($("#new-dispatch-toggle")){$("#new-dispatch-toggle").checked=false;$("#new-dispatch-toggle").onchange();$("#new-dispatch-stage").value="";}
  if(typeof draftDrop==="function")draftDrop("new");
}
async function saveManual() {
  const fields = {};
  for (const c of S.base.slice(1)) fields[c] = NEWF[c].val().trim();
  const miss = S.required.filter(c => !fields[c]);
  if (miss.length) return msgBox("Missing", "Required: " + miss.join(", "));
  let reason = "";
  if (fields["Invoice Status"] === "Cancelled") {
    reason = await promptBox("Cancelled invoice", "Why is this invoice cancelled?");
    if (reason === null || !reason.trim()) return;
  }
  const r = await api("/api/new", { fields, reason: reason.trim() });
  if (r.need_reason) return;
  if (r.ok) { toast(r.msg); clearForm(); }
  else msgBox("Not saved", r.msg || "", true);
}

/* ---- import new invoices + one-by-one classification wizard ---- */
async function importNew() {
  const f = await pickFile(".xlsx,.xlsm");
  if (!f) return;
  toast("Reading the Excel file...");
  let r;
  try { r = await api("/api/import/new", { file: await fileB64(f) }); }
  catch (e) { if (!e.auth) msgBox("Import", "Could not read the Excel file. Nothing was saved.", true); return; }
  finally { clearTimeout(toastT); $("#toast").classList.add("hidden"); }
  if (!r.ok) return msgBox("Import", r.msg || "");
  classifyWizard(r.recs, 0, 0);
}
function classifyWizard(recs, i, saved) {
  if (i >= recs.length) {
    draftDrop("classification");
    msgBox("Done", `Saved ${saved} of ${recs.length} invoices.`);
    go("s:Undelivered");
    return;
  }
  const rec = recs[i];
  const persist=()=>draftWrite("classification",{recs,i,saved});persist();
  const c = el("div");
  c.appendChild(el("h2", null, `Invoice ${i + 1} of ${recs.length}`));
  const info = el("div", "mgrid classification-info");
  for (const [lab, k] of [["Invoice", "Invoice Number"], ["Created date", "Invoice Date"],
                          ["Sales Order No", "Sales Order No"], ["Customer", "Customer Name"],
                          ["Amount", "Invoice Value"], ["Sales Taker", "Sales Taker"],
                          ["Terms of payment (Excel)", "_terms"]]) {
    const f = el("div", "fld");
    f.appendChild(el("label", null, lab));
    f.appendChild(el("div", "cnt", String(rec[k] || "")));
    info.appendChild(f);
  }
  c.appendChild(info);
  const statusField=el("div","fld classification-status");statusField.appendChild(el("label",null,"Invoice Status"));const statusTop=el("input","in");statusTop.readOnly=true;statusTop.required=true;statusTop.dataset.classificationStatus="top";statusTop.value=["Proposal","inprocess"].includes(rec["Invoice Status"])?rec["Invoice Status"]:"Undelivered";statusField.appendChild(statusTop);info.appendChild(statusField);
  const F5 = ["District", "Forward To", "Invoice Type", "Payment Terms", "Brand Name"];
  const ws = {};
  const notesField = el("div", "fld");notesField.style.gridColumn="1 / -1";
  notesField.appendChild(el("label",null,"Remarks (optional)"));
  const notes=el("textarea","in");notes.rows=2;notes.style.cssText="width:100%;min-height:68px;height:68px;font:inherit;resize:vertical";notes.value=rec["Remarks"]||"";
  notes.dataset.field="Remarks";notes.placeholder="Delivery instructions / Gift recipient";notesField.appendChild(notes);
  const g = el("div", "mgrid");
  g.style.marginTop = "10px";
  for (const col of F5) {
    const f = el("div", "fld");
    f.appendChild(el("label", null, col));
    const w = autoCombo({ getvals: () => col === "District" ? districtsFor(rec["Customer Name"]) : listFor(col),
      onPick: () => { if (col === "Brand Name") setTimeout(()=>notes.focus(),0); } });
    w.set(rec[col] || (col === "District" ? (rec._district || "") : col === "Payment Terms" ? (rec._pt || "") : ""));
    f.appendChild(w.input.parentElement);
    ws[col] = w;
    g.appendChild(f);
  }
  c.appendChild(g);
  let dispatch;
  dispatch=dispatchControls(c,rec,()=>{if(!dispatch)return;rec._dispatch_enabled=dispatch.check.checked;Object.assign(rec,dispatch.vals());statusTop.value=dispatch.check.checked?(dispatch.stage.value||"Undelivered"):"Undelivered";rec["Invoice Status"]=statusTop.value;persist();});
  c.appendChild(notesField);
  let tabArrival=false;
  c.addEventListener("keydown",e=>{tabArrival=e.key==="Tab"&&!e.shiftKey;},true);
  dispatch.check.addEventListener("focus",()=>{if(tabArrival){tabArrival=false;dispatch.check.checked=true;dispatch.check.onchange();setTimeout(()=>dispatch.panel.querySelector("input,select").focus(),0);}});
  const draftHint=recoveredHint(c,"Input saved locally while typing. F2 saves and advances. Remarks is optional.");
  const recordInput=()=>{for(const name of F5)rec[name]=ws[name].val();rec.Remarks=notes.value;persist();draftHint.textContent="Input saved locally. F2 saves and advances. Remarks is optional.";};
  c.addEventListener("input",recordInput);c.addEventListener("change",recordInput);
  notes.addEventListener("keydown",e=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();e.stopPropagation();sv.click();}});
  const row = el("div", "mrow");
  const cl = el("button", "btn", "Close"), sk = el("button", "btn", "Skip (not saved)"),
        sv = el("button", "btn accent", "Save & next");
  row.append(cl, sk, sv);
  c.appendChild(row);
  const { ov, close } = modal(c, "860px");ov.querySelector(".modal").classList.add("classification-modal");
  ov.dataset.dismiss = "no";
  ws[F5.find(col => !ws[col].val()) || "District"].input.focus();
  ws["Brand Name"].input.addEventListener("keydown", e => { if (e.key === "Enter" && !e.defaultPrevented) {e.preventDefault();notes.focus();} });
  let committing=false;
  c.addEventListener("keydown",e=>{if(e.key==="F2"){e.preventDefault();e.stopPropagation();sv.click();}});
  sv.onclick = async () => {
    if(committing)return;
    const vals = {};
    for (const col of F5) vals[col] = ws[col].val().trim();
    const miss = F5.filter(col => !vals[col]);
    if (miss.length) { msgBox("Missing", "Required: " + miss.join(", ")); return; }
    const dispatchValues=dispatch.vals();
    const clean = Object.assign({}, rec, vals, {Remarks:notes.value,"Invoice Status":dispatch.check.checked?(dispatch.stage.value||"Undelivered"):"Undelivered"});
    if(dispatch.check.checked){Object.assign(clean,dispatchValues);clean["Invoice Status"]=dispatch.stage.value||"Undelivered";}
    else for(const name of DISPATCH_FIELDS)delete clean[name];
    delete clean._dispatch_enabled;
    committing=true;sv.disabled=true;
    let r;try{r=await api("/api/import/classify", { rec: clean });}catch(e){committing=false;sv.disabled=false;msgBox("Not saved","Local save not confirmed. Your draft is retained.",true);return;}
    committing=false;sv.disabled=false;
    if (r.ok) { close(); classifyWizard(recs, i + 1, saved + 1); }
    else msgBox("Not saved", r.msg || "", true);
  };
  ov._homeExit=async()=>{if(!(await askBox("Home","Return Home? Your unfinished classification input is kept for recovery, but not saved as completed invoices.")))return false;close();return true;};
  sk.onclick = () => { close(); classifyWizard(recs, i + 1, saved); };
  cl.onclick = async () => {
    const left = recs.length - i;
    if (left && !(await askBox("Close", `${left} invoice(s) are not saved yet.\nClose anyway?`))) return;
    close(); go("s:Undelivered");
  };
}

/* ---------------- route reports (Proposal / In Process) ---------------- */
const RB = {};
let repGrid;
function initReport() {
  const bar = $("#rep-bar");
  const mk = (lab, node) => { const f = el("div", "fld"); f.appendChild(el("label", null, lab)); f.appendChild(node); bar.appendChild(f); };
  RB.date = el("input", "in"); RB.date.size = 11; RB.date.placeholder = "dd/mm/yyyy";
  mk("Distributed Date", RB.date);
  RB.drv = autoCombo({ getvals: () => S.lists.drivers || [] });
  RB.drv.input.style.width = "230px";
  mk("Driver name", RB.drv.input.parentElement);
  RB.car = autoCombo({ getvals: () => S.lists.car_no || [] });
  RB.car.input.style.width = "110px";
  mk("Car No", RB.car.input.parentElement);
  RB.line = el("select", "in");
  RB.line.append(el("option", null, ""), ...["1", "2", "3", "4", "5"].map(x => el("option", null, x)));
  mk("Line", RB.line);
  const pr = el("button", "btn big accent", "Print");
  pr.onclick = printRoute;
  bar.appendChild(pr);
  const sv = el("button", "btn big", "Save PDF");
  sv.onclick = saveRoute;
  bar.appendChild(sv);
  repGrid = new Grid($("#rep-grid"), {
    cols: S.repCols, editable: new Set(["District", "Distributed Date", "Driver name", "Car No", "Line", "Remarks"]),
    locked: new Set(), statusList: S.statuses, dateCols: S.dateCols,
    listFor: (col, uid) => listFor(col, routeCust(uid)),
    onEdit: editFieldRoute,
  });
  let t = null;
  const deb = () => { clearTimeout(t); t = setTimeout(fillRoute, 700); };
  for (const n of [RB.date, RB.drv.input, RB.car.input]) n.addEventListener("input", deb);
  RB.line.onchange = deb;
}
function routeCust(uid) {
  const row = repGrid.rows.find(r => r.uid === uid);
  return row ? row.v[S.repCols.indexOf("Customer Name")] : "";
}
function routeF() { return { date: RB.date.value, drv: RB.drv.val(), car: RB.car.val(), line: RB.line.value }; }
async function fillRoute() {
  const p = await apiQ("/api/query/route", { rep: S.repStatus, f: routeF() });
  repGrid.setRows(p.rows);
  $("#rep-cnt").textContent = `Invoices ready for this report: ${p.ready}`;
}
function resetRoute() {
  const d = new Date();
  RB.date.value = `${String(d.getDate()).padStart(2, "0")}/${String(d.getMonth() + 1).padStart(2, "0")}/${d.getFullYear()}`;
  RB.drv.set(""); RB.car.set(""); RB.line.value = "";
  fillRoute();
}
async function editFieldRoute(uid, col, val, reason) {
  const r = await api("/api/edit", { uid, name: col, value: val, reason });
  if (r.ok) fillRoute();
  return r;
}
async function printRoute() {
  const r = await api("/api/pdf/route", { title: $("#rep-title").textContent, rep: S.repStatus, f: routeF() });
  toast(r.msg || "", !r.ok);
  if (r.ok) resetRoute();
}
async function saveRoute() {
  const r = await api("/api/pdf/route", { title: $("#rep-title").textContent, rep: S.repStatus, f: routeF(), save_only: true });
  toast(r.msg || "", !r.ok);
}

/* ---------------- head office ---------------- */
const HO = {};
function initHo() {
  const g = $("#ho-form");
  const mk = (lab, node) => { const f = el("div", "fld"); f.appendChild(el("label", null, lab)); f.appendChild(node); g.appendChild(f); };
  HO.from = el("input", "in"); HO.from.placeholder = "dd/mm/yyyy";
  mk("Date from", HO.from);
  HO.to = el("input", "in"); HO.to.placeholder = "dd/mm/yyyy";
  mk("Date to", HO.to);
  const sel = vals => { const s = el("select", "in"); s.append(el("option", null, ""), ...vals.map(v => el("option", null, v))); return s; };
  HO.fw = sel(S.forwardTo); mk("Forward To", HO.fw);
  HO.ty = sel(S.invoiceType); mk("Invoice Type", HO.ty);
  HO.pt = sel(S.paymentTerms); mk("Payment Terms", HO.pt);
  $("#ho-go").onclick = async () => {
    const r = await api("/api/pdf/ho", { f: { from: HO.from.value, to: HO.to.value, fw: HO.fw.value,
                                              ty: HO.ty.value, pt: HO.pt.value } });
    toast(r.msg || "", !r.ok);
  };
}

/* ---------------- warehouse ---------------- */
function initWh() {
  $("#wh-paper-check").onclick = () => openPaperCheck("so");
  $("#pi-paper-check").onclick = () => openPaperCheck("invoice");
  $("#wh-history").onclick = () => openWarehouseHistory("so");
  $("#pi-history").onclick = () => openWarehouseHistory("invoice");
  document.querySelectorAll(".tab").forEach(t => t.onclick = () => {
    document.querySelectorAll(".tab").forEach(x => x.classList.toggle("on", x === t));
    $("#wh-a").classList.toggle("hidden", t.dataset.tab !== "wh-a");
    $("#wh-b").classList.toggle("hidden", t.dataset.tab !== "wh-b");
  });
  $("#wh-import").onclick = () => importReportExcel("Warehouse import", "wh", whShow);
  $("#wh-print").onclick = () => whPrint(false);
  $("#wh-reprint").onclick = () => whPrint(true);
  $("#wh-savepdf").onclick = async () => {
    const r = await api("/api/pdf/wh", { all: true, save_only: true });
    toast(r.msg || "", !r.ok); if (r.ok) await whShow();
  };
  $("#pi-import").onclick = () => importReportExcel("Printed-invoice import", "pi", async () => { await piShow(); await whShow(); });
  $("#pi-pdf").onclick = async () => {
    const r = await api("/api/pdf/pinv", { f: { date: $("#pi-date").value, q: $("#pi-q").value } });
    toast(r.msg || "", !r.ok); if (r.ok) await piShow();
  };
  let t = null;
  const deb = () => { clearTimeout(t); t = setTimeout(piShow, 700); };
  $("#pi-date").addEventListener("input", deb);
  $("#pi-q").addEventListener("input", deb);
}
function plainTable(host, heads, rows) {
  host.innerHTML = "";
  const t = el("table", "gtab");
  const trh = el("tr");
  heads.forEach(h => trh.appendChild(el("th", null, h)));
  t.appendChild(el("thead")).appendChild(trh);
  const tb = el("tbody");
  rows.forEach((r, i) => {
    const tr = el("tr");
    if (i % 2) tr.classList.add("odd");
    r.forEach(v => tr.appendChild(el("td", null, v)));
    tb.appendChild(tr);
  });
  t.appendChild(tb);
  host.appendChild(t);
}
async function whShow() {
  const p = await apiQ("/api/query/wh");
  $("#wh-grid").style.maxHeight="52vh";
  const visible = warehouseIncomplete(p.rows, 3, 8);
  const hasOrderDate = visible.some(r => r[1]);
  const heads = ["Sales order", "Invoice Number", ...(hasOrderDate ? ["Sales order created date/time"] : []), "Invoice created date/time", "Customer name", "Print step", "Printed on", "Printed by", "Paper checked", "Status"];
  warehouseScrollTable($("#wh-grid"), heads, visible.map(r => [r[0], r[6], ...(hasOrderDate ? [r[1]] : []), r[7], r[2], r[3] ? "Done" : "Not done", r[4], r[5], r[8] ? "✓" : "☐", "Not done"]), "No incomplete sales orders. Use History search to find completed orders.");
  $("#wh-display-note").textContent = "Incomplete only: both Print step and Paper checked must be done to complete an order. Unchecked first. Scroll with the mouse wheel to load every incomplete order in batches of 50. Completed orders stay stored and can be found in History search. Print and PDF actions keep their existing scope.";
  $("#wh-cnt").textContent = `${visible.length} incomplete of ${p.total} stored orders | ${p.not_printed} not printed yet | ${p.invoice_linked} invoice-linked | ${p.invoice_unmatched} without match` + (p.invoice_conflicts ? ` | ${p.invoice_conflicts} conflicting source links` : "");
}
async function whPrint(all) {
  // Reserve the tab during the click, before awaiting the PDF generation request.
  const preview=window.open("about:blank","_blank");
  if(preview){preview.document.title="Preparing warehouse PDF";preview.document.body.textContent="Preparing warehouse PDF...";}
  let r;
  try{r=await api("/api/pdf/wh",{all});}
  catch(error){if(preview&&!preview.closed)preview.close();return msgBox("Warehouse PDF","Could not confirm PDF generation. No print status was changed. Try again when the connection is ready.",true);}
  if(!r.ok||!r.pdf_url){if(preview&&!preview.closed)preview.close();return msgBox("Warehouse PDF",r.msg||"PDF is unavailable.",true);}
  let opened=false;
  try{if(preview&&!preview.closed){preview.location.replace(r.pdf_url);opened=true;}}catch(error){}
  const content=el("div");content.appendChild(el("h2",null,"Warehouse PDF"));
  content.appendChild(el("p","hint",opened?"PDF opened in a new tab. Use its Print button or Ctrl+P to print manually.":"Your browser blocked the PDF tab. Use Open PDF below."));
  content.appendChild(el("p","hint",r.msg||""));
  const link=el("a","btn accent","Open PDF");link.href=r.pdf_url;link.target="_blank";link.rel="noopener";content.appendChild(link);
  content.appendChild(el("p","hint","Saved file on this PC (also works after the app stops):"));
  const path=el("input","in");path.readOnly=true;path.value=r.file_path||"";path.style.width="100%";path.onclick=()=>path.select();content.appendChild(path);
  const actions=el("div","mrow"),closeButton=el("button","btn","Close");actions.appendChild(closeButton);content.appendChild(actions);
  const box=modal(content,"680px");closeButton.onclick=box.close;
  whShow();
}
async function piShow() {
  const p = await apiQ("/api/query/pi", { f: { date: $("#pi-date").value, q: $("#pi-q").value } });
  $("#pi-grid").style.maxHeight="52vh";
  const visible = warehouseIncomplete(p.rows, 4, 7);
  warehouseScrollTable($("#pi-grid"), ["Invoice Number", "Sales order", "Customer name", "Created date and time", "Print step", "Printed on", "Entered By", "Paper checked", "Status"], visible.map(r => [...r.slice(0,4), r[4] ? "Done" : "Not done", r[5], r[6], r[7] ? "✓" : "☐", "Not done"]), "No incomplete invoices match these filters. Use History search to find completed invoices.");
  $("#pi-cnt").textContent = `${visible.length} incomplete of ${p.count} matching invoices. Unchecked first. Scroll to load all incomplete results; 50 is the initial batch only. Completed invoices stay in History search.` + (p.who.length ? ` | Entered by: ${p.who.join(", ")}` : "");
}


async function openPaperCheck(kind) {
 const isSO=kind==="so", label=isSO?"Sales Order Number":"Invoice Number";
 const content=el("div");content.id="paper-check-dialog";
 content.append(el("h2",null,isSO?"Check sales order paper":"Check invoice paper"),el("p","hint","Incomplete only. Both Print step and Paper checked must be done. Unchecked first. Scroll to load all incomplete items, 50 at a time. Completed documents are kept in History search."),el("p","hint",isSO?"Only sales order numbers are accepted here. Invoice-paper checks are separate.":"Only invoice numbers are accepted here. Delivery-note paper checks are separate."));
 const input=el("input","in");input.id="paper-check-number";input.placeholder=label;input.autocomplete="off";input.style.width="100%";content.append(el("label",null,label),input);
 const actions=el("div","mrow"),undo=el("button","btn","Undo check"),back=el("button","btn","Back");actions.append(undo,back);content.append(el("p","hint","Type the full number or the whole number after leading zeros, then Enter. Example:2310 matches002310, not012310. If several match, choose one. Undo uses the same search."),actions);
 const message=el("p","hint");message.id="paper-check-result";message.setAttribute("role","status");content.append(message);
 const list=el("div");list.style.cssText="max-height:42vh;overflow:auto";content.append(list);
 let active=true,busy=false;let refreshTimer=null;
 const choices=el("div");choices.id="paper-check-choices";content.insertBefore(choices,list);
 const render=async()=>{const result=await apiQ(isSO?"/api/query/wh":"/api/query/pi",isSO?{}:{f:{}});if(!active)return;
 const incomplete=warehouseIncomplete(result.rows,isSO?3:4,isSO?8:7);
 const entries=incomplete.map(r=>[r[0],r[2],r[isSO?3:4]?"Done":"Not done",r[isSO?8:7]?"✓":"☐","Not done"]);
 warehouseScrollTable(list,[label,"Customer name","Print step","Paper checked","Status"],entries,"No incomplete documents. Completed documents are kept in History search.");};
 const submit=async (checked,chosenNumber=null)=>{if(busy)return;busy=true;choices.innerHTML="";undo.disabled=true;input.disabled=true;
 try{const r=await api("/api/warehouse/paper-check",{kind,number:chosenNumber===null?input.value:chosenNumber,checked});message.textContent=r.msg||"Could not confirm the check.";message.style.color=r.duplicate?"#946116":r.ok?"#176235":"#b42318";
 if(r.choose){const title=el("p",null,"Choose the full document number:");choices.append(title);for(const candidate of r.candidates){const button=el("button","btn",candidate.number+" | "+candidate.customer+" | "+(candidate.created||"Date not supplied")+(candidate.checked?" | Checked":" | Not checked"));button.style.cssText="display:block;width:100%;text-align:left;margin:5px 0;white-space:normal";button.onclick=()=>submit(checked,candidate.number);choices.append(button);}choices.style.cssText="max-height:26vh;overflow:auto";}
 if(r.ok){await render();await whShow();await piShow();if(checked)input.value="";}}
 catch(e){message.textContent="Could not confirm the paper check. Check the table before retrying.";message.style.color="#b42318";}
 finally{busy=false;undo.disabled=false;input.disabled=false;input.focus();}};
 input.addEventListener("keydown",e=>{if(e.key==="Enter"){e.preventDefault();submit(true);}});undo.onclick=()=>submit(false);
 const box=modal(content,"1000px");back.onclick=()=>{active=false;clearInterval(refreshTimer);box.close();};await render();refreshTimer=setInterval(()=>{if(!content.isConnected){active=false;clearInterval(refreshTimer);return;}if(!busy)render().catch(()=>{});},2000);input.focus();
}


function warehouseIncomplete(rows, printIndex, checkIndex) {
 const newest=rows.slice().reverse().filter(r=>!(r[printIndex]&&r[checkIndex]));
 return newest.filter(r=>!r[checkIndex]).concat(newest.filter(r=>!!r[checkIndex]));
}

function warehouseScrollTable(host, heads, rows, emptyText="No matching rows.") {
 // A batch is a rendering unit, never a cap on unfinished records.
 const oldTop=host.scrollTop,initial=Math.max(50,Number(host.dataset.loadedRows)||50);
 let count=0;host.innerHTML="";const table=el("table","gtab"),thead=el("thead"),head=el("tr"),body=el("tbody");
 heads.forEach(h=>head.append(el("th",null,h)));thead.append(head);table.append(thead,body);host.append(table);
 const append=()=>{const end=Math.min(rows.length,count+50);for(;count<end;count++){const tr=el("tr",count%2?"odd":null);rows[count].forEach(v=>tr.append(el("td",null,v)));body.append(tr);}host.dataset.loadedRows=String(count);};
 do{append();}while(count<Math.min(initial,rows.length));host.scrollTop=oldTop;if(!rows.length)host.append(el("p","hint",emptyText));
 host.onscroll=()=>{if(host.scrollHeight-host.scrollTop-host.clientHeight<150&&count<rows.length)append();};
 // A tall viewport can hold the entire first batch. Fill until a scrollbar appears.
 requestAnimationFrame(()=>{while(count<rows.length&&host.scrollHeight<=host.clientHeight)append();});
 return ()=>count;
}

async function openWarehouseHistory(kind) {
 const isSO=kind==="so",label=isSO?"Sales Order Number":"Invoice Number",content=el("div");content.id="warehouse-history-dialog";
 content.append(el("h2",null,isSO?"Sales order history":"Invoice history"),el("p","hint","Read-only search includes complete and incomplete documents. Full numbers and whole numeric endings are accepted. Searching never marks paper."));
 const style=el("style");style.textContent="#warehouse-history-dialog{width:100%;min-width:0}#warehouse-history-dialog .history-results{max-height:52vh;overflow-y:auto;overflow-x:hidden;width:100%}#warehouse-history-dialog .gtab{width:100%;table-layout:fixed}#warehouse-history-dialog .gtab th,#warehouse-history-dialog .gtab td{min-width:0;max-width:none;white-space:normal;overflow-wrap:anywhere;word-break:normal;padding:8px 6px;font-size:13px}#warehouse-history-dialog .gtab th{font-size:12px}";content.append(style);
 const input=el("input","in");input.id="warehouse-history-number";input.placeholder=label;input.style.width="75%";const search=el("button","btn accent","Search"),line=el("div","mrow");const clear=el("button","btn","Clear search");line.append(input,search,clear);content.append(line);clear.onclick=()=>{input.value="";message.textContent="";list.replaceChildren();input.focus()};
 const message=el("p","hint"),list=el("div");message.id="warehouse-history-result";list.className="history-results";content.append(message,list);
 const run=async()=>{search.disabled=true;try{const r=await api("/api/warehouse/history",{kind,number:input.value});message.textContent=r.msg||"";if(!r.ok){list.innerHTML="";return;}warehouseScrollTable(list,[label,"Customer name","Created","Print step","Paper checked","Status","Paper checked by","Paper checked on"],r.rows.map(x=>[x.number,x.customer,x.created,x.printed?"Done":"Not done",x.paper_checked?"✓":"☐",x.printed&&x.paper_checked?"Done":"Not done",x.paper_checked_by,x.paper_checked_on]));}catch(e){message.textContent="Could not load history. Nothing was changed.";}finally{search.disabled=false;}};
 search.onclick=run;input.onkeydown=e=>{if(e.key==="Enter"){e.preventDefault();run();}};const back=el("button","btn","Back"),actions=el("div","mrow");actions.append(back);content.append(actions);const box=modal(content,"95vw");back.onclick=box.close;input.focus();
}
