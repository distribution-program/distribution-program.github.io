"""Distribution Program - Invoice Program (Browser edition)
Local-first (SQLite) + optional Firebase Firestore + LAN sharing through a shared folder.
Core logic module: database, helpers, PDF builders and sync. The user interface lives in
static/index.html and is served by server.py. Original Tkinter program by Eng. Kirollos William,
converted to a browser app without changing its behavior.
"""
import os, sys, re, json, uuid, time, tempfile, shutil, socket, hashlib, sqlite3, threading, datetime as dt
import base64, webbrowser
from xml.sax.saxutils import escape
# optional cloud: the program works fully offline / on the LAN folder without it.
# firebase-admin is only imported when its key file sits next to the program, so startup stays fast.
import connectedtest
import replicamode
REPLICA=replicamode.load(os.environ.get("DPROGRAM_REPLICA_CONFIG"))
CONNECTED_TEST=replicamode.connected(REPLICA) if REPLICA else connectedtest.load(os.environ.get("DPROGRAM_CONNECTED_TEST_CONFIG"))
# Public/customer package: marked by this file. It ALWAYS runs in its own isolated profile (never the company InvoiceApp folder),
# even when started without the launcher (for example python server.py from a command window).
if os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), "public_edition.flag")):
    os.environ["DPROGRAM_TEST_MODE"] = "1"
    os.environ.setdefault("DPROGRAM_TRIAL_LIMIT", "50")
