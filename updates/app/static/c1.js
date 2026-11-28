/* Distribution Program - browser UI core. Designed & developed by Eng. Kirollos William (c) 2026 */
"use strict";
const $ = s => document.querySelector(s);
const el = (t, c, txt) => { const e = document.createElement(t); if (c) e.className = c;
  if (txt != null) { const tr = (typeof T === "function" ? T(txt) : txt); if (tr !== txt) e.dataset.en = txt; e.textContent = tr; } return e; };

/* ---------------- API ---------------- */
let DATA_V = -1;
async function api(path, body) {
  const r = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}) });
  if (r.status === 401) { showLogin(); throw { auth: true }; }
  return r.json();
}
async function apiQ(path, body) {           // GET-like query (POST for JSON body)
  return api(path, body);
}
function fileB64(file) {
  return new Promise((res, rej) => {
    const rd = new FileReader();
    rd.onload = () => res(rd.result.split(",")[1]);
    rd.onerror = rej;
    rd.readAsDataURL(file);
  });
}
function pickFile(accept) {
  return new Promise(res => {
    const f = $("#filepick");
    f.accept = accept || ".xlsx,.xlsm,.json";
    f.value = "";
    f.onchange = () => res(f.files[0] || null);
    f.oncancel = () => res(null);
    f.click();
  });
}

/* ---------------- toast + modal dialogs (promise based) ---------------- */
let toastT = null;
function toast(msg, err) {
  const t = $("#toast");
  t.textContent = msg;
  t.className = "toast" + (err ? " err" : "");
  clearTimeout(toastT);
  toastT = setTimeout(() => t.classList.add("hidden"), err ? 7000 : 4000);
}
function modal(content, wide) {
  const ov = el("div", "overlay");
  const m = el("div", "modal");
  if (wide) m.style.width = wide;
  m.appendChild(content);
  ov.appendChild(m);
  $("#modal-root").appendChild(ov);
  ov.addEventListener("mousedown", e => { if (e.target === ov && ov.dataset.dismiss !== "no") close(ov); });
  function close() { ov.querySelectorAll('.ac').forEach(n => { if (n.close) n.close(); }); ov.remove(); }
  ov._homeExit=()=>{close();return true;};
  return { ov, close };
}
function msgBox(title, text, err) {
  const c = el("div");
  c.appendChild(el("h2", null, title));
  c.appendChild(el("div", "msgbox", text));
  const row = el("div", "mrow");
  const ok = el("button", "btn accent", "OK");
  row.appendChild(ok);
  c.appendChild(row);
  const { close } = modal(c, "480px");
  ok.onclick = close;
  if (err) c.querySelector("h2").style.color = "#b91c1c";
}
function askBox(title, text) {
  return new Promise(res => {
    const c = el("div");
    c.appendChild(el("h2", null, title));
    c.appendChild(el("div", "msgbox", text));
    const row = el("div", "mrow");
    const no = el("button", "btn", "No"), yes = el("button", "btn accent", "Yes");
    row.append(no, yes); c.appendChild(row);
    const { ov, close } = modal(c, "440px");
    ov._homeExit=()=>{close();res(false);return true;};
    no.onclick = () => { close(); res(false); };
    yes.onclick = () => { close(); res(true); };
  });
}
function promptBox(title, label, secret) {
  return new Promise(res => {
    const c = el("div");
    c.appendChild(el("h2", null, title));
    const f = el("div", "fld");
    f.appendChild(el("label", null, label));
    const inp = el("input", "in");
    if (secret) inp.type = "password";
    f.appendChild(inp); c.appendChild(f);
    const row = el("div", "mrow");
    const cn = el("button", "btn", "Cancel"), ok = el("button", "btn accent", "OK");
    row.append(cn, ok); c.appendChild(row);
    const { ov, close } = modal(c, "440px");
    ov._homeExit=()=>{close();res(null);return true;};
    cn.onclick = () => { close(); res(null); };
    const go = () => { const v = inp.value; close(); res(v); };
    ok.onclick = go;
    inp.onkeydown = e => { if (e.key === "Enter") go(); };
    setTimeout(() => inp.focus(), 50);
  });
}

