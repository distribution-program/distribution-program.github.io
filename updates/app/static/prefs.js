/* Distribution Program view preferences (per device, stored locally) + English/Arabic UI language.
   Visibility is view-only: hidden columns keep their data, stay searchable,
   and stay visible inside invoice details, reports and exports. */
"use strict";
const PREFS_KEY = "ut_view_v1";
// Exact invoice table order requested by the user. Specialized reports keep their own layouts.
const DEFAULT_COLS = ["ID", "Invoice Number", "Invoice Date", "Sales Order No", "Customer Name",
  "Invoice Value", "Sales Taker", "Invoice Status", "District", "Forward To", "Invoice Type",
  "Payment Terms", "Brand Name", "Car No", "Driver name", "Distribution Rep", "Distribution Rep1",
  "Distributed Date", "Line", "Transfer from", "Remarks", "Field1", "Return Value", "Field2",
  "Expected Date", "Purchase Order NO", "Collected Date", "Collected Fees", "Document Deliver Date",
  "Date required", "Field5", "Cost Date Required", "Cost Date", "F34"];
let PREFS = { cols: null, lang: "en", fs: "m", dens: "cozy", layout: 2 };
try {
  const p = JSON.parse(localStorage.getItem(PREFS_KEY) || "{}");
  PREFS = Object.assign(PREFS, p);
  // One-time correction of the old seven-column/reordered layout only.
  if (p.layout !== 2) { PREFS.cols = null; PREFS.layout = 2; }
} catch (e) { /* fresh prefs */ }
function savePrefs() { localStorage.setItem(PREFS_KEY, JSON.stringify(PREFS)); }
savePrefs();
function canonicalCols(allCols) {
  return DEFAULT_COLS.filter(c => allCols.includes(c)).concat(allCols.filter(c => !DEFAULT_COLS.includes(c)));
}
function visibleColIdx(allCols) {
  const names = PREFS.cols === null ? DEFAULT_COLS : PREFS.cols;
  return canonicalCols(allCols).filter(c => names.includes(c)).map(c => allCols.indexOf(c));
}