TEST_MODE = os.environ.get("DPROGRAM_TEST_MODE") == "1"
TRIAL_PRINTING = TEST_MODE and os.environ.get("DPROGRAM_TRIAL_PRINTING") == "1"
try:TRIAL_LIMIT = int(os.environ.get("DPROGRAM_TRIAL_LIMIT", "0") or 0) if TEST_MODE else 0  # public trial edition: max invoices ever created on this PC
except ValueError:TRIAL_LIMIT = 0
if CONNECTED_TEST and TEST_MODE:raise ValueError("Choose offline trial OR connected test, not both")
CREDENTIAL_PATH=os.environ.get("DPROGRAM_TEST_CREDENTIAL_PATH") or os.path.join(os.path.dirname(os.path.abspath(__file__)),"serviceAccountKey.json")
def _bootlog(m):
    try:
        if TRIAL_LIMIT:
            with open(os.path.join(os.path.expanduser("~"), "InvoiceApp_Isolated_Trial", "boot.log"), "a", encoding="utf-8") as _f: _f.write("%s pid=%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), os.getpid(), m))
    except Exception: pass
def _grpc_roots_file():
    """Trusted root certificates for gRPC: the certifi bundle plus the Windows certificate store (so a company antivirus that re-signs
    Google certificates is trusted, exactly like the connection launcher does). Written next to the program data; verification stays on."""
    try:
        import ssl
        pems = []
        try:
            import certifi
            pems.append(open(certifi.where(), "r", encoding="ascii", errors="ignore").read())
        except Exception: pass
        if os.name == "nt":
            for store in ("ROOT", "CA"):
                try:
                    for cert, enc, trust in ssl.enum_certificates(store):
                        if enc == "x509_asn": pems.append(ssl.DER_cert_to_PEM_cert(cert))
                except Exception: pass
        if not pems: return ""
        p = os.path.join(os.path.expanduser("~"), "InvoiceApp_Isolated_Trial", "grpc_roots.pem")
        with open(p, "w", encoding="ascii") as f: f.write("\n".join(pems))
        return p
    except Exception:
        return ""
def _fb_probe():
    """Public edition: try the Firebase start-up (library load, key parse, client, gRPC channel) in a separate short-lived process first.
    If it crashes, hangs or fails there, this program starts without Firebase instead of dying, and boot.log says why.
    After a crash it retries once with the native DNS resolver for gRPC, which avoids a crash seen on some Windows PCs."""
    import subprocess
    code = ("import sys,os,time\n"
            "P=os.path.join(os.path.expanduser('~'),'InvoiceApp_Isolated_Trial','boot.log')\n"
            "def L(m):\n"
            "    open(P,'a',encoding='utf-8').write(time.strftime('%%Y-%%m-%%d %%H:%%M:%%S')+' probe '+m+'\\n')\n"
            "try:\n"
            "    import faulthandler;faulthandler.enable(open(P,'a'))\n"
            "    L('import');import firebase_admin;from firebase_admin import credentials,firestore\n"
            "    L('certificate');c=credentials.Certificate(%r)\n"
            "    L('initialize_app');firebase_admin.initialize_app(c)\n"
            "    L('client');d=firestore.client();L('client ok project='+str(d.project))\n"
            "    L('grpc channel');d._firestore_api;L('grpc channel ok')\n"
            "except BaseException as e:\n"
            "    import traceback;L('ERROR '+traceback.format_exc()[-700:]);sys.exit(3)\n") % (CREDENTIAL_PATH,)
    fl = 0x08000000 if os.name == "nt" else 0
    _ee = "-event_engine_client,-event_engine_listener,-event_engine_dns,-event_engine_fork,-event_engine_for_all_other_endpoints,-event_engine_client_channel_resolver"
    roots = _grpc_roots_file()
    R = {"GRPC_DEFAULT_SSL_ROOTS_FILE_PATH": roots} if roots else {}
    variants = (dict(R, GRPC_DNS_RESOLVER="native"),
                dict(R, GRPC_DNS_RESOLVER="native", GRPC_EXPERIMENTS=_ee, GRPC_ENABLE_FORK_SUPPORT="0", GRPC_POLL_STRATEGY="poll"),
                dict(GRPC_DNS_RESOLVER="native", GRPC_EXPERIMENTS=_ee, GRPC_ENABLE_FORK_SUPPORT="0", GRPC_POLL_STRATEGY="poll"),
                {})
    errp = os.path.join(os.path.expanduser("~"), "InvoiceApp_Isolated_Trial", "probe_stderr.txt")
    for n, extra in enumerate(variants):
        env = dict(os.environ); env.update(extra); env["GRPC_VERBOSITY"] = "DEBUG"
        _bootlog("firebase probe start variant %d %s" % (n + 1, sorted(extra)))
        try:
            with open(errp, "wb") as _ef:
                r = subprocess.run([sys.executable, "-c", code], timeout=30, creationflags=fl, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=_ef)
        except subprocess.TimeoutExpired:
            _bootlog("firebase probe TIMED OUT after 30s: skipping Firebase for this start"); raise RuntimeError("Firebase probe timed out")
        except Exception as e:
            _bootlog("firebase probe could not run: %r (continuing)" % (e,)); return
        if r.returncode == 0:
            os.environ.update(extra); _bootlog("firebase probe ok (variant %d)" % (n + 1)); return
        try:
            _tail = open(errp, "rb").read()[-1200:].decode("utf-8", "replace").replace("\r", "")
        except Exception: _tail = ""
        _bootlog("firebase probe FAILED rc=%s stderr tail: %s" % (r.returncode, _tail))
        if r.returncode == 3: break       # a normal Python error (for example a bad key): retrying will not help
    raise RuntimeError("Firebase probe failed: Firebase skipped for this start")

if (not TEST_MODE or TRIAL_LIMIT) and os.path.exists(CREDENTIAL_PATH):
    # The Firebase libraries are large. On a PC where they have never been loaded (nothing compiled yet, antivirus scanning every file)
    # the first import can take a very long time. Import them in a helper thread and give up waiting after 25 s so the program
    # always opens (local data only); the import keeps going in the background, so the next start is fast.
    import threading as _th, traceback as _tb
    _fb = {}
    def _fb_import():
        try:
            import firebase_admin as _fa
            from firebase_admin import credentials as _cr, firestore as _fs
            from google.cloud.firestore_v1.base_query import FieldFilter as _ff
            _fb.update(fa=_fa, cr=_cr, fs=_fs, ff=_ff)
        except BaseException:
            _fb["err"] = _tb.format_exc()
        _fb["done"] = True
    _t = _th.Thread(target=_fb_import, daemon=True); _t.start(); _t0 = time.time(); _t.join(25 if TRIAL_LIMIT else None)
    def _fblog(m):
        try:
            if TRIAL_LIMIT:
                with open(os.path.join(os.path.expanduser("~"), "InvoiceApp_Isolated_Trial", "boot.log"), "a", encoding="utf-8") as _f: _f.write("%s pid=%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), os.getpid(), m))
        except Exception: pass
    if _fb.get("fa") is not None:
        firebase_admin, credentials, firestore, FieldFilter = _fb["fa"], _fb["cr"], _fb["fs"], _fb["ff"]
        _fblog("firebase libraries imported in %.1fs" % (time.time() - _t0))
    else:
        firebase_admin = None
        FIREBASE_IMPORT_PENDING = not _fb.get("done")
        _fblog("firebase libraries NOT loaded after %.1fs (%s)" % (time.time() - _t0, "still importing in the background, local data only until the next start" if FIREBASE_IMPORT_PENDING else "import error: " + str(_fb.get("err"))[-600:]))
else:
    firebase_admin = None
import openpyxl
import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, KeepTogether, PageBreak
COMPANY = "Distribution Program"
LOGIN_TITLE = "Distribution Program | " + ("REPLICA kw20" if REPLICA else "MAIN")
WH_PRINTER = "كيرلس وليم"
HERE = os.path.dirname(os.path.abspath(__file__))
STATUSES = ["Delivered", "Cancelled", "Unsettled invoices - delivered", "Replacement",
            "Delivered By shipped", "Undelivered", "Pending", "inprocess", "Proposal",
            "RETURN LIST", "temporary"]
BASE = ["ID", "Invoice Number", "Invoice Date", "Sales Order No", "Customer Name",
        "Invoice Value", "Sales Taker", "Invoice Status", "District", "Forward To",
        "Invoice Type", "Payment Terms", "Brand Name", "Car No", "Driver name",
        "Distribution Rep", "Distribution Rep1", "Distributed Date", "Line",
        "Transfer from", "Remarks", "Field1", "Return Value", "Field2", "Expected Date",
        "Purchase Order NO", "Collected Date", "Collected Fees", "Document Deliver Date",
        "Date required", "Field5", "Cost Date Required", "Cost Date", "F34",
        "Print Status Sales Order", "Print Status Invoice"]
COLS = BASE + ["Entered By", "Delivered By", "Delivered At"]
LOCKED = {"Entered By", "Delivered By", "Delivered At", "Print Status Sales Order", "Print Status Invoice"}
EDITABLE = set(COLS) - LOCKED
RGR_COLS = ["Invoice Number", "Invoice Date", "Distributed Date", "Customer Name",
            "Cost Date Required", "Cost Date", "Remarks"]
LIST_FIELDS = {"Customer Name": "customers", "Transfer from": "customers",
               "District": "district", "Forward To": "forward_to",
               "Invoice Type": "invoice_type", "Payment Terms": "payment_terms",
               "Brand Name": "brand", "Car No": "car_no", "Driver name": "drivers",
               "Distribution Rep": "reps", "Distribution Rep1": "reps", "Line": "line"}
DRIVERS = []
REPS = []
FORWARD_TO = []
INV_TYPES = ["RGR", "Transfer", "D/RE-PACKING", "JOURNAL Transfer", 
             "Commercial Invoice", "RETURN LIST", "Purchase order", "External Order"]
PAY_TERMS = ["FREE", "Management", "Reduce from Credit Account"]
DEFAULT_LISTS = {"drivers": DRIVERS, "reps": REPS, "line": ["1", "2", "3", "4", "5"],
                 "forward_to": FORWARD_TO, "invoice_type": INV_TYPES}
LISTS, CD_MAP = {}, {}
ACCENT, ACCENT_2, ACCENT_3 = "#0f4c81", "#2b6cb0", "#1e4e8c"
SIDE_PAL = {"light": dict(home="#e2e8f0", search="#dbeafe", new="#dcfce7", und="#ffedd5", details="#ede9fe", rep="#fce7f3", wh="#cffafe", rgr="#fef9c3"),
            "dark": dict(home="#334155", search="#1e3a8a", new="#14532d", und="#7c2d12", details="#4c1d95", rep="#831843", wh="#164e63", rgr="#713f12")}
SIDE_FG = {"light": "#1e293b", "dark": "#f1f5f9"}
APP_VERSION = "v8.173.37"
VERSION = APP_VERSION + (" Replica" if REPLICA else " Main")
CREDIT = "\u00a9 2026 Distribution Program. All rights reserved.   |   Made by Eng. Kirollos William"
MAX_ROWS = 1200   # a screen never loads more than this (keeps every tab fast); the newest rows are shown
DATE_COLS = {"Invoice Date", "Distributed Date", "Expected Date", "Collected Date", "Document Deliver Date",
             "Date required", "Cost Date Required", "Cost Date"}
REP_COLS = ["Invoice Number", "Invoice Date", "Customer Name", "District", "Invoice Value", "Distributed Date",
            "Driver name", "Car No", "Line", "Remarks"]
EXEMPT = {"Undelivered", "inprocess", "Proposal", "Pending"}   # no current-month limit
SIGNATURE = "Designed & developed by Eng. Kirollos William \u00a9 2026"
ACK = 'أقر أنا الموقّع أدناه بأنني استلمت الفواتير المبيّنة في هذا الكشف سليمة وكاملة، وأتعهد بتسليمها إلى العملاء وتحصيل قيمتها. كما ألتزم، بعد توقيع العملاء عليها، بتوريد المبالغ والمستندات إلى إدارة التوزيع في الموعد المحدد، وأتحمل المسؤولية الكاملة عن أي عجز أو فقد أو تأخير.'
try:
    pdfmetrics.registerFont(TTFont("AR", r"C:\Windows\Fonts\arial.ttf"))
    pdfmetrics.registerFont(TTFont("ARB", r"C:\Windows\Fonts\arialbd.ttf"))
    F, FB = "AR", "ARB"
except Exception:
    try:
        pdfmetrics.registerFont(TTFont("AR", os.path.join(HERE, "fonts", "DejaVuSans.ttf")))
        pdfmetrics.registerFont(TTFont("ARB", os.path.join(HERE, "fonts", "DejaVuSans-Bold.ttf")))
        F, FB = "AR", "ARB"
    except Exception:
        F, FB = "Helvetica", "Helvetica-Bold"
# ---------------- per-device settings + local database ----------------
DATA_DIR = os.path.join(os.path.expanduser("~"),"InvoiceApp_Firebase_Replica_v31_"+REPLICA["run_id"]) if REPLICA else connectedtest.profile(os.path.expanduser("~"),CONNECTED_TEST) if CONNECTED_TEST else os.path.join(os.path.expanduser("~"), "InvoiceApp_Isolated_Trial" if TEST_MODE else "InvoiceApp")
if CONNECTED_TEST and not REPLICA:connectedtest.validate_share(CONNECTED_TEST)
os.makedirs(DATA_DIR, exist_ok=True)
SET_FILE = os.path.join(DATA_DIR, "settings.json")
try:
    with open(SET_FILE, encoding="utf-8") as _f:
        SETTINGS = json.load(_f)
except Exception:
    SETTINGS = {}


def save_settings():
    with open(SET_FILE, "w", encoding="utf-8") as f:
        json.dump(SETTINGS, f)


DB_FILE, OLD_DB = os.path.join(DATA_DIR, "invoices_local.db"), os.path.join(HERE, "invoices_local.db")
if not TEST_MODE and not CONNECTED_TEST and not os.path.exists(DB_FILE) and os.path.exists(OLD_DB):
    shutil.copy(OLD_DB, DB_FILE)
LOCK = threading.RLock()
cx = sqlite3.connect(DB_FILE, check_same_thread=False)
cx.executescript("""
CREATE TABLE IF NOT EXISTS inv(uid TEXT PRIMARY KEY, data TEXT, updated REAL, dirty INT);
CREATE TABLE IF NOT EXISTS lst(name TEXT PRIMARY KEY, items TEXT, dirty INT);
CREATE TABLE IF NOT EXISTS usr(name TEXT PRIMARY KEY, pw TEXT, updated REAL, dirty INT);
CREATE TABLE IF NOT EXISTS del(kind TEXT, key TEXT);
CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS dellan(uid TEXT PRIMARY KEY, ts REAL, lan INT);""")
try:
    cx.execute("ALTER TABLE inv ADD COLUMN lan INT DEFAULT 1")   # 1 = not yet shared on the LAN folder
    cx.commit()
except sqlite3.OperationalError:
    pass


def q(sql, args=()):
    with LOCK:
        rows = cx.execute(sql, args).fetchall()
        cx.commit()
        return rows


def meta(k, d=0):
    r = q("SELECT v FROM meta WHERE k=?", (k,))
    return r[0][0] if r else d


def setmeta(k, v):
    q("INSERT OR REPLACE INTO meta VALUES(?,?)", (k, str(v)))


def db_put(items, dirty=1, lan=1):
    with LOCK:
        for uid, data in items:
            if cx.execute("SELECT 1 FROM dellan WHERE uid=?", (uid,)).fetchone():
                raise ValueError("This invoice was deleted. Reusing its number needs an explicit restore: " + uid)
        _lic = None
        if TRIAL_LIMIT:
            import license_mgr
            _lic = license_mgr.status(sys.modules[__name__])
            if _lic["readonly"]:
                raise ValueError("Trial finished: the 50 operations are used. View and search still work. Press Enter license and paste your license key to continue.")
            row = cx.execute("SELECT v FROM meta WHERE k='trial_ops'").fetchone()
            used = int(row[0]) if row else 0
            fresh = len({u for u, _ in items if not cx.execute("SELECT 1 FROM inv WHERE uid=?", (u,)).fetchone()})  # only NEW invoices count; edits are free
            if fresh and not _lic["licensed"] and used + fresh > TRIAL_LIMIT:
                raise ValueError("Trial version limit reached: %d operations (add, edit, delete or print). Press Enter license and paste your license key to continue." % TRIAL_LIMIT)
        cx.executemany("INSERT OR REPLACE INTO inv(uid,data,updated,dirty,lan) VALUES(?,?,?,?,?)",
                       [(u, json.dumps(d, ensure_ascii=False), d.get("updated", 0), dirty, lan) for u, d in items])
        if TRIAL_LIMIT and fresh and not _lic["licensed"]:
            cx.execute("INSERT OR REPLACE INTO meta VALUES('trial_ops',?)", (str(used + fresh),))
            license_mgr.status(sys.modules[__name__], True)
        cx.commit()


def trial_bump(n=1, pre_only=False):
    """Trial edition: one more operation (edit or print click). Free once a valid license is active. Raises when the limit is reached."""
    if not TRIAL_LIMIT: return
    import license_mgr
    with LOCK:
        st = license_mgr.status(sys.modules[__name__])
        if st["licensed"]: return
        row = cx.execute("SELECT v FROM meta WHERE k='trial_ops'").fetchone()
        used = int(row[0]) if row else 0
        if used + (0 if pre_only else n) > TRIAL_LIMIT or (pre_only and used >= TRIAL_LIMIT):
            raise ValueError("Trial version limit reached: %d operations (add, edit, delete or print). Press Enter license and paste your license key to continue." % TRIAL_LIMIT)
        if pre_only or st["readonly"]: return   # expired license: print stays allowed and is not counted
        cx.execute("INSERT OR REPLACE INTO meta VALUES('trial_ops',?)", (str(used + n),))
        cx.commit()
        license_mgr.status(sys.modules[__name__], True)


# v54 ordering metadata is local and never changes existing invoice/user payloads.
q("CREATE TABLE IF NOT EXISTS invoice_order(uid TEXT PRIMARY KEY, arrival INTEGER NOT NULL)")
with LOCK:
    for uid, in cx.execute("SELECT uid FROM inv ORDER BY rowid").fetchall():
        cx.execute("INSERT OR IGNORE INTO invoice_order(uid,arrival) VALUES(?,(SELECT COALESCE(MAX(arrival),0)+1 FROM invoice_order))",(uid,))
    cx.executescript("""DROP TRIGGER IF EXISTS v54_invoice_arrival; CREATE TRIGGER v54_invoice_arrival AFTER INSERT ON inv WHEN NOT EXISTS(SELECT 1 FROM invoice_order WHERE uid=NEW.uid) BEGIN
    INSERT OR IGNORE INTO invoice_order(uid,arrival) VALUES(NEW.uid,(SELECT COALESCE(MAX(arrival),0)+1 FROM invoice_order)); END;""")
    cx.commit()
def arrival_key(uid):
    row=q("SELECT arrival FROM invoice_order WHERE uid=?",(uid,))
    return row[0][0] if row else 0

INTEGRITY = {'ed25519.py': '05fc4835b5debb89f5fa15f757c03111d9fb1bd8e91b79b62e1f3751f6ba071d', 'license_mgr.py': 'd7d1014d9cc0ad757866fa3907d626a557ef6f9159e5b6ccdd68a25ac1f54459'}  # stamped at build time: SHA-256 of the license files. An edited license file makes the trial read-only.
TAMPERED = False
if TRIAL_LIMIT and INTEGRITY:
    try:
        for _f, _h in INTEGRITY.items():
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), _f), "rb") as _fh:
                if hashlib.sha256(_fh.read()).hexdigest() != _h: TAMPERED = True
    except Exception:
        TAMPERED = True
