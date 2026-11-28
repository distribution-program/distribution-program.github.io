/* License (public trial only): banner with what is left, "Enter license" box, trial-finished box. */
(function () {
  let L = null, boxOpen = false, shownFinished = false;
  const E = (t, c, s) => { const e = document.createElement(t); if (c) e.className = c; if (s) e.style.cssText = s; return e; };
  const BTN = "padding:6px 14px;border-radius:6px;border:1px solid #94a3b8;background:#fff;cursor:pointer;font-weight:600";
  function bar() {
    { const b0 = document.getElementById("lic-bar"); if (b0) b0.remove(); return; }  // the license status lives in Settings only
    let b = document.getElementById("lic-bar");
    if (!L || !L.trial || !(typeof S !== "undefined" && S && S.user)) { if (b) b.remove(); return; }
    if (!b) { b = E("div"); b.id = "lic-bar"; const lb = document.querySelector(".live-bars"); lb.parentNode.insertBefore(b, lb); }
    let en, ar, col;
    if (L.licensed) { en = "Licensed to " + L.name + (L.expiry ? ", valid until " + L.expiry : ", no expiry") + (L.edition === "full" ? " (Full)" : " (Trial limit lifted)"); ar = "مرخص لـ " + L.name + (L.expiry ? " حتى " + L.expiry : " بدون انتهاء"); col = "background:#dcfce7;border-bottom:2px solid #16a34a;color:#14532d"; }
    else if (L.readonly) { en = L.lic_state === "expired" ? "License expired: read and print only" : L.lic_state === "clock" ? "PC date was moved back: read and print only" : "Trial finished: 50 operations used (view and search only)"; ar = L.lic_state === "expired" ? "انتهى الترخيص: قراءة وطباعة فقط" : "انتهت النسخة التجريبية: استخدمت 50 عملية (عرض وبحث بس)"; col = "background:#fee2e2;border-bottom:2px solid #dc2626;color:#7f1d1d"; }
    else { en = "Trial: " + L.left + " of " + L.limit + " operations left"; ar = "النسخة التجريبية: باقي " + L.left + " من " + L.limit + " عملية"; col = "background:#fef3c7;border-bottom:2px solid #f59e0b;color:#78350f"; }
    b.style.cssText = col + ";padding:6px 14px;font:600 14px Segoe UI,Arial;display:flex;gap:14px;align-items:center;flex-wrap:wrap";
    b.innerHTML = "";
    const a = E("span"); a.textContent = en; const c = E("span"); c.setAttribute("dir", "rtl"); c.textContent = ar;
    const k = E("button", null, "margin-left:auto;background:#1e3a8a;color:#fff;border:0;border-radius:6px;padding:6px 14px;font-weight:700;cursor:pointer"); k.textContent = L.licensed ? "License" : "Enter license"; k.onclick = () => openBox();
    b.append(a, c, k);
  }
  async function refresh() {
    try { if (typeof S === "undefined" || !S || !S.user) return; L = await (await fetch("/api/license/status", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" })).json(); }
    catch (e) { return; }
    const f = !!(L && L.full);
    if (f !== !!window.__licFull) { window.__licFull = f; if (typeof boot === "function") { try { boot(); } catch (e) {} } }
    bar();
    if (L && L.trial && L.readonly && !shownFinished) { shownFinished = true; openBox(); }
  }
  function openBox() {
    if (boxOpen || !L || !L.trial) return; boxOpen = true;
    const o = E("div", "overlay"); o.style.zIndex = 400;
    const m = E("div", "modal", "width:560px;max-width:94vw"); o.appendChild(m);
    const done = () => { boxOpen = false; o.remove(); };
    const h = E("h2", null, "margin:0 0 6px"); m.appendChild(h);
    if (L.licensed) { h.textContent = "License"; h.style.color = "#14532d"; }
    else if (L.readonly) { h.textContent = L.lic_state === "expired" ? "License expired" : "Trial finished"; h.style.color = "#b91c1c"; }
    else { h.textContent = "Enter license"; }
    const ar = E("div", null, "margin-bottom:10px;color:#475569"); ar.setAttribute("dir", "rtl");
    ar.textContent = L.licensed ? "الترخيص شغال على الجهاز ده." : L.readonly ? "انتهت النسخة التجريبية. بياناتك موجودة وتقدر تعرض وتدوّر بس." : "اكتب مفتاح الترخيص اللي وصلك."; m.appendChild(ar);
    const p = E("p", null, "margin:6px 0");
    p.innerHTML = L.licensed ? "Licensed to <b></b>.<br>Valid until: <b></b>.<br>Edition: <b></b>." : "To continue, send this <b>device code</b> to the developer and paste the license key you receive. The key works on this PC only.";
    if (L.licensed) { const bs = p.querySelectorAll("b"); bs[0].textContent = L.name; bs[1].textContent = L.expiry || "No expiry"; bs[2].textContent = L.edition === "full" ? "Full (Firebase and phone included)" : "Trial limit lifted"; }
    m.appendChild(p);
    const code = E("div", null, "background:#f1f5f9;border:1px solid #cbd5e1;border-radius:8px;padding:10px;font:700 20px Consolas,monospace;letter-spacing:2px;text-align:center"); code.textContent = L.device || "(device code not available)"; m.appendChild(code);
    const cp = E("button", null, BTN + ";margin:6px 0 10px"); cp.textContent = "Copy device code"; cp.onclick = async () => { try { await navigator.clipboard.writeText(L.device); toast("Device code copied"); } catch (e) { const r = document.createRange(); r.selectNodeContents(code); const s = getSelection(); s.removeAllRanges(); s.addRange(r); toast("Selected. Press Ctrl+C."); } }; m.appendChild(cp);
    const lab = E("label", null, "display:block;font-weight:600"); lab.textContent = L.licensed ? "Change license key" : "License key"; m.appendChild(lab);
    const ta = E("textarea", null, "width:100%;height:70px;margin-top:4px;border:1px solid #94a3b8;border-radius:6px;padding:7px;font:13px Consolas,monospace;box-sizing:border-box"); ta.placeholder = "Paste your license key here"; m.appendChild(ta);
    const msg = E("div", null, "color:#b91c1c;margin:6px 0;min-height:18px;font-weight:600"); m.appendChild(msg);
    if (!L.licensed && L.lic_state !== "none" && L.lic_msg) msg.textContent = L.lic_msg;
    const row = E("div", null, "display:flex;gap:10px;justify-content:flex-end");
    const cl = E("button", null, BTN); cl.textContent = L.readonly ? "Close (read only)" : "Close"; cl.onclick = done;
    const ac = E("button", null, "padding:8px 18px;border-radius:6px;border:0;background:#0f766e;color:#fff;font-weight:700;cursor:pointer"); ac.textContent = "Activate";
    ac.onclick = async () => {
      msg.style.color = "#b91c1c"; msg.textContent = "";
      if (!ta.value.trim()) { msg.textContent = "Paste the license key first."; return; }
      ac.disabled = true;
      try {
        const r = await (await fetch("/api/license/activate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ key: ta.value }) })).json();
        if (r.ok) { msg.style.color = "#166534"; msg.textContent = r.msg; toast(r.msg); L = r.status; window.__licFull = !!(r.status && r.status.full); shownFinished = false; bar(); setTimeout(() => { done(); if (typeof boot === "function") { try { boot(); } catch (e) {} } }, 1200); }
        else msg.textContent = r.msg || "This key was not accepted.";
      } catch (e) { msg.textContent = "Could not check the key."; }
      ac.disabled = false;
    };
    row.append(cl, ac); m.appendChild(row);
    document.getElementById("modal-root").appendChild(o);
  }
  // when the program refuses work because the trial ended, show the box
  const _fetch = window.fetch;
  window.fetch = async function () {
    const r = await _fetch.apply(this, arguments);
    try {
      const u = String(arguments[0] && arguments[0].url || arguments[0] || "");
      if (u.indexOf("/api/") === 0 && u.indexOf("/api/license") !== 0 && r.headers.get("content-type") && r.headers.get("content-type").indexOf("json") >= 0) {
        r.clone().json().then(j => { if (j && typeof j.msg === "string" && /Enter license/.test(j.msg)) { refresh().then(() => { shownFinished = true; openBox(); }); } }).catch(() => {});
      }
    } catch (e) {}
    return r;
  };
  window.openLicenseBox = () => refresh().then(openBox);
  setTimeout(refresh, 1500); setInterval(refresh, 20000);

  // License section inside Settings: status, expiry date, days left, Renew / Enter license
  new MutationObserver(() => {
    const root = document.getElementById("modal-root"); if (!root || !L || !L.trial) return;
    const h = [...root.querySelectorAll("h2")].find(x => x.textContent === "Settings"); if (!h || h.parentNode.querySelector(".lic-sec")) return;
    const sec = E("div", "lic-sec", "margin:10px 0;padding:10px 14px;border-radius:8px;border:1px solid #cbd5e1;background:#f8fafc");
    const t = E("div", null, "font-weight:700;color:var(--accent);margin-bottom:6px"); t.textContent = "License"; sec.appendChild(t);
    let days = null; if (L.expiry) { days = Math.ceil((new Date(L.expiry + "T23:59:59") - new Date()) / 86400000); }
    const row = (a, b, c) => { const r = E("div", null, "margin:3px 0"); r.textContent = a + ": "; const v = E("b"); v.textContent = b; if (c) v.style.color = c; r.appendChild(v); sec.appendChild(r); };
    const exp = L.lic_state === "expired";
    if (L.licensed) { row("Status", "Active", "#166534"); row("Licensed to", L.name); row("Expiry date", L.expiry || "No expiry"); row("Days left", L.expiry ? days + " days" : "Unlimited", days != null && days <= 7 ? "#b45309" : "#166534"); }
    else if (exp) { row("Status", "Expired: read and print only", "#b91c1c"); row("Expiry date", L.expiry || "-", "#b91c1c"); row("Days left", "0 (expired)", "#b91c1c"); }
    else { row("Status", "Trial", "#b45309"); row("Operations left", L.left + " of " + L.limit); row("Expiry date", "-"); row("Days left", "-"); }
    const bt = E("div", null, "margin-top:8px;display:flex;gap:8px");
    const k = E("button", "btn accent"); k.textContent = (L.licensed || exp) ? "Renew" : "Enter license"; k.onclick = () => openBox(); bt.appendChild(k);
    sec.appendChild(bt); h.after(sec);
  }).observe(document.body, { childList: true, subtree: true });
})();