/* ---------------- UI language ---------------- */
const DICT = {
  "Last full import result": "نتيجة آخر استيراد كامل", "Import diagnostics": "تشخيص الاستيراد",
  "Full import result": "نتيجة الاستيراد الكامل", "Importing full data": "جارٍ استيراد البيانات كاملة",
  "Last 5 days (undated included)": "آخر 5 أيام (تشمل غير المؤرخة)",
  "Desktop icon": "أيقونة سطح المكتب", "Quit": "إغلاق البرنامج",
  "Distribution Program stopped. You can close this window. Open the desktop icon to start again.": "تم إغلاق Distribution Program. يمكنك إغلاق النافذة وتشغيله مجددًا من أيقونة سطح المكتب.",

  "Edit invoice (all fields)": "تعديل الفاتورة (كل الخانات)",
  "Select one invoice first.": "اختار فاتورة واحدة الأول.",
  "Save changes": "حفظ التعديلات",
  /* chrome */
  "Login": "تسجيل الدخول", "Menu": "القائمة", "Home": "الرئيسية", "Search Invoice": "بحث الفواتير",
  "New Invoice": "فاتورة جديدة", "Undelivered": "غير المُسلَّمة", "Invoice Details": "تفاصيل الفواتير",
  "Invoice Report": "تقرير الفواتير", "Warehouse Report": "تقرير المخزن", "RGR Not Costed": "RGR غير مُسعَّر",
  "Users": "المستخدمون", "Backup": "النسخ الاحتياطي", "Data": "البيانات", "Help": "مساعدة",
  "Review sync conflicts": "مراجعة تعارضات المزامنة", "Preserved sync conflicts": "تعارضات المزامنة المحفوظة",
  "Settings": "الإعدادات", "Light / Dark": "فاتح / داكن", "Refresh (F5)": "تحديث (F5)", "Sync": "مزامنة",
  "⚙ Settings": "⚙ الإعدادات", "⟳ Sync": "⟳ مزامنة",
  "Manage users (ADMIN only)": "إدارة المستخدمين (للمسؤول فقط)", "Manage users": "إدارة المستخدمين",
  "Backup new data now (to shared folder)": "نسخ احتياطي للبيانات الجديدة الآن (إلى المجلد المشترك)",
  "Load a backup file...": "استرجاع نسخة احتياطية...", "Set shared folder...": "تحديد المجلد المشترك...",
  "Sync now (F5)": "مزامنة الآن (F5)", "Import full data (Excel)": "استيراد كل البيانات (Excel)",
  "Import lists": "استيراد القوائم", "About": "عن البرنامج", "About Distribution Program": "عن Distribution Program",
  "Proposal Report": "تقرير العروض", "In Process Report": "تقرير قيد التنفيذ",
  "Invoice to Head Office": "فواتير المكتب الرئيسي",
  /* statuses */
  "Delivered": "تم التسليم", "Cancelled": "ملغاة", "Unsettled invoices - delivered": "فواتير غير مسواة - مُسلَّمة",
  "Replacement": "استبدال", "Delivered By shipped": "سُلِّمت بالشحن", "Pending": "معلّقة",
  "inprocess": "قيد التنفيذ", "Proposal": "عرض مقترح", "RETURN LIST": "قائمة المرتجعات", "temporary": "مؤقتة",
  /* columns */
  "ID": "الكود", "Invoice Number": "رقم الفاتورة", "Invoice Date": "تاريخ الفاتورة",
  "Sales Order No": "رقم أمر البيع", "Customer Name": "اسم العميل", "Invoice Value": "قيمة الفاتورة",
  "Sales Taker": "مندوب المبيعات", "Invoice Status": "حالة الفاتورة", "District": "المنطقة",
  "Forward To": "توجيه إلى", "Invoice Type": "نوع الفاتورة", "Payment Terms": "شروط الدفع",
  "Brand Name": "اسم البراند", "Car No": "رقم السيارة", "Driver name": "اسم السائق",
  "Distribution Rep": "مندوب التوزيع", "Distribution Rep1": "مندوب التوزيع 1",
  "Distributed Date": "تاريخ التوزيع", "Line": "الخط", "Transfer from": "تحويل من",
  "Remarks": "ملاحظات", "Field1": "Field1", "Return Value": "قيمة المرتجع", "Field2": "Field2",
  "Expected Date": "التاريخ المتوقع", "Purchase Order NO": "رقم أمر الشراء",
  "Collected Date": "تاريخ التحصيل", "Collected Fees": "الرسوم المحصّلة",
  "Document Deliver Date": "تاريخ تسليم المستند", "Date required": "التاريخ المطلوب",
  "Field5": "Field5", "Cost Date Required": "تاريخ التسعير مطلوب", "Cost Date": "تاريخ التسعير",
  "Entered By": "أدخلها", "Delivered By": "سلّمها", "Delivered At": "وقت التسليم",
  /* filters + labels */
  "Invoice / Sales Order:": "رقم الفاتورة / أمر البيع:", "Customer:": "العميل:",
  "Date (dd/mm/yyyy, mm/yyyy, yyyy):": "التاريخ (يوم/شهر/سنة):", "Last 5 days only": "آخر 5 أيام فقط",
  "Filter column:": "عمود التصفية:", "(or click a title)": "(أو اضغط على عنوان عمود)",
  "Date": "التاريخ", "Driver": "السائق", "Print": "طباعة", "User": "المستخدم", "Password": "كلمة المرور",
  "Printed on (dd/mm/yyyy):": "تاريخ الطباعة (يوم/شهر/سنة):", "Invoice:": "الفاتورة:",
  /* buttons */
  "Edit selected (bulk)": "تعديل المحدد (جماعي)", "Delete selected": "حذف المحدد", "Print results": "طباعة النتائج",
  "Save invoice": "حفظ الفاتورة", "Clear": "مسح", "Import new invoices from Excel": "استيراد فواتير جديدة من Excel",
  "Create PDF": "إنشاء PDF", "Sales Orders (delivery notes)": "أوامر البيع (إذون التسليم)",
  "Invoices printed": "الفواتير المطبوعة", "Import Excel (adds new rows only)": "استيراد Excel (يضيف صفوفًا جديدة فقط)",
  "Print new only": "طباعة الجديد فقط", "Reprint all": "إعادة طباعة الكل", "Clear all": "مسح الكل",
  "Import invoices Excel (marks Printed, nothing is printed)": "استيراد Excel الفواتير (يُعلِّمها كمطبوعة)",
  "Save PDF": "حفظ PDF", "Save PDF (no printing)": "حفظ PDF (بدون طباعة)", "Close": "إغلاق", "Cancel": "إلغاء", "Save": "حفظ", "Browse...": "استعراض...",
  "Print Status Sales Order": "حالة طباعة إذن البيع", "Print Status Invoice": "حالة طباعة الفاتورة", "Printed": "مطبوع",
  "Delete user": "حذف المستخدم", "Add user": "إضافة مستخدم", "Import list": "استيراد قائمة",
  "Backup new data now": "نسخ احتياطي الآن", "Shared network folder...": "المجلد المشترك للشبكة...",
  /* settings */
  "New update": "تحديث جديد", "available": "متاح", "Open Update": "افتح التحديث", "Later": "لاحقاً",
  "Choose table columns": "اختيار أعمدة الجدول", "Select all": "تحديد الكل", "selected": "محدد",
  "Switch to Light": "التحويل إلى الفاتح", "Switch to Dark": "التحويل إلى الداكن",
  "Appearance": "المظهر", "Connection": "الاتصال", "Backup & data": "النسخ الاحتياطي والبيانات",
  "Administration": "الإدارة", "Table columns": "أعمدة الجدول", "Language": "اللغة",
  "Font size": "حجم الخط", "Table density": "كثافة الجدول", "Small": "صغير", "Medium": "وسط", "Large": "كبير",
  "Compact": "مضغوط", "Comfortable": "مريح", "Restore default view": "استعادة العرض الافتراضي",
  "Status": "الحالة", "Warehouse": "المخزن", "Shared folder": "المجلد المشترك",
  "Network and Cloud status are shown live in the top bar.": "حالة الشبكة والسحابة تظهر مباشرة في الشريط العلوي.",
  "Hiding a column only changes this screen on this PC. Nothing is deleted: hidden columns stay saved, searchable and printable.":
    "إخفاء العمود يغيّر العرض على هذا الجهاز فقط. لا يُحذف أي شيء: الأعمدة المخفية تبقى محفوظة وقابلة للبحث والطباعة.",
  "Scroll inside the list to see them all.": "حرّك داخل القايمة عشان تشوفهم كلهم.",
  /* hints */
  "Ctrl+A = select all | Ctrl/Shift+click = select many | Tab / arrows = move | Enter = edit":
    "Ctrl+A = تحديد الكل | Ctrl/Shift+click = تحديد متعدد | Tab / الأسهم = تحرّك | Enter = تعديل",
  "Shows Invoice Type RGR while either cost date is blank. Pending RGR stays visible at any age, even with Last 5 days checked.":
    "يعرض فواتير RGR التي لم يُطلب تاريخ تسعيرها ولم تُسعَّر بعد.",
};
Object.assign(DICT,{"Prepare dispatch now":"تجهيز التوزيع الآن","Remarks (optional)":"ملاحظات (اختياري)","Choose stage":"اختر المرحلة","Dispatch stage":"مرحلة التوزيع","Save & next":"حفظ والتالي","Skip (not saved)":"تخطي (بدون حفظ)","Resume classification":"استكمال التصنيف"});
function T(s) { return (PREFS.lang === "ar" && DICT[s]) ? DICT[s] : s; }
function applyLang() {
  const ar = PREFS.lang === "ar";
  document.documentElement.dir = ar ? "rtl" : "ltr";
  document.documentElement.lang = PREFS.lang;
  document.body.classList.toggle("rtl", ar);
  // translate text-only elements; never touch ones with child elements (checkboxes, icons)
  document.querySelectorAll("button, th, h1, h2, h3, label, a, option, .hint, span.slab, span.home-lab, span[data-en]").forEach(n => {
    if (n.children.length) return;
    let txt = n.textContent.trim();
    let arrow = "";
    const m = txt.match(/^(.*?)[\s ]*[▾▼]$/u);
    if (m) { txt = m[1].trim(); arrow = " ▾"; }
    if (!n.dataset.en) { if (DICT[txt]) n.dataset.en = txt; }
    if (n.dataset.en) n.textContent = (ar ? (DICT[n.dataset.en] || n.dataset.en) : n.dataset.en) + arrow;
  });
}
function applyAppearance() {
  document.body.classList.toggle("fs-s", PREFS.fs === "s");
  document.body.classList.toggle("fs-l", PREFS.fs === "l");
  document.body.classList.toggle("dens-compact", PREFS.dens === "compact");
}
function setLang(l) { PREFS.lang = l; savePrefs(); applyLang(); refreshCurrent(); }