if TRIAL_LIMIT:  # public trial: every invoice delete also counts as one operation (until a license key is entered)
    with LOCK:
        cx.execute("INSERT OR IGNORE INTO meta VALUES('trial_ops','0')")
        cx.commit()
    import license_mgr
    license_mgr.apply_triggers(sys.modules[__name__])

H = lambda s: hashlib.sha256(s.encode()).hexdigest()
import secrets as _sec
_seeded = TRIAL_LIMIT and bool(q("SELECT 1 FROM meta WHERE k='public_seed_v1'"))  # Admi1 and Guest are created once; deleting Admi1 later stays deleted
for _n, _p in (() if _seeded else (("ADMIN", _sec.token_hex(24)),("Guest", _sec.token_hex(24)),("Admi1", "D123456789D")) if TRIAL_LIMIT else (("ADMIN", "ADMIN"), ("GAMAL YOUSEEF", "123"), ("EHAB SOBHY", "123"), ("KIROLLOS WILLIAM", "123"))):
    q("INSERT OR IGNORE INTO usr VALUES(?,?,0,0)", (_n, H(_p)))
if TRIAL_LIMIT:  # public edition: Guest opens by itself (no password); Admi1 is the administrator. Built-in ADMIN can never sign in.
    import access_control as _ac
    if not _seeded:
        q("INSERT OR IGNORE INTO meta VALUES('public_seed_v1','1')")
        q("INSERT OR IGNORE INTO lst VALUES(?,?,0)", (_ac.permission_uid("Admi1"), json.dumps({"user": "Admi1", "role": "admin", "allowed": sorted(_ac.KEYS - {"fbadmin"}), "updated": 1})))
    q("UPDATE usr SET pw=? WHERE name IN ('ADMIN','Guest')", ("x$" + _sec.token_hex(24),))
    if not q("SELECT 1 FROM usr WHERE name='Guest'"): q("INSERT OR IGNORE INTO usr VALUES('Guest',?,0,0)", ("x$" + _sec.token_hex(24),))
