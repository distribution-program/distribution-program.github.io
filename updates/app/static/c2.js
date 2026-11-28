/* Distribution Program grid: inline editing, keyboard navigation, multi-select (port of the desktop Sheet). */
"use strict";
class Grid {
  constructor(container, opts) {
    // opts: {cols, editable:Set, onEdit(uid,col,val,reason)->Promise{ok,need_reason,msg},
    //        onHead(col), extra:[{label,fn}], locked:Set, listFor(col,uid)->[values], statusList:[..], dateCols:Set}
    Object.assign(this, opts);
    this.root = container;
    this.vis = null;      // optional: visible column indices in display order (view-only hiding)
    this.rows = [];       // {uid, v:[..]}
    this.sel = new Set();
    this.cell = null;     // {r, c}
    this.meas = document.createElement("canvas").getContext("2d");
    this.meas.font = '600 14px "Segoe UI", Tahoma, Arial';
    this.render();
  }

  setRows(rows) {
    const keepCellUid = this.cell && this.rows[this.cell.r] ? this.rows[this.cell.r].uid : null;
    const keepSel = new Set(this.sel);
    const keepCol = this.cell ? this.cell.c : null;
    this.rows = rows;
    this.sel = new Set(rows.filter(r => keepSel.has(r.uid)).map(r => r.uid));
    this.cell = null;
    if (keepCellUid) {
      const i = rows.findIndex(r => r.uid === keepCellUid);
      if (i >= 0) this.cell = { r: i, c: keepCol };
    }
    this.render();
  }

  measure(s) { return this.meas.measureText(String(s)).width; }

  render() {
    this.root.innerHTML = "";
    const t = el("table", "gtab");
    const thead = el("thead"), trh = el("tr");
    const idxs = this.vis || this.cols.map((c, j) => j);
    // column widths sized by the longest visible value, like the desktop version
    this.widths = this.cols.map((c, j) => {
      let best = c;
      for (const r of this.rows) if (String(r.v[j]).length > best.length) best = String(r.v[j]);
      return Math.min(Math.max(this.measure(c) + 36, this.measure(best) + 24), 700);
    });
    idxs.forEach(j => {
      const c = this.cols[j];
      const th = el("th", null, c);
      th.style.minWidth = this.widths[j] + "px";
      th.onclick = () => this.onHead && this.onHead(c);
      trh.appendChild(th);
    });
    thead.appendChild(trh); t.appendChild(thead);
    const tb = el("tbody");
    this.rows.forEach((r, i) => {
      const tr = el("tr");
      tr.dataset.uid = r.uid;
      if (i % 2) tr.classList.add("odd");
      if (this.sel.has(r.uid)) tr.classList.add("sel");
      idxs.forEach(j => {
        const val = r.v[j];
        const td = el("td", null, val);
        td.title = val;
        td.style.minWidth = this.widths[j] + "px";
        td.style.maxWidth = "700px";
        tr.appendChild(td);
      });
      tb.appendChild(tr);
    });
    t.appendChild(tb);
    this.root.appendChild(t);
    this.table = t;
    this.bindEvents(t);
    this.drawCell();
  }

  rowEls() { return [...this.table.tBodies[0].rows]; }
  idxOf(uid) { return this.rows.findIndex(r => r.uid === uid); }

  bindEvents(t) {
    t.addEventListener("mousedown", e => {
      if(this.editing)return;
      const td = e.target.closest("td"); if (!td) return;
      const tr = td.parentElement, uid = tr.dataset.uid;
      const r = this.idxOf(uid);
      const c = this.vis ? this.vis[td.cellIndex] : td.cellIndex;
      if (e.button === 2) { this.onCtx(e, uid, r, c); return; }
      if (e.ctrlKey || e.metaKey) {
        this.sel.has(uid) ? this.sel.delete(uid) : this.sel.add(uid);
        this.anchor = r;
      } else if (e.shiftKey && this.anchor != null) {
        const [a, b] = [Math.min(this.anchor, r), Math.max(this.anchor, r)];
        for (let i = a; i <= b; i++) this.sel.add(this.rows[i].uid);
      } else {
        this.sel = new Set([uid]); this.anchor = r;
      }
      this.cell = { r, c };
      this.refreshSel();
      this.root.focus();
      if (e.detail === 2) {e.preventDefault();this.startEdit();}   // double click
    });
    this.root.tabIndex = 0;
    if (!this.keysBound) {
      this.root.addEventListener("keydown", e => this.onKey(e));
      this.root.addEventListener("contextmenu", e => e.preventDefault());
      this.keysBound = true;
    }
  }