/* ---------------- context menu ---------------- */
function ctxMenu(x, y, items) {
  document.querySelectorAll(".ctx").forEach(e => e.remove());
  const m = el("div", "ctx");
  for (const it of items) {
    if (it === "-") { m.appendChild(el("hr")); continue; }
    const b = el("button", null, it.label);
    b.onclick = () => { m.remove(); it.fn(); };
    m.appendChild(b);
  }
  document.body.appendChild(m);
  m.style.left = Math.min(x, innerWidth - m.offsetWidth - 8) + "px";
  m.style.top = Math.min(y, innerHeight - m.offsetHeight - 8) + "px";
  const kill = e => { if (!m.contains(e.target)) { m.remove(); document.removeEventListener("mousedown", kill); } };
  document.addEventListener("mousedown", kill);
}

/* ---------------- autocomplete (port of AutoCombo) ---------------- */
function autoCombo(opts) {
  const box = el("span", "ac"), inp = el("input", "ac-input");
  const arrow = el("button", "ac-arrow", "▾");
  arrow.type = "button"; arrow.tabIndex=-1;arrow.title = "Open list"; arrow.setAttribute("aria-label", "Open list");
  inp.setAttribute("autocomplete", "off"); inp.setAttribute("role", "combobox");
  inp.setAttribute("aria-autocomplete", "list"); inp.setAttribute("aria-expanded", "false");
  if (opts.placeholder) inp.placeholder = opts.placeholder;
  if (opts.value) inp.value = opts.value;
  if (opts.readonlyList) { inp.readOnly = true; inp.style.cursor = "pointer"; }
  const clear = el("button", "ac-clear", "×"); clear.type="button";clear.tabIndex=-1;clear.title="Clear selection";clear.setAttribute("aria-label","Clear selection");
  if (!opts.readonlyList) box.append(inp, clear, arrow); else box.append(inp, arrow);
  let selectedValue = opts.value || null, autoTyped="", autoPicked=false, choosing=false;
  function clearValue(){autoPicked=false;autoTyped="";selectedValue=null;inp.value="";inp.dispatchEvent(new Event("input",{bubbles:true}));inp.dispatchEvent(new Event("change",{bubbles:true}));close();inp.focus();}
  clear.onmousedown=e=>{e.preventDefault();clearValue();};
  let pop = null, items = [], sel = -1;
  const vals = () => (opts.getvals() || []).map(String);
  const key = v => String(v).replace(/[\u200e\u200f]/g, "").trim().replace(/\s+/g, " ").toLowerCase();
  const matches = () => {
    const t = key(inp.value);
    if (!t) return [];
    return vals().filter(v => key(v).includes(t)).sort((a,b) =>
      (key(a).startsWith(t) ? 0 : 1) - (key(b).startsWith(t) ? 0 : 1) || key(a).indexOf(t)-key(b).indexOf(t));
  };
  const fullValues = () => {
    const all = vals(), t = key(inp.value), m = matches();
    return opts.fullList || opts.readonlyList || !t || all.some(v => key(v) === t) || !m.length ? all : m;
  };
  function position() {
    if (!pop) return;
    if (!inp.isConnected) { close(); return; }
    const r = inp.getBoundingClientRect(), gap = 4;
    const width = Math.min(innerWidth-16, Math.max(r.width, Math.min(560, Math.max(...items.map(v=>v.length))*8.4+34)));
    pop.style.width = width + "px";
    pop.style.left = Math.max(8, Math.min(document.documentElement.dir === "rtl" ? r.right-width : r.left, innerWidth-width-8)) + "px";
    const below = innerHeight-r.bottom-8, above = r.top-8;
    const up = below < Math.min(180, pop.scrollHeight) && above > below;
    pop.style.maxHeight = Math.max(35, Math.min(260, up ? above-gap : below-gap)) + "px";
    pop.style.top = (up ? Math.max(8,r.top-pop.offsetHeight-gap) : r.bottom+gap) + "px";
  }
  function open(list, typed=false) {
    close(); items = typed ? list.slice(0,15) : list; sel=-1;
    if (!items.length) return;
    pop = el("div", "ac-pop"); pop.setAttribute("role","listbox");
    items.forEach(v => { const d=el("div","ac-item",v); d.setAttribute("role","option");
      d.onmousedown=e=>{e.preventDefault();choose(v);}; pop.appendChild(d); });
    document.body.appendChild(pop); inp.setAttribute("aria-expanded","true"); position();
    window.addEventListener("resize",close); document.addEventListener("scroll",onScroll,true);
  }
  function onScroll(e) { if (pop && (e.target === pop || pop.contains(e.target))) return; close(); }
  function mark() { if(pop) [...pop.children].forEach((d,i)=>d.classList.toggle("on",i===sel)); }
  function close() { if(pop){pop.remove();pop=null;} inp.setAttribute("aria-expanded","false");
    window.removeEventListener("resize",close); document.removeEventListener("scroll",onScroll,true); }
  function choose(v,automatic=false) {
    autoPicked=automatic;choosing=true;inp.value=v;selectedValue=v;
    inp.dispatchEvent(new Event("input",{bubbles:true}));
    inp.dispatchEvent(new Event("change",{bubbles:true}));
    close();choosing=false; if(opts.onPick) opts.onPick(v);
    if(!autoPicked&&!opts.onPick)focusNextField(inp);
  }
  arrow.onmousedown=e=>{e.preventDefault(); if(pop){close();return;} inp.focus();open(fullValues());};
  inp.addEventListener("input",()=>{if(!inp.readOnly&&!choosing){const m=matches();m.length?open(m,true):close();
    if(opts.autoNearest&&key(inp.value).length>=2){const t=key(inp.value);autoTyped=inp.value;const score=v=>{const k=key(v);return k===t?0:k.startsWith(t)?1:2;};const best=m.filter(v=>score(v)===Math.min(...m.map(score)));if(best.length===1){choose(best[0],true);}}}});
  inp.addEventListener("focus",()=>{if(opts.readonlyList)open(vals());});
  inp.addEventListener("click",()=>{if(opts.readonlyList)open(vals());});
  inp.addEventListener("keydown",e=>{
    if(autoPicked&&e.key.length===1&&!e.ctrlKey&&!e.metaKey&&!e.altKey){inp.value=autoTyped;inp.setSelectionRange(inp.value.length,inp.value.length);autoPicked=false;selectedValue=null;}
    if((e.key==="Backspace"||e.key==="Delete")&&!inp.readOnly&&selectedValue!==null&&inp.value===selectedValue){e.preventDefault();clearValue();return;}
    if(e.key==="ArrowDown"||e.key==="ArrowUp"){
      if(!pop){open(fullValues());e.preventDefault();return;}
      sel=Math.max(0,Math.min(items.length-1,sel+(e.key==="ArrowDown"?1:-1)));
      mark(); pop.children[sel].scrollIntoView({block:"nearest"}); e.preventDefault();
    }else if(e.key==="Enter"){
      if(autoPicked){autoPicked=false;e.preventDefault();e.stopPropagation();focusNextField(inp);return;}
      if(pop&&items.length){choose(items[Math.max(0,sel)]);e.preventDefault();e.stopPropagation();}
    }else if(e.key==="Tab"){autoPicked=false;if(pop&&items.length)choose(items[Math.max(0,sel)]);}
    else if(e.key==="Escape")close();
  });
  inp.addEventListener("blur",()=>setTimeout(close,180));
  box.isAc=true;box.val=()=>inp.value;box.set=v=>{inp.value=v;selectedValue=v||null;};box.input=inp;box.close=close;
  return box;
}

async function returnHome(){for(const ov of [...document.querySelectorAll("#modal-root > .overlay")].reverse()){if(ov._homeExit&&!(await ov._homeExit()))return;}document.querySelectorAll(".ctx").forEach(n=>n.remove());go("home");}

function focusNextField(input){const scope=input.closest(".modal")||input.closest("section")||document;const fields=[...scope.querySelectorAll("input,select,textarea,button.btn")].filter(n=>!n.disabled&&!n.readOnly&&n.tabIndex!==-1&&n.getClientRects().length);const next=fields[fields.indexOf(input)+1];if(next)setTimeout(()=>next.focus(),0);}
document.addEventListener("keydown",e=>{if(e.key!=="Enter"||e.defaultPrevented||e.target.tagName!=="INPUT"||e.target.closest(".ac")||e.target.classList.contains("cell-editor"))return;if(e.target.closest(".modal")&&e.target.dataset.classificationStatus)return;e.preventDefault();focusNextField(e.target);});
document.addEventListener("change",e=>{if(e.target.tagName==="SELECT")focusNextField(e.target);});