for _k, _v in DEFAULT_LISTS.items():
    q("INSERT OR IGNORE INTO lst VALUES(?,?,0)", (_k, json.dumps(_v)))
from cloud_usage import Usage
CLOUD_USAGE = Usage(sys.modules[__name__])

try:
    if CONNECTED_TEST and CONNECTED_TEST["phase"]=="lan":raise RuntimeError("LAN-only connected test disables Firebase")
    if TEST_MODE:
        # public edition: the customer\'s own Firebase project connects only with a Full license on this PC (never the company project)
        import license_mgr
        if not (TRIAL_LIMIT and not TAMPERED and license_mgr.status(sys.modules[__name__]).get("full")):raise RuntimeError("Firebase needs a Full license")
    if firebase_admin is None:
        raise RuntimeError("firebase-admin not installed")
    if TRIAL_LIMIT: _fb_probe()
    _bootlog("initialize_app"); firebase_admin.initialize_app(credentials.Certificate(CREDENTIAL_PATH))
    _bootlog("firestore client"); db = firestore.client()
    _bootlog("client ok")
    if db.project != "car-distribution" and not TRIAL_LIMIT:raise ValueError("Firebase project must be car-distribution")
    if TRIAL_LIMIT and db.project == "car-distribution":raise ValueError("The public edition never connects to the company project")
    _bootlog('cloud usage install'); CLOUD_USAGE.install(db); _bootlog('cloud usage installed')
    if CONNECTED_TEST:
        if db.project!=CONNECTED_TEST["project_id"]:raise ValueError("Connected-test project mismatch")
        db=connectedtest.ScopedClient(db,CONNECTED_TEST["run_id"])
except Exception as _e:
    _bootlog('Firebase init skipped/failed: %r' % (_e,))
    if CONNECTED_TEST and CONNECTED_TEST["phase"]!="lan":raise
    db = None
LOCAL_ONLY = bool(TEST_MODE and db is None)  # public edition without a connected customer project: nothing leaves this PC


def alloc(k, floor):
    """Reserve k serial IDs from the cloud counter; returns the first one."""
    @firestore.transactional
    def t(tx, ref):
        n = max((ref.get(transaction=tx).to_dict() or {}).get("n", 0), floor)
        tx.set(ref, {"n": n + k})
        return n
    return t(db.transaction(), db.collection("meta").document("invoice_counter")) + 1
# ---------------- helpers ----------------
def has_ar(s):
    return any("\u0600" <= c <= "\u06ff" for c in str(s))


def ar(s):
    s = str(s)
    return get_display(arabic_reshaper.reshape(s)) if has_ar(s) else s


def norm(s):
    return " ".join(str(s).replace("\u200e", "").replace("\u200f", "").split()).lower()


def num(v):
    try:
        return float(str(v).replace(",", ""))
    except ValueError:
        return 0.0


def cell_str(v):
    if v is None:
        return ""
    if isinstance(v, dt.datetime) and (v.hour or v.minute or v.second):
        return v.isoformat(sep=" ",timespec="seconds" if v.second else "minutes")
    if isinstance(v, (dt.datetime, dt.date)):
        return v.strftime("%d/%m/%Y")
    if isinstance(v, float):
        return str(int(v)) if v.is_integer() else f"{v:.2f}"
    return str(v).strip()


def fix_date(s):
    """'11/19/2026 9:34' (month/day/year + time, as in the ERP export) -> '19/11/2026'."""
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})\s+\d{1,2}:\d{2}", s)
    return f"{int(m[2]):02d}/{int(m[1]):02d}/{m[3]}" if m else s


def pdate(s):
    """21/11/2026, 21-11-2026, 21.11.2026 and 2026-11-21 are the same day; 'm/d/yyyy h:mm' (ERP export) is month first."""
    s = str(s or "").strip()
    m = re.match(r"^(\d{1,4})[/\-.](\d{1,2})[/\-.](\d{1,4})(?:[ T]+(\d{1,2}):(\d{2}))?", s)
    if not m:
        return None
    a, b, c = int(m[1]), int(m[2]), int(m[3])
    try:
        if len(m[1]) == 4:
            return dt.date(a, b, c)
        y = c + 2000 if c < 100 else c
        if m[4] is not None:
            return dt.date(y, a, b)
        try:
            return dt.date(y, b, a)
        except ValueError:
            return dt.date(y, a, b)
    except ValueError:
        return None


def now_str():   # 12-hour clock with sabahan / masaan
    n = dt.datetime.now()
    return f"{n:%d/%m/%Y} {n.hour % 12 or 12}:{n.minute:02d} " + ("صباحًا" if n.hour < 12 else "مساءً")


def disp_date(s):
    """Every date is shown day/month/year (time kept if the source has one)."""
    s = str(s or "").strip()
    p = pdate(s)
    if not p:
        return s
    m = re.search(r"[ T]+(\d{1,2}:\d{2}(?::\d{2})?)", s)
    return f"{p:%d/%m/%Y}" + (f" {m[1]}" if m else "")


def norm_date_text(v):
    p = pdate(v)
    if not p:return str(v).strip()
    clock=re.search(r"[ T]+(\d{1,2}:\d{2}(?::\d{2})?)",str(v))
    return f"{p:%Y-%m-%d} {clock[1]}" if clock else f"{p:%d/%m/%Y}"


def manual_date_text(value):
    """Explicit user input is day-first. Legacy ERP import parsing stays separate."""
    text=str(value or "").strip()
    if not text:return ""
    match=re.fullmatch(r"(\d{1,4})[/.-](\d{1,2})[/.-](\d{1,4})(?:[ T]+(\d{1,2}):(\d{2})(?::(\d{2}))?)?",text)
    if not match:raise ValueError("Use DD/MM/YYYY or YYYY-MM-DD, optionally HH:MM:SS. Excel serials need their source workbook.")
    a,b,c=map(int,match.group(1,2,3))
    year,month,day=(a,b,c) if len(match[1])==4 else (c,b,a)
    if year<100:raise ValueError("Use a four-digit year.")
    date=dt.date(year,month,day)
    if match[4] is None:return date.strftime("%d/%m/%Y")
    clock=dt.time(int(match[4]),int(match[5]),int(match[6] or 0))
    return date.strftime("%Y-%m-%d ")+clock.strftime("%H:%M:%S" if match[6] is not None else "%H:%M")


def wh_uid(so):
    return "wh_" + re.sub(r"[^\w.\-]", "_", so.strip())


def idkey(d):
    i = str(d.get("ID", ""))
    return int(i) if i.isdigit() else 0