  refreshSel() {
    for (const tr of this.rowEls()) tr.classList.toggle("sel", this.sel.has(tr.dataset.uid));
    this.drawCell();
  }

  drawCell() {
    this.table.querySelectorAll("td.cellcur").forEach(td => td.classList.remove("cellcur"));
    if (!this.cell) return;
    const trs = this.rowEls();
    const tr = trs[this.cell.r];
    if (!tr) return;
    const vi = this.vis ? this.vis.indexOf(this.cell.c) : this.cell.c;
    const td = vi >= 0 ? tr.cells[vi] : null;
    if (td) { td.classList.add("cellcur"); td.scrollIntoView({ block: "nearest", inline: "nearest" }); }
  }

  move(dc, dr) {
    if (!this.rows.length) return;
    if (!this.cell) this.cell = { r: 0, c: 0 };
    let { r, c } = this.cell;
    if (dc) {
      const idxs = this.vis || this.cols.map((x, j) => j);
      let vi = idxs.indexOf(c); if (vi < 0) vi = 0;
      vi += dc;
      if (vi >= idxs.length) { vi = 0; r = Math.min(this.rows.length - 1, r + 1); }
      else if (vi < 0) { vi = idxs.length - 1; r = Math.max(0, r - 1); }
      c = idxs[vi];
    }
    r = Math.max(0, Math.min(this.rows.length - 1, r + dr));
    this.cell = { r, c };
    this.sel = new Set([this.rows[r].uid]); this.anchor = r;
    this.refreshSel();
  }

  onKey(e) {
    if (this.editing) return;
    const k = e.key, code = e.code;
    if (k === "ArrowLeft" || (k === "Tab" && e.shiftKey)) { this.move(-1, 0); e.preventDefault(); }
    else if (k === "ArrowRight" || k === "Tab") { this.move(1, 0); e.preventDefault(); }
    else if (k === "ArrowUp") { this.move(0, -1); e.preventDefault(); }
    else if (k === "ArrowDown") { this.move(0, 1); e.preventDefault(); }
    else if (k === "Enter" || k === "F2") { this.startEdit(); e.preventDefault(); }
    else if ((e.ctrlKey || e.metaKey) && code === "KeyA") {      // layout-independent: works on Arabic keyboards
      this.rows.forEach(r => this.sel.add(r.uid)); this.refreshSel(); e.preventDefault();
    } else if ((e.ctrlKey || e.metaKey) && code === "KeyC") { this.copyCell(); e.preventDefault(); }
    else if ((e.ctrlKey || e.metaKey) && code === "KeyV") { this.pasteCell(); e.preventDefault(); }
  }

  curVal() {
    if (!this.cell) return "";
    return String(this.rows[this.cell.r].v[this.cell.c] || "");
  }

  copyCell() {
    if (!this.cell) return;
    navigator.clipboard.writeText(this.curVal()).catch(() => {});
  }

  pasteCell() {
    if (!this.cell) return;
    const col = this.cols[this.cell.c];
    if (!this.editable.has(col)) return;
    navigator.clipboard.readText().then(t => {
      const v = (t || "").split("\n")[0].trim();
      if (v) this.commit(this.rows[this.cell.r].uid, col, v);
    }).catch(() => {});
  }

