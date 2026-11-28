/* Settings > "Firebase and phone app" (Admi1 only; disabled in the trial). */
(function () {
  const ANDROID_LINK = "";   // private Drive link of the phone app, filled at release
  const TRIAL_TXT = "Not available in the trial";
  const H = (t, tag) => { const e = document.createElement(tag || "div"); e.innerHTML = t; return e; };
  const btn = (label, fn, cls) => { const b = el("button", "btn " + (cls || ""), label); if (fn) b.onclick = fn; return b; };
  const bar = (...bs) => { const d = el("div", "toolbar"); d.style.margin = "6px 0"; bs.forEach(b => d.appendChild(b)); return d; };
  const ok = (t) => `<div style="color:#15803d">&#10003; ${t}</div>`;
  const bad = (t) => `<div style="color:#b91c1c">&#10007; ${t}</div>`;
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const fbapi = (a, b) => api("/api/fb/" + a, b || {});
  const openUrl = (u) => window.open(u, "_blank");
  const li = (a) => a.map(x => `<li style="margin:3px 0">${x}</li>`).join("");
  const blk = (n, en, ar) => `<h3 style="margin:0 0 6px">${n}</h3><ol style="margin:0 0 6px 18px;padding:0">${li(en)}</ol><ol dir="rtl" style="margin:0 18px 6px 0;padding:6px 22px 6px 6px;background:#f8fafc;border-radius:6px;font-size:14px">${li(ar)}</ol>`;

  function wizard(title, items, pages, width) {
    const c = el("div"); let cur = 0;
    const { close } = modal(c, width || "960px");
    const draw = () => {
      c.innerHTML = ""; c.appendChild(el("h2", null, title));
      const row = el("div"); row.style.cssText = "display:flex;gap:18px";
      const side = el("div"); side.style.cssText = "width:200px;flex:none;border-right:1px solid #e2e8f0;padding-right:10px;font-size:13px";
      side.innerHTML = items.map((t, i) => `<div style="display:flex;gap:8px;align-items:center;margin:5px 0;${i == cur ? "font-weight:700;color:#0b4a82" : "color:#64748b"}"><span style="width:22px;height:22px;flex:none;border-radius:50%;background:${i < cur ? "#16a34a" : (i == cur ? "#0b4a82" : "#cbd5e1")};color:#fff;display:inline-flex;align-items:center;justify-content:center;font-size:12px">${i < cur ? "&#10003;" : i + 1}</span>${t}</div>`).join("");
      const body = el("div"); body.style.cssText = "flex:1;font-size:13px";
      row.appendChild(side); row.appendChild(body); c.appendChild(row);
      pages[cur](body);
      const nb = el("div", "toolbar"); nb.style.marginTop = "12px";
      const back = btn("Back", () => { cur--; draw(); }); back.disabled = cur == 0;
      const last = cur == items.length - 1;
      nb.appendChild(back); nb.appendChild(btn(last ? "Finish" : "Next", () => { if (last) close(); else { cur++; draw(); } }, "accent")); nb.appendChild(btn("Close", close));
      c.appendChild(nb);
    };
    draw(); return close;
  }

  function checkBox(host, lines) {
    host.innerHTML = lines.join("");
  }
  async function runStatus(host, full) {
    host.innerHTML = '<span class="hint">Checking...</span>';
    const r = await fbapi("status");
    if (!r.ok) { host.innerHTML = bad(esc(r.msg || "Failed")); return r; }
    const L = [r.key_found ? ok("Key file found") : bad("serviceAccountKey.json not found in: " + esc(r.folder))];
    if (r.key_found) {
      L.push(r.cloud ? ok("Project: " + esc(r.project) + " (connected)") : bad("Key found but the program is not connected. Restart the program once."));
      if (full) {
        L.push(r.signin === true ? ok("Email/Password sign-in is ON") : (r.signin === false ? bad("Email/Password sign-in is OFF (step 1)") : bad("Sign-in: " + esc(r.signin_error || "unknown"))));
        L.push(r.rules ? ok("Rules published " + esc(r.rules.updated || "")) : bad("Rules: " + esc(r.rules_error || "unknown")));
        L.push(r.drivers != null ? ok(r.drivers + " driver account(s)") : bad("Drivers: " + esc(r.drivers_error || "unknown")));
      } else if (r.cloud) L.push(ok("Firebase reachable (read only check, nothing changed)"));
    }
    host.innerHTML = L.join("");
    return r;
  }

  const CONSOLE = "https://console.firebase.google.com/";
  const keyStep = (en, ar, extra) => (b) => { b.innerHTML = blk(en, ["Open <b>console.firebase.google.com</b> and click your project.", "Click the <b>gear</b>, then <b>Project settings</b>, tab <b>Service accounts</b>.", "Click <b>Generate new private key</b>, then <b>Generate key</b>.", "Rename the downloaded file to <b>serviceAccountKey.json</b>. Never send it to anyone."], ["افتح <b>console.firebase.google.com</b> واضغط على مشروعك.", "اضغط <b>الترس</b> ثم <b>Project settings</b> ثم تبويب <b>Service accounts</b>.", "اضغط <b>Generate new private key</b> ثم <b>Generate key</b>.", "غير اسم الملف إلى <b>serviceAccountKey.json</b>. ماتبعتوش لحد أبدا."]); b.appendChild(bar(btn("Open Firebase console", () => openUrl(CONSOLE), "accent"))); b.appendChild(H('<p class="hint">' + extra + '</p>')); };
  const putStep = (b) => {
    b.innerHTML = blk("Put the key next to the program", ["Press <b>Open folder</b>.", "Copy <b>serviceAccountKey.json</b> into it.", "Press <b>Check</b>."], ["اضغط <b>Open folder</b>.", "انسخ <b>serviceAccountKey.json</b> جوه الفولدر.", "اضغط <b>Check</b>."]);
    const out = H(""); const path = H("", "div"); path.style.cssText = "background:#f1f5f9;padding:8px;border-radius:6px;font-family:monospace";
    fbapi("status").then(r => { path.textContent = r.folder || ""; });
    b.appendChild(path);
    b.appendChild(bar(btn("Open folder", async () => { const r = await fbapi("open_folder"); if (!r.ok) toast(r.msg || "Could not open", true); }, "accent"), btn("Check", () => runStatus(out, false))));
    b.appendChild(out);
  };
  const checkStep = (full) => (b) => {
    b.innerHTML = blk("Check the connection", ["Press <b>Check connection</b>. All lines must be green.", "Restart the program once after adding the key if it was open."], ["اضغط <b>Check connection</b>. لازم كل السطور تبقى خضرا.", "اعمل ريستارت للبرنامج مرة بعد إضافة المفتاح لو كان مفتوح."]);
    const out = H(""); out.style.lineHeight = "1.8";
    b.appendChild(bar(btn("Check connection", () => runStatus(out, full), "accent"))); b.appendChild(out);
  };

  function createWizard() {
    wizard("Connect with Firebase (new project)", ["1. Create the free project", "2. Turn on Firestore", "3. Create the key file", "4. Put the key next to the program", "5. Check connection"], [
      (b) => { b.innerHTML = blk("Step 1 of 5: create the free project", ["Open <b>console.firebase.google.com</b> and sign in with your Google account.", "Click <b>Create a project</b>.", "Type a name, for example <b>distribution-program</b>, click <b>Continue</b>.", "Turn <b>Google Analytics</b> OFF, click <b>Create project</b>, wait, click <b>Continue</b>."], ["افتح <b>console.firebase.google.com</b> وسجل بحساب جوجل.", "اضغط <b>Create a project</b>.", "اكتب اسم مثلا <b>distribution-program</b> واضغط <b>Continue</b>.", "اقفل <b>Google Analytics</b> واضغط <b>Create project</b> واستنى ثم <b>Continue</b>."]); b.appendChild(bar(btn("Open Firebase console", () => openUrl(CONSOLE), "accent"))); b.appendChild(H('<p class="hint">Free plan (Spark). No card needed.</p>')); },
      (b) => { b.innerHTML = blk("Step 2 of 5: turn on Firestore (the database)", ["In the left menu click <b>Build</b>, then <b>Firestore Database</b>.", "Click <b>Create database</b>.", "Choose the location closest to you (for example <b>europe-west</b>), click <b>Next</b>.", "Choose <b>Start in production mode</b>, click <b>Create</b>."], ["من القائمة الشمال اضغط <b>Build</b> ثم <b>Firestore Database</b>.", "اضغط <b>Create database</b>.", "اختار أقرب مكان (مثلا <b>europe-west</b>) واضغط <b>Next</b>.", "اختار <b>Start in production mode</b> واضغط <b>Create</b>."]); b.appendChild(bar(btn("Open Firebase console", () => openUrl(CONSOLE), "accent"))); b.appendChild(H('<p class="hint">The location cannot be changed later.</p>')); },
      keyStep("Step 3 of 5: create the key file", "", '<span style="color:#b91c1c">This file is the key to your data: keep it private.</span>'),
      putStep, checkStep(false)]);
  }
  function connectWizard() {
    wizard("Connect with Firebase (existing project)", ["1. Get the key file", "2. Put the key next to the program", "3. Check connection"], [
      keyStep("Step 1 of 3: get the key file of your project", "", "No project, account or database is created. Existing data is not touched."), putStep, checkStep(false)]);
  }
  function connectChoice() { /* kept for a later release (Connect-only path) */
    const c = el("div"); c.appendChild(el("h2", null, "Connect with Firebase"));
    c.appendChild(el("p", null, "What do you want to do? / عايز تعمل إيه؟"));
    const row = el("div"); row.style.cssText = "display:flex;gap:12px";
    const card = (t, en, ar, b, color) => { const d = el("div"); d.style.cssText = `flex:1;border:2px solid ${color};border-radius:10px;padding:12px;font-size:13px`; d.innerHTML = `<h3 style="margin:0 0 6px">${t}</h3>${en}<span dir="rtl" style="display:block;margin-top:4px">${ar}</span>`; d.appendChild(bar(b)); return d; };
    const { close } = modal(c, "760px");
    row.appendChild(card("Create", "I do not have a Firebase project yet.", "معنديش مشروع Firebase لسه. أعمل واحد جديد مجاني.", btn("Create a new project (5 steps)", () => { close(); createWizard(); }), "#cbd5e1"));
    row.appendChild(card("Connect", "I already have a Firebase project. Only connect this program to it. No account or project is created.", "عندي مشروع Firebase. بس أوصل البرنامج بيه. مفيش حاجة بتتعمل جديدة.", btn("Connect to my project (3 steps)", () => { close(); connectWizard(); }, "accent"), "#0b4a82"));
    c.appendChild(row); c.appendChild(bar(btn("Close", close)));
  }

  /* ---- drivers ---- */
  function driverForm(d, done) {
    const edit = !!d; d = d || {};
    const c = el("div"); c.appendChild(el("h2", null, edit ? "Edit user" : "Add user"));
    const f = {};
    const field = (k, label, val, type, ro) => { const l = el("label", null, label); l.style.cssText = "display:block;margin:8px 0 2px;font-weight:600"; const i = el("input"); i.type = type || "text"; i.value = val || ""; i.style.cssText = "width:100%;padding:7px;border:1px solid #9aa7b8;border-radius:6px"; if (ro) i.disabled = true; f[k] = i; c.appendChild(l); c.appendChild(i); };
    field("username", "Username (no spaces, this is what the user types)", d.username, "text", edit);
    field("name", "Name (driver: printed on invoices, must match exactly)", d.name);
    let role = d.role === "manager" ? "manager" : "driver";
    const rl = el("label", null, "Role"); rl.style.cssText = "display:block;margin:8px 0 2px;font-weight:600;color:#0f766e"; c.appendChild(rl);
    const rw = el("div"); rw.style.cssText = "display:flex;gap:10px;margin:2px 0 4px"; c.appendChild(rw);
    const opt = (v, t1, t2) => { const l = el("label"); l.style.cssText = "flex:1;border-radius:8px;padding:8px;cursor:pointer"; const r = el("input"); r.type = "radio"; r.name = "role_" + Date.now(); r.checked = role === v; r.onchange = () => { role = v; paint(); }; l.appendChild(r); l.appendChild(H(" <b>" + t1 + "</b><div style='font-size:12px;font-weight:400'>" + t2 + "</div>")); rw.appendChild(l); return l; };
    const oD = opt("driver", "Driver", "Phone opens on In Process only. Sees only his own In Process invoices."), oM = opt("manager", "Distribution manager (مسؤول توزيع)", "Sees Undelivered and In Process, for all drivers.");
    const paint = () => { [[oD, "driver"], [oM, "manager"]].forEach(([l, v]) => { l.style.border = role === v ? "3px solid #0f766e" : "1px solid #9aa7b8"; l.style.background = role === v ? "#ecfdf5" : ""; }); [f.car, f.line].forEach(i => { if (i) { i.style.display = role === "driver" ? "" : "none"; if (i.previousSibling) i.previousSibling.style.display = role === "driver" ? "" : "none"; } }); };
    if (!edit) field("password", "Password (min 6 characters, you type it, not shown again)", "", "password");
    field("car", "Car No (driver only)", d.car); field("line", "Line (driver only)", d.line); field("phone", "Phone (optional)", d.phone); paint();
    const msg = el("div"); msg.style.cssText = "color:#b91c1c;margin:6px 0"; c.appendChild(msg);
    const { close } = modal(c, "520px");
    const save = btn("Save", async () => {
      save.disabled = true; msg.textContent = "";
      const b = { uid: d.uid, role }; Object.keys(f).forEach(k => b[k] = f[k].value);
      const r = await fbapi(edit ? "driver_edit" : "driver_add", b);
      if (r.ok) { toast(r.msg); close(); done(); } else { msg.textContent = r.msg || "Failed"; save.disabled = false; }
    }, "accent");
    c.appendChild(bar(save, btn("Cancel", close)));
  }
  function resetForm(d, done) {
    const c = el("div"); c.appendChild(el("h2", null, "Reset password: " + d.username));
    const mk = (l) => { const lb = el("label", null, l); lb.style.cssText = "display:block;margin:8px 0 2px;font-weight:600"; const i = el("input"); i.type = "password"; i.style.cssText = "width:100%;padding:7px;border:1px solid #9aa7b8;border-radius:6px"; c.appendChild(lb); c.appendChild(i); return i; };
    const a = mk("New password (min 6 characters)"), b2 = mk("Type it again");
    const msg = el("div"); msg.style.cssText = "color:#b91c1c;margin:6px 0"; c.appendChild(msg);
    c.appendChild(el("p", "hint", "The driver is signed out on the phone and must use the new password."));
    const { close } = modal(c, "480px");
    c.appendChild(bar(btn("Save new password", async () => { const r = await fbapi("driver_reset", { uid: d.uid, pw1: a.value, pw2: b2.value }); if (r.ok) { toast(r.msg); close(); done(); } else msg.textContent = r.msg; }, "accent"), btn("Cancel", close)));
  }
  function driversModal() {
    const c = el("div"); c.appendChild(el("h2", null, "Drivers"));
    c.appendChild(el("p", "hint", "Each driver logs in on the phone app with a username and sees only his own In Process invoices. Passwords are never shown again after saving."));
    const { close } = modal(c, "900px");
    let rows = [], sel = null;
    const tb = el("div", "toolbar"); tb.style.margin = "6px 0"; c.appendChild(tb);
    const holder = el("div"); c.appendChild(holder);
    const msg = el("div", "hint"); c.appendChild(msg);
    c.appendChild(bar(btn("Close", close)));
    const cur = () => rows.find(r => r.uid === sel);
    const need = (fn) => () => { const d = cur(); if (!d) { toast("Select a driver first", true); return; } fn(d); };
    const bAdd = btn("Add user", () => driverForm(null, load), "accent");
    const bEdit = btn("Edit", need(d => driverForm(d, load)));
    const bDis = btn("Disable", need(async d => { const r = await fbapi("driver_disable", { uid: d.uid, disabled: !d.disabled }); toast(r.msg, !r.ok); load(); }));
    const bRes = btn("Reset password", need(d => resetForm(d, load)));
    const bDel = btn("Delete", need(async d => { if (!(await askBox("Delete driver", "Delete the login of " + d.username + " (" + d.name + ")? The driver can no longer sign in. Invoices are NOT deleted."))) return; const r = await fbapi("driver_delete", { uid: d.uid }); toast(r.msg, !r.ok); sel = null; load(); }));
    [bAdd, bEdit, bDis, bRes, bDel].forEach(b => tb.appendChild(b));
    function draw() {
      const d = cur(); bDis.textContent = d && d.disabled ? "Enable" : "Disable";
      holder.innerHTML = `<table class="tbl" style="width:100%;border-collapse:collapse;font-size:13px"><tr style="background:#e8eef6;text-align:left"><th style="padding:6px"></th><th>Username</th><th>Name</th><th>Role</th><th>Car No</th><th>Line</th><th>Phone</th><th>Status</th><th>Created</th></tr>` +
        rows.map(r => `<tr data-u="${esc(r.uid)}" style="cursor:pointer;${r.uid === sel ? "background:#dbeafe" : ""}"><td style="padding:6px">${r.uid === sel ? "&#9745;" : "&#9744;"}</td><td>${esc(r.username)}</td><td>${esc(r.name)}</td><td>${r.role === "manager" ? "Distribution manager" : "Driver"}</td><td>${esc(r.car)}</td><td>${esc(r.line)}</td><td>${esc(r.phone)}</td><td style="font-weight:700;color:${r.disabled ? "#b91c1c" : "#15803d"}">${r.disabled ? "Disabled" : "Active"}</td><td>${esc(r.created)}</td></tr>`).join("") + "</table>";
      holder.querySelectorAll("tr[data-u]").forEach(t => t.onclick = () => { sel = t.dataset.u; draw(); });
    }
    async function load() { const r = await fbapi("drivers"); if (!r.ok) { msg.textContent = r.msg; msg.style.color = "#b91c1c"; return; } rows = r.drivers; msg.textContent = rows.length + " driver(s)"; draw(); }
    load();
  }

  function androidWizard() {
    wizard("Add Android application", ["1. Turn on sign-in", "2. Publish the rules", "3. Add users", "4. Install the phone app", "5. Check"], [
      (b) => { b.innerHTML = blk("Step 1 of 5: turn on sign-in", ["Press <b>Turn on sign-in</b>. The program turns on Email/Password sign-in in your Firebase by itself.", "Nothing to do in the console."], ["اضغط <b>Turn on sign-in</b>. البرنامج بيفتح تسجيل الدخول بالإيميل والباسورد في Firebase لوحده.", "مفيش حاجة تعملها في الكونسول."]); const out = H(""); b.appendChild(bar(btn("Turn on sign-in", async () => { out.innerHTML = '<span class="hint">Working...</span>'; const r = await fbapi("signin"); out.innerHTML = r.ok ? ok(esc(r.msg)) : bad(esc(r.msg)); }, "accent"))); b.appendChild(out); b.appendChild(H('<p class="hint">If the key is not allowed, the program shows the exact error and the one console click to fix it.</p>')); },
      (b) => {
        b.innerHTML = blk("Step 2 of 5: publish the rules", ["Press <b>Publish rules</b>, then <b>Yes, publish</b>.", "The old rules are saved on this PC first."], ["اضغط <b>Publish rules</b> ثم <b>Yes, publish</b>.", "القواعد القديمة بتتحفظ على الجهاز الأول."]);
        const pre = el("pre"); pre.style.cssText = "background:#0f172a;color:#e2e8f0;padding:8px;border-radius:6px;font-size:11px;max-height:130px;overflow:auto;margin:0"; b.appendChild(pre);
        fbapi("rules_text").then(r => { pre.textContent = r.text || r.msg || ""; });
        const out = H(""); const conf = H(""); conf.style.cssText = "display:none;background:#fef9c3;border:1px solid #eab308;padding:6px;border-radius:6px;margin-top:6px";
        conf.innerHTML = "<b>Publish to your Firebase?</b> This replaces the current rules. The old rules are saved on this PC first.";
        conf.appendChild(bar(btn("Yes, publish", async () => { conf.style.display = "none"; out.innerHTML = '<span class="hint">Publishing...</span>'; const r = await fbapi("rules_publish"); out.innerHTML = r.ok ? ok(esc(r.msg) + (r.backup ? "<br>Old rules saved: " + esc(r.backup.split(/[\\/]/).pop()) : "")) : bad(esc(r.msg)); }, "accent"), btn("Cancel", () => conf.style.display = "none")));
        b.appendChild(bar(btn("Publish rules", () => conf.style.display = "block", "accent"), btn("Restore previous rules", async () => { if (!(await askBox("Restore", "Put back the rules saved before the last publish?"))) return; const r = await fbapi("rules_restore"); out.innerHTML = r.ok ? ok(esc(r.msg)) : bad(esc(r.msg)); })));
        b.appendChild(conf); b.appendChild(out);
      },
      (b) => { b.innerHTML = blk("Step 3 of 5: add users", ["Press <b>Add user</b>. Type username, name, choose the role (Driver or Distribution manager), password, car, line.", "Press <b>Save</b>. Repeat for each driver."], ["اضغط <b>Add user</b>. اكتب اليوزر والاسم واختار الدور (سواق أو مسؤول توزيع) والباسورد والعربية والخط.", "اضغط <b>Save</b>. كرر لكل سواق."]); b.appendChild(bar(btn("Add user", () => driverForm(null, () => { }), "accent"), btn("Open Drivers list", driversModal))); },
      (b) => { b.innerHTML = blk("Step 4 of 5: install the phone app", ["Press <b>Copy app link</b> and send it to the phone (your own Drive link).", "On the phone open it, download, tap the file, allow install if asked.", "Open the app and sign in with the username and password."], ["اضغط <b>Copy app link</b> وابعته للموبايل (لينك الدرايف بتاعك).", "على الموبايل افتحه ونزل وافتح الملف واسمح بالتثبيت لو سأل.", "افتح التطبيق وسجل دخول باليوزر والباسورد."]); const i = el("input"); i.placeholder = "App link"; i.value = localStorage.getItem("dp_android_link") || ANDROID_LINK; i.style.cssText = "width:100%;padding:7px;border:1px solid #9aa7b8;border-radius:6px;margin:6px 0"; b.appendChild(i); b.appendChild(bar(btn("Copy app link", async () => { localStorage.setItem("dp_android_link", i.value); try { await navigator.clipboard.writeText(i.value); toast("Link copied"); } catch (e) { i.select(); toast("Press Ctrl+C to copy", true); } }, "accent"))); b.appendChild(H('<p class="hint">The link is private to your Google account. No keys are inside the app.</p>')); },
      checkStep(true)], "960px");
  }

  function plansModal() {
    const usd = 54.91, e = (x) => (x * usd).toLocaleString("en", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    const c = el("div");
    c.innerHTML = `<h2>About Firebase plans</h2>
<p class="hint" style="margin:0 0 6px">Prices checked 27/11/2026. USD to EGP: 54.91 (Central Bank of Egypt selling rate, 26/11/2026). Visible only to Admi1.</p>
<div style="display:flex;gap:10px">
<div style="flex:1;border:2px solid #16a34a;border-radius:10px;padding:10px;font-size:13px"><h3 style="margin:0 0 4px;color:#15803d">Spark (free) - recommended</h3><b>EGP 0 per month</b>, no card needed.<br>Daily free limits: 50,000 reads, 20,000 writes, 20,000 deletes, 1 GiB stored, 10 GiB data out per month.<br><b style="color:#15803d">About 2,300 to 4,000 invoices per day</b> (3 to 2 PCs, see below).<br>When a daily limit is reached, the cloud pauses until the next day. Local work continues.</div>
<div style="flex:1;border:2px solid #64748b;border-radius:10px;padding:10px;font-size:13px"><h3 style="margin:0 0 4px">Blaze (pay as you go)</h3>Needs a payment card. The Spark free amounts are still free, you pay only above them:<br>Reads: EGP ${e(0.03)} per 100,000<br>Writes: EGP ${e(0.09)} per 100,000<br>Deletes: EGP ${e(0.01)} per 100,000<br>Stored data: about EGP ${e(0.15)} per GiB per month<br><b>No daily limit.</b> Example at 5,000 invoices/day: about EGP 27 per month.</div></div>
<h3 style="margin:10px 0 4px;font-size:13px">How many invoices per day (free plan)</h3>
<table style="width:100%;border-collapse:collapse;font-size:12.5px"><tr style="background:#e8eef6;text-align:left"><th style="padding:5px">PCs using the program</th><th>Invoices stored</th><th>Reads per invoice</th><th>Invoices per day (Spark)</th><th>Limit reached first</th></tr>
<tr><td style="padding:5px">2</td><td>5,000</td><td>10</td><td><b>4,000</b></td><td>writes</td></tr>
<tr style="background:#f8fafc"><td style="padding:5px">3</td><td>5,000</td><td>15</td><td><b>2,300</b></td><td>reads</td></tr>
<tr><td style="padding:5px">3</td><td>15,000</td><td>15</td><td><b>0 (startup reads alone use the day)</b></td><td>reads</td></tr></table>
<p class="hint" style="margin:6px 0">Estimates, not promises. Assumptions: one invoice = about 5 saved changes, each change is 1 write and 1 read, and every other PC reads it once. Each PC reads all stored invoices once when it starts. Phone app reads are not counted. Prices may differ slightly by region.</p>`;
    const { close } = modal(c, "980px");
    c.appendChild(bar(btn("Open Firebase pricing page", () => openUrl("https://firebase.google.com/pricing")), btn("Close", close)));
  }


  function customerKeyDialog() {
    const c = el("div"); c.appendChild(el("h2", null, "Upload your Firebase key file"));
    c.appendChild(el("p", "hint", "Firebase console > Project settings > Service accounts > Generate new private key. Choose the downloaded .json file here. The file stays on this PC."));
    const inp = el("input"); inp.type = "file"; inp.accept = ".json,application/json"; c.appendChild(inp);
    const out = el("div"); out.style.margin = "10px 0"; c.appendChild(out);
    const { close } = modal(c, "560px");
    const go = btn("Save key file", async () => {
      if (!inp.files.length) { out.innerHTML = bad("Choose the .json file first."); return; }
      const text = await inp.files[0].text(); const r = await api("/api/customer/key", { text });
      if (!r.ok) { out.innerHTML = bad(esc(r.msg)); return; }
      out.innerHTML = ok(esc(r.msg)); rs.style.display = "";
    }, "accent");
    const rs = btn("Restart now", async () => { await api("/api/customer/restart", {}); out.innerHTML = ok("Restarting... the program reopens by itself."); }, "accent"); rs.style.display = "none";
    c.appendChild(bar(go, rs, btn("Close", close)));
  }
  function customerPhoneDialog() {
    const c = el("div"); c.appendChild(el("h2", null, "Phone app company code"));
    c.appendChild(el("p", "hint", "Firebase console > Project settings > General > Web API key (starts with AIza). Then scan the QR with the phone app's company setup screen, or copy the code and paste it there."));
    const k = el("input", "in"); k.placeholder = "Web API key (AIza...)"; const n = el("input", "in"); n.placeholder = "Company name"; n.style.marginTop = "6px";
    const ta = el("textarea", "in"); ta.readOnly = true; ta.style.cssText = "flex:1;height:190px"; const out = el("div");
    const qr = el("div"); qr.style.cssText = "text-align:center;display:none"; const qbox = el("div"); qbox.style.cssText = "background:#fff;padding:6px;border-radius:8px;border:1px solid #cbd5e1;width:190px;height:190px"; qr.append(qbox, el("div", "hint", "Scan with the phone app"));
    const row = el("div"); row.style.cssText = "display:flex;gap:16px;margin-top:10px;align-items:flex-start"; row.append(ta, qr);
    const drawQr = (t) => { qbox.innerHTML = ""; qr.style.display = "none"; if (!t || !window.qrcode) return; try { const q = window.qrcode(0, "M"); q.addData(t); q.make(); qbox.innerHTML = q.createSvgTag({ cellSize: 4, margin: 2, scalable: true }); const sv = qbox.querySelector("svg"); if (sv) { sv.style.width = "100%"; sv.style.height = "100%"; } qr.style.display = ""; } catch (e) { qr.style.display = "none"; } };
    c.append(k, n, row, out);
    const { close } = modal(c, "620px");
    const mk = btn("Make code", async () => { const r = await api("/api/customer/phonecode", { apiKey: k.value, company: n.value }); if (!r.ok) { out.innerHTML = bad(esc(r.msg)); ta.value = ""; drawQr(""); return; } ta.value = r.code; drawQr(r.code); out.innerHTML = ok("Project " + esc(r.project)); }, "accent");
    api("/api/customer/phonecode", { load: true }).then(r => { if (r && r.ok && r.saved) { k.value = r.apiKey; n.value = r.company; ta.value = r.code; drawQr(r.code); out.innerHTML = ok("Saved code for project " + esc(r.project)); } }).catch(() => { });
    const cp = btn("Copy", async () => { if (!ta.value) return; try { await navigator.clipboard.writeText(ta.value); } catch (e) { ta.select(); document.execCommand("copy"); } out.innerHTML = ok("Copied"); });
    c.appendChild(bar(mk, cp, btn("Close", close)));
  }

  window.fbToolsSection = function (c, sec) {
    if (!(S.fbTools || S.trialLimit)) return;
    const dis = !!S.trialLimit && !window.__licFull;
    const g = (label, fn, cls) => [label, dis ? () => toast(TRIAL_TXT, true) : fn, cls];
    sec("Firebase and phone app", [g("0. Upload Firebase key file", customerKeyDialog, "accent"), g("1. Connect with Firebase", createWizard, "accent"), g("2. Add Android application", androidWizard), g("3. Add user", () => driverForm(null, () => { })), g("Drivers...", driversModal), g("Phone app company code", customerPhoneDialog), g("About Firebase plans", plansModal)]);
    if (dis) { const gs = c.lastChild.querySelectorAll("button"); gs.forEach(b => { b.disabled = true; b.title = TRIAL_TXT; b.textContent += " (" + TRIAL_TXT + ")"; }); }
  };
})();