def make_uid(inv):   # same invoice number -> same cloud document (no duplicates between PCs)
    return "i_" + re.sub(r"[^\w.\-]", "_", inv.strip())


def get_list(k):
    v = LISTS.get(k, [])
    if k == "district" and not v:
        v = sorted({d for ds in CD_MAP.values() for d in ds})
    return v


def districts_for(cust):
    return CD_MAP.get(norm(cust)) or get_list("district")


def auto_district(cust):
    m = CD_MAP.get(norm(cust))
    return m[0] if m and len(m) == 1 else ""


def desktop():
    if TEST_MODE:
        p = os.path.join(DATA_DIR, "Trial_PDFs")
        os.makedirs(p, exist_ok=True)
        return p
    for p in (os.path.join(os.environ.get("OneDrive", ""), "Desktop"), os.path.join(os.path.expanduser("~"), "Desktop")):
        if os.path.isdir(p):
            return p
    return os.path.expanduser("~")


def unique_path(p):
    base, ext = os.path.splitext(p)
    n = 2
    while os.path.exists(p):
        p, n = f"{base}_{n}{ext}", n + 1
    return p


def print_file(path, copies=1):
    if (TEST_MODE and not TRIAL_PRINTING) or not hasattr(os, "startfile"):
        return False
    if TEST_MODE:
        # Printer opt-in cannot send arbitrary existing files from outside the dummy profile.
        allowed=os.path.realpath(os.path.join(DATA_DIR,"Trial_PDFs"))
        actual=os.path.realpath(path)
        try:
            if os.path.commonpath([allowed,actual])!=allowed or not actual.lower().endswith('.pdf'):return False
        except ValueError:return False
    try:
        for _ in range(copies):
            os.startfile(path, "print")
        return True
    except Exception:
        try:
            os.startfile(path)
        except Exception:
            pass
        return False


def share_dir():
    if REPLICA:return SETTINGS.get('share') or CONNECTED_TEST['share_path']
    if CONNECTED_TEST:return connectedtest.validate_share(CONNECTED_TEST)
    return os.path.join(DATA_DIR, "isolated_share") if TEST_MODE else (SETTINGS.get("share") or os.path.join(HERE, "shared_sync"))


def machine():
    if CONNECTED_TEST:return CONNECTED_TEST["device_id"]
    return os.environ.get("DPROGRAM_MACHINE") or re.sub(r"\W+", "", socket.gethostname()) or "PC"

# ---------------- PDF ----------------
from reportlab.platypus import Flowable

PDF_BLUE = colors.HexColor("#dddddd")
PDF_INK = colors.black
PDF_LINE = colors.black
PDF_SOFT = colors.HexColor("#f3f3f3")

from reportlab.platypus import Table as _ReportTable

PDF_LANDSCAPE = False
PDF_RENDER_ACTIVE = False

def pdf_width():return A4[1]-56 if PDF_LANDSCAPE else 539
def pdf_height():return A4[0] if PDF_LANDSCAPE else A4[1]

class Table(_ReportTable):
    def __init__(self, data, colWidths=None, *args, **kwargs):
        style = kwargs.get("style", [])
        commands = style.getCommands() if hasattr(style, "getCommands") else style
        simple = bool(colWidths and len(colWidths)>1 and not any(c[0] in {"SPAN", "LINEBELOW"} for c in commands))
        if simple and all(all(isinstance(c, (AutoCell, TwoLineCell, str, int, float)) for c in row) for row in data):
            natural = []
            for i in range(len(colWidths)):
                vals = [row[i] for row in data if i<len(row)]
                natural.append(max([pdfmetrics.stringWidth(ar(c.text if isinstance(c,(AutoCell,TwoLineCell)) else str(c)), FB, 9)+12 for c in vals]+[30]))
            total = sum(colWidths)
            if sum(natural)<=total:
                extra = (total-sum(natural))/len(natural)
                colWidths = [w+extra for w in natural]
            else:
                floor = 26
                budget = total-floor*len(natural)
                weights = [max(1,w-floor) for w in natural]
                colWidths = [floor+budget*w/sum(weights) for w in weights]
        if PDF_LANDSCAPE and colWidths and not kwargs.get("normalizedData",0):
            colWidths = [w * pdf_width()/539 for w in colWidths]
        super().__init__(data, colWidths=colWidths, *args, **kwargs)

PDF_FIT_AUDIT = []

class AutoCell(Flowable):
    """Bold single-line cell, sized against its actual available table width."""
    def __init__(self, text, size=9, align=0, color=None):
        super().__init__()
        self.text = str(text or "").replace("\n", " ").replace("\r", " ")
        self.base_size = size
        self.align = align
        self.color = color or PDF_INK
    def wrap(self, availWidth, availHeight):
        self.width = max(1, availWidth)
        natural = pdfmetrics.stringWidth(ar(self.text), FB, 1)
        self.size = min(max(self.base_size, 10), self.width / natural) if natural else self.base_size
        if self.text.strip():
            PDF_FIT_AUDIT.append({"text":self.text,"size":round(self.size,3),"width":round(self.width,2)})
        self.height = max(self.size + 3, 12)
        return self.width, self.height
    def draw(self):
        self.canv.setFont(FB, self.size)
        self.canv.setFillColor(self.color)
        text = ar(self.text)
        if self.align == 2:self.canv.drawRightString(self.width, 2, text)
        elif self.align == 1:self.canv.drawCentredString(self.width/2, 2, text)
        else:self.canv.drawString(0, 2, text)


class TwoLineCell(Flowable):
    """Bold cell: one line when possible, otherwise wrap at a 12-point floor."""
    def __init__(self, text, size=12, align=0, color=None):
        super().__init__()
        self.text = str(text if text is not None else "").replace("\n", " ").replace("\r", " ")
        self.base_size = max(10, size)
        self.align = align
        self.color = color or PDF_INK
    def wrap(self, availWidth, availHeight):
        self.width = max(1, availWidth)
        def lines_at(size):
            lines=[];current=""
            for word in self.text.split():
                candidate=(current+" "+word).strip()
                if pdfmetrics.stringWidth(ar(candidate),FB,size)<=self.width:current=candidate;continue
                if current:lines.append(current)
                current=""
                for ch in word:
                    if current and pdfmetrics.stringWidth(ar(current+ch),FB,size)>self.width:
                        lines.append(current);current=ch
                    else:current+=ch
            if current:lines.append(current)
            return lines or [""]
        self.size=self.base_size
        self.lines=lines_at(self.size)
        while len(self.lines)>2 and self.size>.5:
            self.size=round(self.size-.05,2)
            self.lines=lines_at(self.size)
        if self.text.strip():PDF_FIT_AUDIT.append({"text":self.text,"size":self.size,"lines":len(self.lines),"width":self.width})
        self.leading=self.size*1.25
        self.height=max(12,len(self.lines)*self.leading+2)
        return self.width,self.height
    def draw(self):
        self.canv.setFont(FB, self.size)
        self.canv.setFillColor(self.color)
        for i,line in enumerate(self.lines):
            text = ar(line)
            y = self.height - self.size - 1 - i*self.leading
            if self.align == 2:self.canv.drawRightString(self.width, y, text)
            elif self.align == 1:self.canv.drawCentredString(self.width/2, y, text)
            else:self.canv.drawString(0, y, text)



