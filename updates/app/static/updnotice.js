/* Update-available banner. One constant below sets how often the program checks. */
const UPDATE_CHECK_MS = 120000;   // 2 minutes for live testing. Change to 3600000 for hourly.
(function () {
  const SITE = "https://distribution-program.github.io/";
  let shown = "";
  function dismissed(v) { try { return sessionStorage.getItem("upd_later") === v; } catch (e) { return false; } }
  function remove() { const b = document.getElementById("upd-banner"); if (b) b.remove(); shown = ""; }
  function show(ver, trial) {
    if (shown === ver && document.getElementById("upd-banner")) return;
    remove(); shown = ver;
    const b = document.createElement("div"); b.id = "upd-banner";
    b.style.cssText = "position:sticky;top:0;z-index:99999;display:flex;gap:12px;align-items:center;justify-content:center;padding:9px 14px;background:#1f7a3f;color:#fff;font:600 14px Segoe UI,Arial,sans-serif;box-shadow:0 2px 6px rgba(0,0,0,.25)";
    const t = document.createElement("span"); t.textContent = T("New update") + " " + ver + " " + T("available");
    const o = document.createElement("button"); o.textContent = T("Open Update");
    o.style.cssText = "background:#fff;color:#1f7a3f;border:0;border-radius:6px;padding:5px 12px;font-weight:700;cursor:pointer";
    o.onclick = () => {
      if (trial) { window.open(SITE, "_blank"); return; }
      try { settingsModal(); } catch (e) { return; }
      setTimeout(() => { const x = [...document.querySelectorAll("button")].find(k => k.textContent.trim() === "Check for updates"); if (x) x.click(); }, 400);
    };
    const l = document.createElement("button"); l.textContent = T("Later");
    l.style.cssText = "background:transparent;color:#fff;border:1px solid #fff;border-radius:6px;padding:4px 10px;cursor:pointer";
    l.onclick = () => { try { sessionStorage.setItem("upd_later", ver); } catch (e) {} remove(); };
    b.append(t, o, l); document.body.prepend(b);
  }
  async function runningTag() {
    try { const r = await (await fetch("/api/instance")).json(); return String(r.version || "").split(" ")[0]; } catch (e) { return ""; }
  }
  async function check() {
    try {
      if (typeof S === "undefined" || !S || !S.user) return;
      let licOn = false;
      if (S.trialLimit) { try { const L = await (await fetch("/api/license/status", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" })).json(); licOn = !!(L && L.licensed && !L.readonly && !L.tampered); } catch (e) {} }
      if (S.trialLimit && !licOn) {
        const r = await (await fetch(SITE + "latest.json?t=" + Date.now(), { cache: "no-store" })).json();
        const ver = String((r && r.version) || ""), cur = await runningTag();
        if (ver && cur && ver !== cur && !dismissed(ver)) show(ver, true); else if (!ver || ver === cur) remove();
        return;
      }
      if (!S.isAdmin) return;
      const r = await api("/api/update/check", {});
      const cur = await runningTag();
      if (r && r.ok && r.available && r.version && r.version !== cur && !dismissed(r.version)) show(r.version, false);
      else if (r && r.ok && !r.available) remove();
    } catch (e) { /* offline or key problem: stay silent */ }
  }
  setTimeout(check, 8000);
  setInterval(check, UPDATE_CHECK_MS);
})();