  async startEdit() {
    if (!this.cell || this.editing) return;
    const { r, c } = this.cell;
    const uid = this.rows[r].uid, col = this.cols[c];
    if (!this.editable.has(col)) {
      if (this.locked.has(col)) toast(`'${col}' is locked - it comes from the system`);
      return;
    }
    const td = this.rowEls()[r].cells[this.vis ? this.vis.indexOf(c) : c];
    if (!td) return;
    const rect = td.getBoundingClientRect(), host = this.root.getBoundingClientRect();
    const old = this.curVal();
    this.editing = true;
    let ed, getv;
    if (this.statusList && col === "Invoice Status") {
      ed = autoCombo({ getvals: () => this.statusList, readonlyList: true, value: old });
      getv = () => ed.val();
    } else if (this.listFor && this.listFor(col, uid)) {
      ed = autoCombo({ getvals: () => this.listFor(col, uid), value: old, readonlyList: col === "Version" });
      getv = () => ed.val();
    } else {
      ed = el("input", "cell-editor"); ed.value = old;
      getv = () => ed.value;
    }
    const node = ed.isAc ? ed : ed;
    const input = ed.input || ed;
    node.classList.add("cell-editor");
    node.style.left = (rect.left - host.left + this.root.scrollLeft) + "px";
    node.style.top = (rect.top - host.top + this.root.scrollTop) + "px";
    node.style.width = Math.max(rect.width, 200) + "px";
    td.style.position="relative";node.style.position="absolute";node.style.left="0";node.style.top="0";node.style.width="100%";node.style.minWidth="0";td.appendChild(node);
    const draftKey="cell:"+uid+":"+col,recovered=draftRead(draftKey);
    if(recovered!==null){if(ed.isAc)ed.set(recovered);else input.value=recovered;}
    if(this.dateCols?.has(col)){input.placeholder="DD/MM/YYYY HH:MM:SS";input.title="Enter DD/MM/YYYY or YYYY-MM-DD, optional time. Blank clears this date.";}
    input.focus(); input.select && input.select();
    let done = false,autoTimer,savedValue=old,queue=Promise.resolve();
    const flush=()=>{clearTimeout(autoTimer);const v=getv().trim();draftWrite(draftKey,v);
      queue=queue.catch(()=>{}).then(async()=>{if(v===savedValue||(col==="Invoice Status"&&v==="Cancelled"))return;
       const a=await this.onEdit(uid,col,v,"");if(a?.ok){input.removeAttribute("aria-invalid");input.setCustomValidity?.("");savedValue=v;const row=this.rows.find(r=>r.uid===uid);if(row)row.v[c]=v;}else if(a?.msg){input.setAttribute("aria-invalid","true");input.setCustomValidity?.(a.msg);if(!this.dateCols?.has(col))toast("Input kept locally: "+a.msg,true);}
      });return queue;};
    input.addEventListener("input",()=>{draftWrite(draftKey,getv());clearTimeout(autoTimer);autoTimer=setTimeout(flush,250);});
    input.addEventListener("change",()=>{clearTimeout(autoTimer);flush();});
    const finish = async (ok, move) => {
      if (done) return; done = true;
      const v = getv().trim();
      await flush();
      if(ok && this.dateCols?.has(col) && v!==savedValue){done=false;input.focus();input.reportValidity?.();return false;}
      if (ed.close) ed.close();
      node.remove();
      this.editing = false;
      this.root.focus();
      if (ok && v !== savedValue) {const result=await this.commit(uid, col, v);if(result?.ok)savedValue=v;}
      if(v===savedValue)draftDrop(draftKey);
      if(this.refresh)await this.refresh();
      if (ok && move) this.move(1, 0); else this.drawCell();
    };
    input.addEventListener("keydown", e => {
      if (e.key === "Enter") { e.stopPropagation(); e.preventDefault(); finish(true, true); }
      else if (e.key === "Tab") { e.stopPropagation(); e.preventDefault(); finish(true, false).then(ok => {if(ok!==false)this.move(1, 0);}); }
      else if (e.key === "Escape") { e.stopPropagation(); finish(false, false); }
    });
    input.addEventListener("blur", () => setTimeout(() => finish(true, false), 250));
  }

  async commit(uid, col, v) {
    let reason = "";
    if (col === "Invoice Status" && v === "Cancelled") {
      const d = this.rows[this.idxOf(uid)];
      reason = await promptBox("Cancelled invoice", "Why is this invoice cancelled?");
      if (reason === null || !reason.trim()) { this.refresh && this.refresh(); return; }
    }
    const r = await this.onEdit(uid, col, v, reason.trim());
    if (r && r.msg && !r.ok) toast(r.msg, true);
    return r;
  }

  onCtx(e, uid, r, c) {
    e.preventDefault();
    this.cell = { r, c };
    if (!this.sel.has(uid)) { this.sel = new Set([uid]); this.anchor = r; }
    this.refreshSel();
    const items = [
      { label: "Copy cell", fn: () => this.copyCell() },
      { label: "Paste into cell", fn: () => this.pasteCell() },
    ];
    if (this.extra && this.extra.length) { items.push("-"); items.push(...this.extra); }
    ctxMenu(e.clientX, e.clientY, items);
  }

  selected() { return this.rows.filter(r => this.sel.has(r.uid)).map(r => r.uid); }
}