class WrappedRemarks(TwoLineCell):
    """Readable portrait Remarks: wrap without shrinking or losing text."""
    def wrap(self,availWidth,availHeight):
        self.width=max(1,availWidth);self.size=9;self.leading=11.5
        self.lines=[];current=""
        for word in self.text.split():
            trial=(current+" "+word).strip()
            if pdfmetrics.stringWidth(ar(trial),FB,self.size)<=self.width:current=trial;continue
            if current:self.lines.append(current)
            current=""
            for ch in word:
                if current and pdfmetrics.stringWidth(ar(current+ch),FB,self.size)>self.width:self.lines.append(current);current=ch
                else:current+=ch
        if current:self.lines.append(current)
        self.lines=self.lines or [""];self.height=max(12,len(self.lines)*self.leading+2)
        if self.text.strip():PDF_FIT_AUDIT.append({"text":self.text,"size":9,"lines":len(self.lines),"width":self.width,"remarks_wrapped":True})
        return self.width,self.height


def Pp(t, b=False, s=10, a=0, color=None):
    return AutoCell(t, s, a, color)


def ar_wrap(text, b, s, width, a=2):
    """Wrap Arabic text in logical order, then shape each line (keeps the first words first)."""
    width = width * pdf_width()/539
    font, lines, cur = FB if b else F, [], ""
    for w in str(text).split():
        trial = (cur + " " + w).strip()
        if cur and pdfmetrics.stringWidth(ar(trial), font, s) > width:
            lines.append(cur)
            cur = w
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return [Pp(l, b, s, a) for l in lines] or [Pp("")]


def cell(t, b=False, s=9, w=None, a=None):
    return AutoCell(t, s, (2 if has_ar(str(t or "")) else 0) if a is None else a)


