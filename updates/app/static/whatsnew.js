/* "What's New" box: shown once per version after login. To add a release, add one entry below (newest version only needs to exist). */
(function () {
  const NEWS = {
    "v8.153.35": {
      en: ["Driver Deliveries now updates by itself while it is open. When a driver marks an invoice delivered on the phone, the numbers and the driver's list change within a few seconds. You no longer need to leave and re-enter. It reads only this PC's own data, so it adds no Firebase reads."],
      ar: ["شاشة Driver Deliveries بقت بتتحدث لوحدها وهي مفتوحة. لما السواق يعلّم فاتورة تم تسليمها من الموبايل، الأرقام وقايمة السواق بتتغير في ثواني. مش لازم تخرج وتدخل. بتقرا داتا الجهاز نفسه بس، فمفيش قراءات Firebase زيادة."]
    },
    "v8.073.27": {
      en: ["Fixed: the second start of the program (from the icon, after closing it) could show a black window that closed at once. The second start now keeps its window open. The program also writes launcher.log in its data folder so any start problem can be traced."],
      ar: ["تم الإصلاح: التشغيل التاني للبرنامج (من الأيقونة بعد ما تقفله) كان ممكن يطلع شاشة سودا وتقفل على طول. دلوقتي التشغيل التاني بيسيب النافذة مفتوحة. وكمان البرنامج بيكتب ملف launcher.log في فولدر بياناته علشان أي مشكلة في التشغيل تتتبع."]
    },
    "v8.063.26": {
      en: ["Safety: the public program now always uses its own separate data folder, even if it is started without its launcher. Fixed: starting the program again after it was closed or stopped could show a black window that closes at once. Leftover window processes are now cleaned up and, if the native window still fails, the program opens in an Edge or Chrome app window instead."],
      ar: ["أمان: البرنامج العام بقى دايما بيستخدم فولدر بيانات منفصل بتاعه، حتى لو اتشغل من غير الـ launcher. تم الإصلاح: تشغيل البرنامج تاني بعد ما اتقفل أو اتوقف كان ممكن يطلع شاشة سودا وتقفل على طول. دلوقتي بيتم تنضيف عمليات النافذة المتبقية، ولو النافذة الأصلية فشلت البرنامج بيفتح في نافذة Edge أو Chrome."]
    },
    "v8.053.25": {
      en: ["Fixed: Restart now (after uploading the Firebase key file or an update) could close the program on Windows without opening it again. The program now reopens reliably and writes restart.log if anything goes wrong."],
      ar: ["تم الإصلاح: زر Restart now (بعد رفع ملف مفتاح Firebase أو بعد تحديث) كان ممكن يقفل البرنامج على ويندوز ومايفتحش تاني. دلوقتي بيفتح من جديد بشكل ثابت وبيكتب ملف restart.log لو حصل أي مشكلة."]
    },
    "v8.043.24": {
      en: ["Phone app company code now shows a QR code next to the code. In the phone app press Scan QR code and point the camera at it. Copy and paste still work."],
      ar: ["كود الشركة للتطبيق دلوقتي بيظهر كـ QR جنب الكود. في تطبيق الموبايل دوس Scan QR code ووجّه الكاميرا عليه. النسخ واللصق لسه شغالين."]
    },
    "v8.033.23": {
      en: ["The program now opens as Guest with limited rights, no password. Use \"Switch user\" and sign in as Admi1 (password D123456789D) to set the program up.", "Customer setup, all inside Settings: add your own administrator, upload your Firebase key file, get the phone app company code. With a Full license and your Firebase project, invoices and users sync to your own cloud between your PCs. Delete Admi1 once your own admin works."],
      ar: ["البرنامج دلوقتي بيفتح كـ Guest بصلاحيات محدودة وبدون كلمة سر. اضغط \"تبديل المستخدم\" وادخل بـ Admi1 (كلمة السر D123456789D) علشان تجهز البرنامج.", "تجهيز العميل كله من الإعدادات: ضيف الأدمن بتاعك، ارفع ملف مفتاح Firebase، واطلع كود الشركة لتطبيق الموبايل. مع ترخيص Full ومشروع Firebase بتاعك، الفواتير والمستخدمين بيتزامنوا على السحابة بتاعتك بين أجهزتك. امسح Admi1 لما الأدمن بتاعك يشتغل."]
    },
    "v8.023.22": {
      en: ["Distribution Program (public edition) with a Full license: connect your OWN Firebase project with the Firebase buttons and wizard. Put your key file next to the program, enter the license and restart once. Your invoices stay on this PC for now."],
      ar: ["نسخة Distribution Program العامة مع ترخيص Full: تقدر توصّل مشروع Firebase بتاعك إنت بأزرار Firebase والمعالج. حط ملف المفتاح جنب البرنامج، دخّل الترخيص، وأعد التشغيل مرة. فواتيرك لسه بتفضل على الجهاز ده."]
    },
    "v8.013.21": {
      en: ["Licenses made by the Distribution License phone app are now accepted too, next to the ones made on the PC. Any old key keeps working."],
      ar: ["المفاتيح اللي بتتعمل من تطبيق Distribution License على الموبايل بقت بتشتغل كمان، جنب اللي بتتعمل من الكمبيوتر. وأي مفتاح قديم لسه شغال."]
    },
    "v8.003.20": {
      en: ["New \"Enter license\" button in the trial edition. Send the device code shown in the box to the developer and paste the license key you get. A key works only on that PC.", "A banner shows how many of the 50 trial operations are left. After the trial ends the program is read and print only, nothing is lost.", "Security: the program now answers only requests from this PC itself, and the login cookie is hidden from page scripts."],
      ar: ["زرار جديد Enter license في النسخة التجريبية. ابعت كود الجهاز اللي بيظهر في الشاشة للمطور وحط مفتاح الترخيص اللي هيوصلك. المفتاح بيشتغل على الجهاز ده بس.", "شريط فوق بيوريك فاضل كام عملية من الـ 50 في التجربة. بعد ما التجربة تخلص البرنامج بيبقى قراءة وطباعة بس ومفيش حاجة بتضيع.", "أمان: البرنامج بقى بيرد على الطلبات اللي جاية من الجهاز نفسه بس، وكوكي الدخول مخفي عن سكريبتات الصفحة."]
    },
    "v7.993.19": {
      en: ["New Home button \"Driver Deliveries\": shows the drivers who have In Process invoices, then everything a driver marked delivered on the phone. Type an invoice number in the Check box and it becomes Delivered (duplicates and numbers outside the driver's list are refused with a message). Leading zeros are ignored. Allowed per user under Users & permissions.", "The phone only records who delivered and when. The invoice stays In Process until you check it here. Setting an invoice back to In Process clears Delivered By/At.", "Settings > Firebase and phone app (Admi1 only): Add driver is now Add user with a role (Driver or Distribution manager). The Add Android application wizard publishes the new rules with a saved backup in one click. The program keeps a small marker per driver up to date so the phone refreshes cheaply."],
      ar: ["زرار جديد في Home اسمه Driver Deliveries: بيعرض السواقين اللي عندهم In Process، وتدوس على سواق تشوف كل اللي علّمه تم تسليمه من الموبايل. اكتب رقم الفاتورة في خانة Check وتبقى Delivered (التكرار والأرقام اللي برا خط السواق بتترفض برسالة). الأصفار في الأول بتتتجاهل. الصلاحية لكل يوزر من Users & permissions.", "الموبايل بيسجل مين سلّم وإمتى بس. الفاتورة بتفضل In Process لحد ما تأكدها من هنا. لما ترجّع فاتورة لـ In Process بيتمسح Delivered By/At.", "في Settings > Firebase and phone app (لـ Admi1 بس): Add driver بقى Add user وفيه دور (سواق أو مسؤول توزيع). ومعالج Add Android application بينشر القواعد الجديدة بنسخة احتياطية بضغطة واحدة. والبرنامج بيحدّث علامة صغيرة لكل سواق عشان الموبايل يتحدّث بأقل قراءات."]
    },
    "v7.983.18": {
      en: ["Invoice Details and Invoice Report now open as a full page (not a small popup) and Back returns to Home.", "New Settings section \"Firebase and phone app\" (Admi1 only): Connect with Firebase wizard, Add Android application wizard (turns on sign-in, publishes rules with a saved backup and Restore previous), Drivers window (Add, Edit, Disable/Enable, Reset password, Delete), and About Firebase plans with prices in EGP.", "New read-only fields Delivered By and Delivered At: filled by the driver phone app, or by the user who changes an invoice to Delivered.", "In the trial these buttons show \"Not available in the trial\"."],
      ar: ["Invoice Details و Invoice Report بيفتحوا دلوقتي صفحة كاملة (مش نافذة صغيرة) و Back بيرجعك لـ Home.", "قسم جديد في Settings اسمه Firebase and phone app (لـ Admi1 بس): معالج Connect with Firebase، ومعالج Add Android application (بيفتح تسجيل الدخول وينشر القواعد مع نسخة احتياطية وزرار Restore previous)، ونافذة Drivers (إضافة وتعديل وإيقاف/تفعيل وتغيير الباسورد وحذف)، و About Firebase plans بالأسعار بالجنيه.", "حقلين جداد للقراءة بس: Delivered By و Delivered At. بيتملوا من تطبيق السواق أو من المستخدم اللي يغير الفاتورة لـ Delivered.", "في النسخة التجريبية الأزرار دي مكتوب عليها Not available in the trial."]
    },
    "v7.973.17": {
      en: ["Customize buttons: every button now has \"Move to\" and an arrow. The arrow puts the button inside any other button (any level, for example Undelivered inside Invoice Details), or in Hidden, or back On Home. A button with buttons inside opens a small window with its own page first", "Button size: five sizes (XS, S, M, L, XL) for all buttons, saved per user, Reset puts it back to M", "Filters: new Blank only box next to the column filter shows only the rows where that column is empty"],
      ar: ["Customize buttons: كل زرار جمبه Move to وسهم. السهم يدخل الزرار جوة أي زرار تاني (أي مستوى، مثلاً Undelivered جوة Invoice Details) أو Hidden أو يرجعه On Home. الزرار اللي جواه أزرار بيفتح شباك صغير فيه صفحته الأول", "حجم الأزرار: خمس أحجام (XS وS وM وL وXL) لكل الأزرار، محفوظ لكل مستخدم، وReset يرجعه M", "الفلاتر: خانة Blank only جنب فلتر العمود تعرض الصفوف اللي العمود بتاعها فاضي"]
    },
    "v7.963.16": {
      en: ["Settings > Customize buttons: new board. All Home buttons are listed, drag a button into or out of a group (or click it and press Move here). Quick groups: Reports, Cash, Warehouse. Hidden box", "Conflict Expenses now looks and works like Conflict Invoices: Was / Became table, Show all fields, Keep Became, Keep Was, Reject (voids the entry, history stays) and Skip"],
      ar: ["Settings > Customize buttons: شاشة جديدة فيها كل أزرار Home، تسحب أي زرار جوة مجموعة أو برا (أو تدوس عليه وبعدين Move here). مجموعات سريعة: Reports وCash وWarehouse، وصندوق Hidden", "Conflict Expenses بقت بنفس شكل ونظام Conflict Invoices: جدول Was / Became وShow all fields وKeep Became وKeep Was وReject (بيعمل Void للإدخال والتاريخ يفضل) وSkip"]
    },
    "v7.953.15": {
      en: ["Conflict Invoices: every item now has a Reject button for false conflicts", "Settings > Customize buttons: move buttons, hide them, or put buttons inside a group or the More menu on the top bar. Reset puts everything back"],
      ar: ["الكونفليكت: كل عنصر فيه زرار Reject للكونفليكت الغلط", "Settings > Customize buttons: تنقل الأزرار وتخفيها أو تحطها جوة مجموعة أو جوة قائمة More في الشريط اللي فوق. وفي Reset يرجع كل حاجة"]
    },
    "v7.943.14": {
      en: ["Notifications: point at a notification and it moves to Earlier right away, and the header counter goes down at once. A Mark all as read button sits at the top"],
      ar: ["الإشعارات: لما تقف بالماوس على إشعار بينزل تحت في Earlier على طول والرقم اللي فوق بينقص فورا. وفي زر تعليم الكل كمقروء فوق"]
    },
    "v7.923.12": {
      en: ["Notifications no longer miss an Edit when an invoice is added and edited within a few seconds, or when changes were made while the program was closed or updating"],
      ar: ["الإشعارات بقت متفوتش التعديل لو الفاتورة اتضافت واتعدلت في ثواني، أو لو التغييرات حصلت والبرنامج مقفول أو بيتحدث"]
    },
    "v7.913.11": {
      en: ["Update and Restore questions now open in the program's own dialog instead of a browser-style box"],
      ar: ["أسئلة التحديث والاسترجاع بقت بتظهر في نافذة البرنامج نفسه بدل صندوق المتصفح"]
    },
    "v7.903.10": {
      en: ["The edit notice shows what it was and what it became",
           "Update closes the old program and opens the new one by itself",
           "The program opens only once; if it is already open, it comes to the front",
           "Live sync moved to the top, next to the user name",
           "A green bar tells you when a new version is available",
           "The History button was removed (Notifications replaces it)"],
      ar: ["الإشعار بيوضح كانت إيه وبقت إيه بعد التعديل",
           "التحديث بيقفل البرنامج القديم ويفتح الجديد لوحده",
           "البرنامج بيفتح مرة واحدة، ولو مفتوح بيظهر قدامك",
           "Live sync بقى فوق جنب اسم المستخدم",
           "شريط أخضر بيقولك لما يكون فيه نسخة جديدة",
           "زرار History اتشال (Notifications مكانه)"]
    }
  };
  function seen(v) { return document.cookie.split("; ").some(c => c === "dp_wn=" + v); }
  function mark(v) { document.cookie = "dp_wn=" + v + "; max-age=94608000; path=/; SameSite=Lax"; }
  let busy = false, done = false;
  async function tick() {
    if (busy || done) return;
    try {
      if (typeof S === "undefined" || !S || !S.user) return;
      busy = true;
      const r = await (await fetch("/api/instance")).json();
      const v = String(r.version || "").split(" ")[0], n = NEWS[v];
      if (!n || seen(v)) { done = true; return; }
      if (document.getElementById("wn-box")) return;
      const ar = (typeof PREFS !== "undefined" && PREFS.lang === "ar");
      const o = document.createElement("div"); o.id = "wn-box";
      o.style.cssText = "position:fixed;inset:0;background:rgba(15,23,42,.45);z-index:99998;display:flex;align-items:center;justify-content:center;font-family:Segoe UI,Arial,sans-serif";
      const b = document.createElement("div");
      b.style.cssText = "background:#fff;border-radius:12px;width:430px;max-width:92vw;padding:18px 20px;box-shadow:0 12px 40px rgba(0,0,0,.35);color:#0f172a";
      if (ar) b.dir = "rtl";
      const h = document.createElement("div"); h.style.cssText = "display:flex;justify-content:space-between;align-items:center";
      const t = document.createElement("b"); t.style.fontSize = "17px"; t.textContent = ar ? "الجديد" : "What's New";
      const vv = document.createElement("span"); vv.style.cssText = "font-size:12px;color:#64748b"; vv.textContent = v;
      h.append(t, vv);
      const ul = document.createElement("ul"); ul.style.cssText = "margin:12px 0 14px;padding-inline-start:20px;line-height:1.7;font-size:14px";
      for (const x of (ar ? n.ar : n.en)) { const li = document.createElement("li"); li.textContent = x; ul.append(li); }
      const row = document.createElement("div"); row.style.textAlign = ar ? "left" : "right";
      const ok = document.createElement("button"); ok.textContent = ar ? "تمام" : "Got it";
      ok.style.cssText = "background:#1e3a8a;color:#fff;border:0;border-radius:7px;padding:7px 18px;font-weight:700;cursor:pointer";
      const close = () => { mark(v); done = true; o.remove(); };
      ok.onclick = close; o.onclick = e => { if (e.target === o) close(); };
      row.append(ok); b.append(h, ul, row); o.append(b); document.body.append(o);
    } catch (e) {} finally { busy = false; }
  }
  setInterval(tick, 2000);
})();