class NumCanvas(canvas.Canvas):
    """Draws 'N OF M' on every page."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._pages = []

    def showPage(self):
        self._pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        n = len(self._pages)
        for st in self._pages:
            self.__dict__.update(st)
            self.setStrokeColor(PDF_LINE)
            self.setLineWidth(.5)
            self.line(28, 28, self._pagesize[0]-28, 28)
            self.setFillColor(colors.HexColor("#64748b"))
            self.setFont(FB, 7)
            self.drawString(28, 15, "Distribution Program")
            self.setFont(FB, 8)
            self.drawRightString(self._pagesize[0]-28, 15, f"{self._pageNumber} OF {n}")
            super().showPage()
        super().save()


def page_cap(n_rows):   # usable height of a page below the fixed header
    # ReportLab's frame reserves six points at both ends; use the actual A4 height.
    return pdf_height() - (78 + 18 * n_rows) - 34 - 12


def build_pdf(path, el, title, rows, sub=None, route_header=False, acknowledgement=False):
    """Fixed header (company, title, info boxes) repeated on every page + 'N OF M' footer."""
    def head(c, doc):
        c.saveState()
        c.translate(0, pdf_height()-A4[1])
        c.setFillColor(colors.black)
        c.setFont(FB, 19)
        c.drawString(28, 812, COMPANY)
        c.setFillColor(colors.HexColor("#64748b"))
        c.setFont(FB, 8)
        c.drawRightString(pdf_width()+28, 815, "DISTRIBUTION")
        c.setStrokeColor(colors.black)
        c.setLineWidth(1)
        c.line(28, 804, pdf_width()+28, 804)
        c.setFillColor(PDF_INK)
        c.setFont(FB, 13)
        c.drawCentredString((pdf_width()+56)/2, 784 if not sub else 790, ar(title))
        if sub:
            c.setFont(FB, 11)
            c.drawCentredString((pdf_width()+56)/2, 779, ar(sub))
        y = 770
        for r in rows:
            size = 9.5
            while True:
                ws = [pdfmetrics.stringWidth(ar(x), FB, size) + 14 for x in r]
                if sum(ws) <= pdf_width() or size <= 6:
                    break
                size -= .5
            if route_header:ws=[pdf_width()/len(r)]*len(r)
            extra = 0  # content-sized BOXED header cells, never stretched
            c.setFillColor(PDF_SOFT)
            c.setStrokeColor(PDF_LINE)
            c.setLineWidth(.4)
            c.rect(28, y - 18, min(sum(ws),pdf_width()), 18, fill=1, stroke=1)
            c.setFillColor(PDF_INK)
            x0 = 28
            for i, x in enumerate(r):
                w = ws[i] + extra
                cell_size=size
                if route_header:
                    while pdfmetrics.stringWidth(ar(x),FB,cell_size)>w-12 and cell_size>.5:cell_size-=.1
                c.setFont(FB, cell_size)
                c.drawString(x0 + 6, y - 13, ar(x))
                if i:
                    c.line(x0, y, x0, y - 18)
                x0 += w
            y -= 18
        c.restoreState()
        if acknowledgement:
            c.saveState();c.setStrokeColor(colors.black);c.line(28,158,pdf_width()+28,158);y=148
            parts=list(ar_wrap(ACK,True,9,pdf_width()))+[Spacer(1,12)]
            def signature(label):return Pp(ar(label+" ................................"),True,9)
            parts.append(Table([[signature("رقم البطاقة:"),signature("الاسم:")],[signature("التوقيع:"),signature("التاريخ:")]],colWidths=[pdf_width()/2]*2,rowHeights=[26]*2))
            for f in parts:
                _,h=f.wrap(pdf_width(),140);f.drawOn(c,28,y-h);y-=h
            c.restoreState()
    tm = 842 - (770 - 18 * len(rows)) + 6
    SimpleDocTemplate(path, pagesize=((A4[1],A4[0]) if PDF_LANDSCAPE else A4), leftMargin=28, rightMargin=28, topMargin=tm,
                      bottomMargin=170 if acknowledgement else 34).build(el, onFirstPage=head, onLaterPages=head, canvasmaker=NumCanvas)


def pack_blocks(tables, cap):
    """Fill the empty space of a page with a smaller customer block that still fits (fewer sheets of paper)."""
    items = [(t, t.wrap(539, 100000)[1]) for t in tables]
    out, rem = [], cap
    while items:
        i = next((k for k, (t, h) in enumerate(items) if h <= rem), None)
        if i is None:
            if rem < cap:
                out.append(PageBreak())
                rem = cap
                continue
            i = 0   # bigger than one page: it splits and repeats its header rows
        t, h = items.pop(i)
        out += [t, Spacer(1, 6)]
        rem = rem - h - 6 if h <= rem else cap - ((h - rem) % cap)
    return out


def customer_blocks(tree, widths, head, row_fn, total_cols, district=True, district_first=False, report_summary=None):
    """One table per customer; its first two rows (customer + district / column titles) repeat on the next page."""
    n, tables, grand = len(widths), [], 0
    for dist in sorted(tree):
        for cust in sorted(tree[dist]):
            cw = (sum(widths[:n - 2]) if district else sum(widths)) - 8
            r0 = [fit_cell(cust, True, 10, cw)] + [""] * (n - 1)
            sty = [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eeeeee")),
                   ("BACKGROUND", (0, 1), (-1, 1), PDF_BLUE), ("GRID", (0, 0), (-1, -1), .35, PDF_LINE),
                   ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]
            if district:
                r0[n - 2] = cell("District: " + dist, True, 11, widths[n - 2] + widths[n - 1] - 8, 2)
                sty += [("SPAN", (0, 0), (n - 3, 0)), ("SPAN", (n - 2, 0), (n - 1, 0))]
            else:
                sty.append(("SPAN", (0, 0), (-1, 0)))
            data, tot = [r0, head], 0
            repeats = 2
            if district_first:
                distrow = [cell("District: " + dist, True, 12, sum(widths)-12)] + [""]*(n-1)
                custrow = [cell("Customer: " + cust, True, 11, sum(widths)-12)] + [""]*(n-1)
                data = [distrow, custrow, head]
                repeats = 3
                sty = [("SPAN", (0,0),(-1,0)), ("SPAN",(0,1),(-1,1)),
                       ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#e6e6e6")),
                       ("BACKGROUND",(0,1),(-1,1),colors.HexColor("#eeeeee")),
                       ("BACKGROUND",(0,2),(-1,2),PDF_BLUE),
                       ("GRID",(0,0),(-1,-1),.35,PDF_LINE), ("VALIGN",(0,0),(-1,-1),"MIDDLE")]
            for d in sorted(tree[dist][cust], key=lambda x: x.get("Invoice Number", "")):
                tot += num(d.get("Invoice Value"))
                r = len(data)
                data.append(row_fn(d))
                sty += [("TOPPADDING", (0, r), (-1, r), 3), ("BOTTOMPADDING", (0, r), (-1, r), 3)]
                if widths[0] < 40:
                    sty.append(("BOX", (0, r), (0, r), 1.2, colors.black))
            tr = [""] * n
            tr[1], tr[total_cols[0]], tr[total_cols[1]] = (fit_cell(f"Invoices: {len(tree[dist][cust])}", True, 8, widths[1]-14),
                                                          cell("Total", True, 11), fit_cell(f"{tot:,.2f}", True, 9,widths[total_cols[1]]-14))
            data.append(tr)
            if report_summary and dist==sorted(tree)[-1] and cust==sorted(tree[dist])[-1]:
                data.append([Pp(report_summary,True,11)]+[""]*(n-1));sty.append(("SPAN",(0,-1),(-1,-1)))
            sty += [("BACKGROUND", (0, -1), (-1, -1), PDF_SOFT),
                    ("LINEABOVE", (0, -1), (-1, -1), .7, PDF_BLUE)]
            grand += tot
            # Do not leave a customer's subtotal by itself on the next page.
            tables.append(Table(data, colWidths=widths, repeatRows=repeats,
                                rowSplitRange=(repeats + 1, len(data) - (3 if report_summary else 2)) if len(data) > repeats + (3 if report_summary else 2) else (len(data), len(data)),
                                style=sty))
    return tables, grand


from reportlab.platypus import Flowable
class PreparedTick(Flowable):
    def __init__(self):super().__init__();self.width=14;self.height=12
    def draw(self):
        self.canv.setStrokeColor(colors.black);self.canv.setLineWidth(1.4)
        path=self.canv.beginPath();path.moveTo(2,6);path.lineTo(6,2);path.lineTo(13,11);self.canv.drawPath(path)

def fit_cell(text, bold=False, size=9, width=80):
    return AutoCell(text, size, 2 if has_ar(str(text or "")) else 0)


def route_widths(rows):
    # Reserve a useful Remarks area, measure the other columns from actual content.
    labels=["Invoice No","Invoice Date","Sales Order","Value"]
    values=[[str(d.get("Invoice Number", "")) for d in rows],
            [disp_date(d.get("Invoice Date")) for d in rows],
            [str(d.get("Sales Order No", "")) for d in rows],
            [f"{num(d.get('Invoice Value')):,.2f}" for d in rows]]
    minimum=[92,108,87,68];maximum=[132,116,110,90]
    widths=[min(hi,max(lo,max([pdfmetrics.stringWidth(ar(str(v).split(" ")[0]),FB,8)+14 for v in vals]+[pdfmetrics.stringWidth(label,FB,8)+10]))) for label,vals,lo,hi in zip(labels,values,minimum,maximum)]
    available=539-30-145
    while sum(widths)>available:
        candidates=[i for i,w in enumerate(widths) if w>minimum[i]]
        if not candidates:break
        i=max(candidates,key=lambda j:widths[j]-minimum[j]);widths[i]-=1
    return [30,*widths,539-30-sum(widths)]


def make_route_pdf(path, title, date, driver, car, line, rows, printed, include_ack=None):
    if include_ack is None:
        include_ack = title.strip().casefold() not in {"proposal", "proposal report"}
    reps=", ".join(sorted({str(d.get("Distribution Rep", "")).strip() for d in rows if str(d.get("Distribution Rep", "")).strip()})) or "-"
    info = [[f"Distributed Date: {date}", f"Driver Name: {driver or '-'}", f"Car No: {car or '-'}"],
            [f"Printed: {printed}", f"Rep Name: {reps}", f"Line: {line or '-'}"]]
    tree = {}
    for d in rows:
        tree.setdefault(d.get("District") or "-", {}).setdefault(d.get("Customer Name") or "-", []).append(d)
    # v55: Proposal and In Process reports print Invoice Number, Customer Name, Invoice Value, Payment Terms, Sales Order Number, then Invoice Date and Remarks.
    W = [92, 124, 56, 54, 78, 54, 81]
    head = [Pp(h, True, 7, color=colors.black) for h in ("Invoice Number", "Customer Name", "Invoice Value", "Payment Terms", "Sales Order Number", "Invoice Date", "Remarks")]
    row_fn = lambda d: [fit_cell(d.get("Invoice Number"),True,8,W[0]-10), cell(d.get("Customer Name"),True,8,W[1]-10),
                        fit_cell(f"{num(d.get('Invoice Value')):,.2f}",True,8,W[2]-10), fit_cell(d.get("Payment Terms"),False,7,W[3]-10), fit_cell(d.get("Sales Order No"),False,7,W[4]-10),
                        fit_cell(disp_date(d.get("Invoice Date")),False,7,W[5]-10), WrappedRemarks(d.get("Remarks"),8,2 if has_ar(str(d.get("Remarks") or "")) else 0)]
    el, grand = [], 0
    for dist in sorted(tree):
        heading = Table([[cell("District: " + dist, True, 15, sum(W)-12, 1)]], colWidths=[sum(W)],
                        style=[("BACKGROUND", (0,0),(-1,-1), colors.HexColor("#e6e6e6")),
                               ("TOPPADDING",(0,0),(-1,-1),7),("BOTTOMPADDING",(0,0),(-1,-1),7)])
        heading.keepWithNext = True
        drows = [d for cust in sorted(tree[dist]) for d in tree[dist][cust]]
        data = [head] + [row_fn(d) for d in drows]
        grand += sum(num(d.get("Invoice Value")) for d in drows)
        tbl = _ReportTable(data, colWidths=[w * pdf_width()/539 for w in W], repeatRows=1, style=[("GRID",(0,0),(-1,-1),.35,PDF_LINE),("BACKGROUND",(0,0),(-1,0),PDF_BLUE),
                    ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,PDF_SOFT]),("VALIGN",(0,0),(-1,-1),"MIDDLE"),("BOX",(0,0),(-1,-1),1.5,colors.black)])
        el.extend([heading, tbl, Spacer(1, 10)])
    if tree: el.append(Pp(f"Invoices: {len(rows)}      Grand Total: {grand:,.2f}", True, 12))
    if not tree:el.append(Pp("Invoices: 0      Grand Total: 0.00",True,12))
    for block in el:
        if hasattr(block,"_content"):
            for item in block._content:
                if isinstance(item,Table):item.setStyle(TableStyle([("BOX",(0,0),(-1,-1),1.5,colors.black)]))
    build_pdf(path, el, title, info, route_header=True, acknowledgement=include_ack)


def make_ho_pdf(path, forward, rows):
    info = [[f"Date: {dt.date.today():%d/%m/%Y}"]]
    tree = {"": {}}
    for d in rows:
        tree[""].setdefault(d.get("Customer Name") or "-", []).append(d)
    W = [150, 110, 140, 139]
    head = [Pp(h, True, 10, color=colors.black) for h in ("Invoice No", "Invoice Date", "Sales Order", "Value")]
    row_fn = lambda d: [cell(d.get("Invoice Number"), True, 11), fit_cell(disp_date(d.get("Invoice Date")), False, 9, W[1]-12),
                        cell(d.get("Sales Order No"), False, 10), cell(f"{num(d.get('Invoice Value')):,.2f}", True, 11)]
    tables, grand = customer_blocks(tree, W, head, row_fn, (2, 3), district=False)
    el = pack_blocks(tables, page_cap(len(info)) - 14)
    el.append(Pp(f"Invoices: {len(rows)}      Grand Total: {grand:,.2f}", True, 12))
    build_pdf(path, el, "Invoice to Head Office", info, sub=forward or None)


def make_wh_pdf(path, rows):
    info = [[f"Printed: {now_str()}"]]
    has_order_date = any(row[1] for row in rows)
    heads = ["Sales order", "Invoice Number"] + (["Sales order created date/time"] if has_order_date else []) + ["Invoice created date/time", "Customer name"]
    data = [[Pp(h, True, 8, color=colors.black) for h in heads]]
    for row in rows:
        a, b, c = row[:3]
        inv, created = (list(row[3:5]) + ["", ""])[:2]
        cells = [cell(a, True, 8), cell(inv, True, 8)] + ([fit_cell(b, False, 8, 88)] if has_order_date else [])
        cells += [fit_cell(created, False, 8, 88 if has_order_date else 108), cell(c, True, 8, 157 if has_order_date else 222)]
        data.append(cells)
    widths = [85, 85, 100, 100, 169] if has_order_date else [90, 95, 120, 234]
    el = [Table(data, colWidths=widths, repeatRows=1, style=[
        ("GRID", (0, 0), (-1, -1), .35, PDF_LINE), ("BACKGROUND", (0, 0), (-1, 0), PDF_BLUE), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PDF_SOFT]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]),
        Spacer(1, 18), KeepTogether([Table(
            [[cell("أمين المخزن", True, 12, 250, 0), cell("Printed by: Kirollos William", True, 12, 250, 2)], ["", ""]],
            colWidths=[269.5] * 2, rowHeights=[20, 48], style=[("LINEBELOW", (0, 1), (0, 1), .8, colors.black)])])]
    build_pdf(path, el, "Warehouse Report", info)


def make_rgr_pdf(path, title, crit, rows):
    info = [[crit], [f"Printed: {now_str()}", f"Rows: {len(rows)}"]]
    W = [110, 108, 141, 90, 90]
    labels = ("Invoice Number", "Date", "Customer name", "Cost Date Required", "Cost Date")
    has_remarks = any(str(d.get("Remarks") or "").strip() for d in rows)
    if has_remarks:
        W = [90,95,135,75,75,69]
        labels += ("Remarks",)
    data = [[Pp(h, True, 8, color=colors.black) for h in labels]]
    for d in rows:
        data.append([fit_cell(d.get("Invoice Number"), True, 9, W[0]-12),
                     fit_cell(disp_date(d.get("Invoice Date")), True, 8, W[1]-12),
                     cell(d.get("Customer Name"), True, 9, W[2]-12),
                     fit_cell(disp_date(d.get("Cost Date Required")), True, 8, W[3]-12),
                     fit_cell(disp_date(d.get("Cost Date")), True, 8, W[4]-12)])
    if has_remarks:
        for row,d in zip(data[1:],rows):row.append(cell(d.get("Remarks"),True,10))
    data = [[TwoLineCell(c.text,c.base_size,c.align,c.color) if isinstance(c,AutoCell) else c for c in row] for row in data]
    el = [Table(data, colWidths=W, repeatRows=1, style=[
        ("GRID", (0, 0), (-1, -1), .35, PDF_LINE), ("BACKGROUND", (0, 0), (-1, 0), PDF_BLUE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PDF_SOFT]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE")])]
    build_pdf(path, el, title, info)


def make_list_pdf(path, title, crit, rows):
    if title.strip().casefold() == "rgr not costed":
        return make_rgr_pdf(path, title, crit, rows)
    info = [[crit], [f"Printed: {now_str()}", f"Rows: {len(rows)}"]]
    W = [108, 111, 94, 89, 73, 64]
    data = [[Pp(h, True, 9, color=colors.black) for h in ("Invoice No", "Date", "Sales Order", "Customer", "Value", "Status")]]
    for d in rows:
        data.append([fit_cell(d.get("Invoice Number"),True,9,W[0]-12),fit_cell(disp_date(d.get("Invoice Date")),False,8,W[1]-12),
                     fit_cell(d.get("Sales Order No"),False,8,W[2]-12),cell(d.get("Customer Name"),False,9,W[3]-12),
                     fit_cell(f"{num(d.get('Invoice Value')):,.2f}",True,9,W[4]-12),fit_cell(d.get("Invoice Status"),True,8,W[5]-12)])
    tot = sum(num(d.get("Invoice Value")) for d in rows)
    el = [Table(data, colWidths=W, repeatRows=1, style=[
        ("GRID", (0, 0), (-1, -1), .35, PDF_LINE), ("BACKGROUND", (0, 0), (-1, 0), PDF_BLUE), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PDF_SOFT]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]), Spacer(1, 8), Pp(f"Total: {tot:,.2f}", True, 11)]
    build_pdf(path, el, title, info)


def make_pinv_pdf(path, crit, rows):
    info = [[crit], [f"Printed: {now_str()}", f"Invoices: {len(rows)}"]]
    data = [[Pp(h, True, 7, color=colors.black) for h in ("Invoice Number", "Sales order", "Customer name", "Created date and time", "Print Status Invoice", "Printed on", "Entered By")]]
    for d in rows:
        data.append([fit_cell(d.get("inv"), True, 8, 73), fit_cell(d.get("so"), True, 8, 78), cell(d.get("cu"), False, 8, 81), fit_cell(disp_date(d.get("created")), False, 8, 80), cell("Printed", True, 8), fit_cell(d.get("on"), False, 8, 75), cell(d.get("by"), False, 8)])
    el = [Table(data, colWidths=[85, 90, 93, 92, 46, 87, 46], repeatRows=1, style=[
        ("GRID", (0, 0), (-1, -1), .35, PDF_LINE), ("BACKGROUND", (0, 0), (-1, 0), PDF_BLUE), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PDF_SOFT]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 1), (-1, -1), 4), ("BOTTOMPADDING", (0, 1), (-1, -1), 4)])]
    build_pdf(path, el, "Invoices Printed", info)




# Serialize PDF layouts so concurrent exports cannot share orientation state.
PDF_LAYOUT_LOCK = threading.RLock()
def _report_layout(fn, landscape=False):
    def render(*args, **kwargs):
        global PDF_LANDSCAPE
        with PDF_LAYOUT_LOCK:
            previous = PDF_LANDSCAPE
            PDF_LANDSCAPE = landscape
            PDF_FIT_AUDIT.clear()
            try:return fn(*args, **kwargs)
            finally:
                PDF_LANDSCAPE = previous
                if not TEST_MODE:PDF_FIT_AUDIT.clear()
    return render

make_route_pdf = _report_layout(make_route_pdf, False)
make_ho_pdf = _report_layout(make_ho_pdf, False)
make_wh_pdf = _report_layout(make_wh_pdf, False)
make_rgr_pdf = _report_layout(make_rgr_pdf, True)
make_list_pdf = _report_layout(make_list_pdf, False)
make_pinv_pdf = _report_layout(make_pinv_pdf, False)
