#!/usr/bin/env python3
"""Distribution Program - Browser edition server.
Serves the single-page UI on 127.0.0.1 and exposes the original program logic
through a small JSON API. Data stays local-first (SQLite), then the LAN shared
folder, then optional Firebase - exactly like the desktop program.
Designed & developed by Eng. Kirollos William (c) 2026
"""
import collections, sys, os, re, io, json, time, threading, base64, secrets, tempfile, uuid, datetime as dt
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Public edition boot trace (written before anything heavy is imported, so a crash during import is still recorded).
_BOOT = None
try:
    if os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), "public_edition.flag")):
        _d = os.path.join(os.path.expanduser("~"), "InvoiceApp_Isolated_Trial"); os.makedirs(_d, exist_ok=True)
        _BOOT = os.path.join(_d, "boot.log")
        if os.path.exists(_BOOT) and os.path.getsize(_BOOT) > 200000: os.replace(_BOOT, _BOOT + ".old")
        _bf = open(_BOOT, "a", encoding="utf-8", buffering=1)
        _bf.write("%s pid=%s BOOT python=%s key_present=%s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), os.getpid(), sys.executable,
                  os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), "serviceAccountKey.json"))))
        import faulthandler; faulthandler.enable(_bf)   # native crashes (for example in the Firebase/gRPC libraries) leave a traceback here
        sys.stderr = sys.stderr or _bf; sys.stdout = sys.stdout or _bf
except Exception:
    _BOOT = None
def _boot(msg):
    try:
        if _BOOT:
            with open(_BOOT, "a", encoding="utf-8") as f: f.write("%s pid=%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), os.getpid(), msg))
    except Exception: pass
_boot("importing core")
if _BOOT:
    try:
        faulthandler.dump_traceback_later(20, repeat=True, file=_bf)   # if the import is stuck, boot.log shows exactly where
    except Exception: pass
    def _precompile():
        # compile the Firebase libraries once (no .pyc ships with the package) so later starts load them quickly
        try:
            import compileall, site
            _t0 = time.time(); _base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "python", "Lib", "site-packages")
            for _n in ("firebase_admin", "google", "grpc", "proto", "grpc_status", "cachecontrol", "msgpack", "h2", "hpack", "hyperframe", "httpx", "httpcore", "anyio", "h11", "jwt", "cryptography", "pyasn1", "pyasn1_modules"):
                _p = os.path.join(_base, _n)
                if os.path.isdir(_p): compileall.compile_dir(_p, quiet=2, workers=1)
            _boot("precompile done in %.1fs" % (time.time() - _t0))
        except Exception as e: _boot("precompile error %r" % (e,))
    threading.Thread(target=_precompile, daemon=True).start()
try:
    import core
except BaseException:
    import traceback as _tb2
    _boot("FATAL while importing core:\n" + _tb2.format_exc())
    raise
try: faulthandler.cancel_dump_traceback_later()
except Exception: pass
_boot("core imported; firebase_connected=%s" % (core.db is not None))
import prefix_ids
import trial_autologin
import access_control
from core import (SETTINGS, save_settings, q, meta, setmeta, db_put, LISTS, CD_MAP,
                  STATUSES, BASE, COLS, LOCKED, EDITABLE, RGR_COLS, LIST_FIELDS, DATE_COLS,
                  REP_COLS, EXEMPT, MAX_ROWS, VERSION, CREDIT, SIGNATURE, COMPANY, LOGIN_TITLE,
                  H, norm, num, pdate, disp_date, norm_date_text, idkey, make_uid, wh_uid,
                  get_list, districts_for, auto_district, desktop, unique_path, print_file,
                  share_dir, machine, cell_str, now_str, db)

HERE = os.path.dirname(os.path.abspath(__file__))
EXIT_FLOW=None
lan_completed=0
cloud_completed=0

# ---------------- shared application state (was: App attributes) ----------------
docs, wh_rows, pinv_rows = {}, {}, {}
ui_dirty = False
data_version = 0          # bumped whenever local data changes; the browser polls it
st_lan, st_cloud = "Network: checking...", "Cloud: waiting"
cloud_now = False
cloud_pull_requested = False
cloud_retry_after = 0
cloud_failures = 0
sync_now, cloud_ev = threading.Event(), threading.Event()
CLOUD_REQUEST_LOCK = threading.Lock()
STATE_LOCK = threading.RLock()
PDF_VIEWS = {}          # random-token -> generated warehouse PDF in this running instance
AUTO_SESSION_EXPIRY = {}
SESSIONS = {}             # token -> user name (per running instance, memory only)


def bump():
    global data_version
    with STATE_LOCK:
        data_version += 1


def reload_data():
    global docs, wh_rows, pinv_rows
    d, wh, pi = {}, {}, {}
    for u, j in q("SELECT uid,data FROM inv"):
        x = json.loads(j)
        if x.get("_deleted") is True:
            continue
        k = x.get("_kind")
        if k in {"review_plan","user_permissions"}:continue
        (wh if k == "wh" else pi if k == "pi" else d)[u] = x
    docs, wh_rows, pinv_rows = d, wh, pi
    LISTS.clear()
    LISTS.update({n: json.loads(i) for n, i in q("SELECT name,items FROM lst") if not n.startswith("user_access_v54_")})
    CD_MAP.clear()
    for line in LISTS.get("customer_district", []):
        if "\t" in line:
            c, dd = line.split("\t", 1)
            lst = CD_MAP.setdefault(norm(c), [])
            if dd.strip() and dd.strip() not in lst:
                lst.append(dd.strip())


def migrate_wh():
    old = json.loads(meta("wh_rows", "[]"))
    if not old:
        return
    now = time.time()
    items = [(wh_uid(r["so"]), {"_kind": "wh", "so": r["so"], "dt": r["dt"], "cu": r["cu"], "p": r.get("p", 0),
                                "on": "", "by": "", "seq": now * 1000 + i, "updated": now}) for i, r in enumerate(old)]
    db_put(items, 1, 1)
    setmeta("wh_rows", "[]")
    reload_data()


ACTOR = threading.local()


def save_doc(uid, d):
    d["updated"] = time.time()
    if not d.get("_kind"):
        try: d["_rev"] = int(d.get("_rev", 0) or 0) + 1   # save counter, lets a receiver know a new invoice arrived already edited
        except (TypeError, ValueError): d["_rev"] = 1
    if not d.get("_kind") and getattr(ACTOR, "user", "") and d.get("Invoice Status") == "Delivered":
        _old = docs.get(uid)
        if _old is not None and _old.get("Invoice Status") != "Delivered" and not str(d.get("Delivered By", "")).strip():
            d["Delivered By"] = ACTOR.user
            d["Delivered At"] = time.strftime("%d/%m/%Y %H:%M:%S")
    if not d.get("_kind") and d.get("Invoice Status") == "inprocess":
        _old2 = docs.get(uid)
        if _old2 is not None and _old2.get("Invoice Status") == "Delivered":
            d["Delivered By"] = ""; d["Delivered At"] = ""   # set back to In Process: the delivery mark is cleared
    if not d.get("_kind") and getattr(ACTOR, "user", ""):
        d["Last Updated By"] = ACTOR.user
    if core.TRIAL_LIMIT and not d.get("_kind"):  # trial: a real edit of an existing invoice counts as one operation
        _prev = docs.get(uid)
        if _prev is not None:
            _skip = {"updated", "_rev", "Last Updated By"}
            if {k: v for k, v in _prev.items() if k not in _skip} != {k: v for k, v in d.items() if k not in _skip}:
                core.trial_bump(1)
    db_put([(uid, d)], 1, 1)
    k = d.get("_kind")
    if k not in {"review_plan","user_permissions"}:(wh_rows if k == "wh" else pinv_rows if k == "pi" else docs)[uid] = d
    bump()
    sync_now.set()
    request_cloud()


def notify_list(user):
    j = CLOUD_SYNC.journal()
    seen = set(json.loads(meta("notify_seen_" + user, "[]")))
    out = [dict(e, seen=e["id"] in seen) for e in j[-300:]]
    return {"ok": True, "events": out[::-1], "unseen": sum(1 for e in out if not e["seen"])}


def notify_seen(user, ids):
    seen = set(json.loads(meta("notify_seen_" + user, "[]"))) | {int(i) for i in ids}
    keep = {e["id"] for e in CLOUD_SYNC.journal()[-300:]}
    setmeta("notify_seen_" + user, json.dumps(sorted(seen & keep)))
    return notify_list(user)


def delete_uids(uids, user=""):
    now = time.time()
    with core.LOCK:
        for u in uids:
            if user: setmeta("delby_" + u, user)
            core.cx.execute("DELETE FROM inv WHERE uid=?", (u,))
            core.cx.execute("INSERT INTO del VALUES('invoices',?)", (u,))
            core.cx.execute("INSERT OR REPLACE INTO dellan VALUES(?,?,1)", (u, now))
        core.cx.commit()
    for u in uids:
        docs.pop(u, None)
        wh_rows.pop(u, None)
        pinv_rows.pop(u, None)
    if core.TRIAL_LIMIT:
        import license_mgr; license_mgr.status(core, True)
    bump()
    sync_now.set(); request_cloud()


def new_ids(k, extra=0):
    # Legacy helper retained for offline compatibility; never a connected/offline-cloud fallback.
    if not core.LOCAL_ONLY:
        raise prefix_ids.NotReady("Legacy numeric allocation disabled. Initial sync and shared prefix reservation are required.")
    with core.LOCK:
        used = {idkey(d) for d in docs.values()}
        return max(list(used) + [extra, 0]) + 1


def allocated_ids(user, uids):
    result=[]
    # Firestore transactions cap their writes; 100 invoices require <=201 writes.
    for start in range(0,len(uids),100):result.extend(ID_SERVICE.allocate(user,uids[start:start+100]))
    return result


def new_invoice_uid(number, reserved=()):
    # Number is editable. Once created, synchronization identity never changes.
    if any(str(d.get("Invoice Number", "")).strip().casefold() == str(number).strip().casefold() for d in docs.values()):
        raise ValueError("This invoice number already exists. Nothing was replaced.")
    candidate = make_uid(number)
    occupied = set(docs) | set(reserved)
    if candidate not in occupied:
        return candidate  # db_put still refuses a retained tombstone for this ID
    while True:
        uid = candidate + "_" + uuid.uuid4().hex[:12]
        if uid not in occupied and not q("SELECT 1 FROM dellan WHERE uid=?", (uid,)):
            return uid


def apply_invoice_changes(uid, changes, reason=""):
    with core.LOCK:
        if uid not in docs:
            return {"ok": False, "msg": "Row no longer exists."}
        if any(name not in EDITABLE for name in changes):
            return {"ok": False, "msg": "A system-set audit field is not editable."}
        d = dict(docs[uid])
        edits = {name: str(value).strip() for name, value in changes.items()}
        if "Invoice Status" in edits and edits["Invoice Status"] not in STATUSES:
            return {"ok": False, "msg": "Choose Invoice Status from the existing status list. Nothing was changed."}
        for name in DATE_COLS:
            if edits.get(name):
                try: edits[name] = core.manual_date_text(edits[name])
                except ValueError:
                    return {"ok":False,"field":name,"msg":name+": enter a valid DD/MM/YYYY date (optional HH:MM:SS), or clear it. Nothing was changed."}
        number = edits.get("Invoice Number", str(d.get("Invoice Number", ""))).strip()
        identity = edits.get("ID", str(d.get("ID", ""))).strip()
        if not number:
            return {"ok": False, "msg": "Invoice Number cannot be empty."}
        try:
            prefix, sequence = prefix_ids.parse(identity)
            identity = prefix + str(sequence)
        except ValueError as error:return {"ok":False,"msg":str(error)}
        for other_uid, other in docs.items():
            if other_uid == uid: continue
            if str(other.get("Invoice Number", "")).strip().casefold() == number.casefold():
                return {"ok": False, "msg": "This invoice number already exists. Nothing was changed."}
            if str(other.get("ID", "")) == identity:
                return {"ok": False, "msg": "This ID already exists. Nothing was changed."}
        if edits.get("Invoice Status") == "Cancelled" and d.get("Invoice Status") != "Cancelled" and not reason.strip():
            return {"ok": False, "need_reason": True}
        for name in DATE_COLS:
            if name in edits and edits[name]!=d.get(name,"") and re.fullmatch(r"[+-]?\d+(?:\.\d+)?",str(d.get(name,""))):
                history=list(d.get("_date_raw_history",[]))
                history.append({"field":name,"raw":d[name],"replaced_at":time.time()})
                d["_date_raw_history"]=history
        if identity != str(d.get("ID", "")):
            try:ID_SERVICE.claim(identity,uid)
            except Exception as error:return {"ok":False,"msg":str(error)}
        d.update(edits)
        d["Invoice Number"], d["ID"] = number, identity
        if edits.get("Invoice Status") == "Cancelled" and docs[uid].get("Invoice Status") != "Cancelled":
            with_reason(d, reason.strip())
        save_doc(uid, d)
        return {"ok": True, "msg": "Invoice saved. Internal sync identity unchanged."}


def with_reason(d, reason):
    old = d.get("Remarks", "").strip()
    d["Remarks"] = f"{old} - {reason}" if old else reason


def set_field(uid, name, value, reason=""):
    return apply_invoice_changes(uid, {name: value}, reason)


# ---------------- cloud + LAN sync (background threads) ----------------
LAN_CHECK_SECONDS = 5

def preserve_lan(kind, uid, data):
    raw = json.dumps(data, ensure_ascii=False, sort_keys=True)
    if not q("SELECT 1 FROM sync_conflicts WHERE kind=? AND key=? AND data=? LIMIT 1", (kind, uid, raw)):
        q("INSERT INTO sync_conflicts(kind,key,data,recorded) VALUES(?,?,?,?)", (kind, uid, raw, time.time()))

def lan_export():
    rows = q("SELECT uid,data,updated FROM inv WHERE lan=1")
    dels = q("SELECT uid,ts FROM dellan WHERE lan=1")
    if not rows and not dels:
        return
    d = os.path.join(share_dir(), "backup")
    os.makedirs(d, exist_ok=True)
    parts = [rows[i:i + 2000] for i in range(0, len(rows), 2000)] or [[]]
    for k, part in enumerate(parts):
        fn = os.path.join(d, f"backup_{machine()}_{time.strftime('%Y%m%d_%H%M%S')}_{time.time_ns() % 10**9:09d}_{k}.json")  # unique per export: two cycles in the same second must never overwrite each other's journal file
        with open(fn + ".tmp", "w", encoding="utf-8") as f:
            json.dump({"connected_test_run":core.CONNECTED_TEST["run_id"] if core.CONNECTED_TEST else None,"from": machine(), "records": [[u, json.loads(x)] for u, x, _ in part],
                       "deleted": [[u, ts] for u, ts in dels] if k == 0 else []}, f, ensure_ascii=False)
        os.replace(fn + ".tmp", fn)
        with core.LOCK:
            core.cx.executemany("UPDATE inv SET lan=0 WHERE uid=? AND updated=?", [(u, up) for u, _, up in part])
            if k == 0:
                core.cx.executemany("UPDATE dellan SET lan=0 WHERE uid=? AND ts=?", dels)
            core.cx.commit()


def merge_invoice_file(path, dirty):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if core.CONNECTED_TEST and not core.REPLICA and data.get("connected_test_run")!=core.CONNECTED_TEST["run_id"]:raise ValueError("Backup is outside this connected-test run")
    n, recs = 0, data["records"]
    with core.LOCK:
        for u, ts in data.get("deleted", []):
            existed = core.cx.execute("SELECT data FROM inv WHERE uid=?", (u,)).fetchone()
            if existed:preserve_lan("lan_before_delete", u, json.loads(existed[0]))
            CLOUD_SYNC.tombstone(u, {"updated": float(ts)})
            n += int(bool(existed))
            core.cx.execute("INSERT INTO del VALUES('invoices',?)", (u,))
        core.cx.commit()
    for i in range(0, len(recs), 300):
        with core.LOCK:
            for u, dd in recs[i:i + 300]:
                if dd.get("_deleted") is True:
                    prior=core.cx.execute("SELECT data FROM inv WHERE uid=?",(u,)).fetchone()
                    if prior:preserve_lan("lan_before_delete",u,json.loads(prior[0]))
                    CLOUD_SYNC.tombstone(u, dd)
                    core.cx.execute("INSERT INTO del VALUES('invoices',?)", (u,))
                    n += 1
                    continue
                up = float(dd.get("updated", 0) or 0)
                r = core.cx.execute("SELECT updated,data FROM inv WHERE uid=?", (u,)).fetchone()
                if r and json.loads(r[1])==dd:continue
                if r and float(r[0] or 0) >= up:
                    preserve_lan("lan_incoming_not_applied",u,dd)
                    continue
                if r:preserve_lan("lan_previous_version",u,json.loads(r[1]))
                tomb = core.cx.execute("SELECT ts FROM dellan WHERE uid=?", (u,)).fetchone()
                if tomb:
                    preserve_lan("lan_blocked_by_delete",u,dd)
                    continue
                core.cx.execute("INSERT OR REPLACE INTO inv(uid,data,updated,dirty,lan) VALUES(?,?,?,?,0)",
                                (u, json.dumps(dd, ensure_ascii=False), up, dirty))
                n += 1
            core.cx.commit()
        time.sleep(0.01)
    return n


def merge_file(path,dirty):
    with open(path,encoding="utf-8") as f:package=json.load(f)
    if "finance_v1" not in package:return merge_invoice_file(path,dirty)
    if not FINANCE_ENABLED:raise ValueError("This backup includes finance history. Upgrade and enable the approved finance version before loading it.")
    fs=localfinance.store(core.DATA_DIR)
    fd,fp=tempfile.mkstemp(prefix="finance_restore_",suffix=".json");os.close(fd)
    try:
        with open(fp,"w",encoding="utf-8") as f:json.dump(package["finance_v1"],f)
        check=localfinance.Finance(":memory:")
        try:check.ops.restore(fp);check.ledger()
        finally:check.ops.db.close()
        with core.LOCK,fs.lock,fs.ops.lock:
            def apply():
                n=merge_invoice_file(path,dirty);fs.ops.restore(fp);return n
            n=restorejournal.CombinedRestore(core.DATA_DIR,core.cx,fs.ops.db).run(apply)
        finance_wake();return n
    finally:os.remove(fp)


def lan_import():
    global ui_dirty
    done = set(json.loads(meta("lan_done", "[]")))
    base = share_dir()
    todo = []
    for folder, prefix, tag in ((os.path.join(base, "sync"), "", "s:"), (os.path.join(base, "backup"), "backup_", "b:"),
                                (base, "backup_", "b:")):
        if os.path.isdir(folder):
            for f in sorted(os.listdir(folder)):
                key = tag + f
                if f.endswith(".json") and f.startswith(prefix) and key not in done \
                        and not f.startswith(prefix + machine() + "_"):
                    todo.append((key, os.path.join(folder, f)))
    n = 0
    for key, path in todo:
        try:
            n += merge_file(path, 0)
        except Exception:
            continue
        done.add(key)
    if todo:
        setmeta("lan_done", json.dumps(sorted(done)))
    if n:
        ui_dirty = True
        reload_data()   # imported rows must enter the in-memory caches, not only SQLite
        bump()


def auto_backup():
    d = os.path.join(share_dir(), "backup")
    os.makedirs(d, exist_ok=True)
    fn = os.path.join(d, f"auto_{machine()}_{time.strftime('%Y%m%d')}.db")
    if not os.path.exists(fn):
        import sqlite3
        dst = sqlite3.connect(fn)
        with core.LOCK:
            core.cx.backup(dst)
        # Unfinished typing is device-local, not distributed in shared-folder backups.
        dst.execute("DELETE FROM meta WHERE k LIKE 'input_draft:%'")
        dst.commit()
        dst.close()
    if FINANCE_ENABLED:
        finance_backup=os.path.join(d,f"auto_finance_{machine()}_{time.strftime('%Y%m%d')}.json")
        if not os.path.exists(finance_backup):
            fp=finance_backup+'.finance.tmp';localfinance.store(core.DATA_DIR).ops.backup(fp)
            try:
                with open(fp,encoding='utf-8') as f:finance_package=json.load(f)
                with open(finance_backup+'.tmp','w',encoding='utf-8') as f:json.dump({'connected_test_run':core.CONNECTED_TEST['run_id'] if core.CONNECTED_TEST else None,'from':machine(),'records':[[u,json.loads(raw)]for u,raw in q('SELECT uid,data FROM inv')],'deleted':[[u,ts]for u,ts in q('SELECT uid,ts FROM dellan')],'finance_v1':finance_package},f,ensure_ascii=False);f.flush();os.fsync(f.fileno())
                os.replace(finance_backup+'.tmp',finance_backup)
            finally:os.remove(fp)
    for f in os.listdir(d):
        p = os.path.join(d, f)
        if f.startswith(f"auto_{machine()}_") and time.time() - os.path.getmtime(p) > 14 * 86400:
            os.remove(p)


def lan_cycle():
    global st_lan,lan_completed
    if core.CONNECTED_TEST and core.CONNECTED_TEST["phase"]=="firebase":
        st_lan="CONNECTED TEST: LAN disabled for Firebase-only phase";return
    try:
        lan_export()
        lan_import()
        if meta("auto_bk", "") != time.strftime("%Y%m%d"):
            auto_backup();setmeta("auto_bk",time.strftime("%Y%m%d"))
        lan_completed+=1
        st_lan = ("ISOLATED TRIAL: 5s local-folder check " if core.TEST_MODE else "Network: 5s change-check, last completed ") + time.strftime("%H:%M:%S")
    except Exception:
        st_lan = "Network folder not reachable - everything is kept on this PC and shared later"


def lan_loop():
    """Check at five-second intervals; one worker only, even while SMB is hung.
    Incremental journals are atomic, unchanged invoices are never recopied, and
    incoming files merge individual records rather than replacing the database.
    """
    global st_lan
    worker = None
    while True:
        started=time.monotonic()
        if worker is None or not worker.is_alive():
            worker = threading.Thread(target=lan_cycle, daemon=True)
            worker.start()
        worker.join(1)
        if worker.is_alive():
            st_lan = "Network folder slow/unreachable - local work is safe; waiting without overlapping copies"
        sync_now.wait(max(0,LAN_CHECK_SECONDS-(time.monotonic()-started)))
        sync_now.clear()


import expenses
import localfinance
import restorejournal
import finance_service
# v55: the package ships finance_rollout_v1.json beside launch_v39.py. First start copies it into this profile's data folder (never overwrites).
# Remove the shipped file (or the copy in the data folder) to switch finance off. Old expenses.db is backed up before migration (localfinance.migrate_legacy).
try:
    _ship=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),"finance_rollout_v1.json")
    _dest=os.path.join(core.DATA_DIR,"finance_rollout_v1.json")
    if not core.TEST_MODE and not core.CONNECTED_TEST and os.path.isfile(_ship) and not os.path.exists(_dest):
        import shutil;os.makedirs(core.DATA_DIR,exist_ok=True);shutil.copyfile(_ship,_dest)
except Exception:
    pass
FINANCE_ROLLOUT=({"bootstrap_read_cap":2000} if core.CONNECTED_TEST else finance_service.rollout(core.DATA_DIR,core.TEST_MODE))
FINANCE_ENABLED=core.TEST_MODE or bool(FINANCE_ROLLOUT)
FINANCE_SERVICE=None

def finance_status():
    if FINANCE_SERVICE:return FINANCE_SERVICE.status()
    return {"enabled":FINANCE_ENABLED,"ready":False,"pending":len(localfinance.store(core.DATA_DIR).ops.pending()) if FINANCE_ENABLED else 0,"error":"Cloud connection unavailable; finance changes remain pending" if FINANCE_ROLLOUT else None,"note":"Isolated local profile, no live finance sync" if core.TEST_MODE else "Finance connection unavailable" if FINANCE_ROLLOUT else "Finance rollout not activated"}

def finance_wake():
    bump()
    if FINANCE_SERVICE:FINANCE_SERVICE.request()

from cloudsync import CloudSync
CLOUD_SYNC = CloudSync(core)
from project_usage import ProjectUsage
PROJECT_USAGE = ProjectUsage(core)
ID_SERVICE = prefix_ids.Service(core, lambda: db is not None and CLOUD_SYNC.live, lambda: docs)
WATCHES = []

def cloud_changed():
    global ui_dirty
    reload_data()
    ui_dirty = True
    bump()
    sync_now.set()

def push():
    CLOUD_SYNC.push()

def pull(first):
    CLOUD_SYNC.pull(first)
    cloud_changed()


def request_cloud(full_pull=False):
    global cloud_now,cloud_pull_requested
    with CLOUD_REQUEST_LOCK:
        cloud_now=True
        if full_pull:cloud_pull_requested=True
    cloud_ev.set()

def cloud_cycle(full_pull=False,first=False):
    global st_cloud,cloud_completed,last_push_at,last_pull_at,pull_done,last_cloud_error
    if core.CONNECTED_TEST and core.CONNECTED_TEST["phase"]=="lan":
        st_cloud="CONNECTED TEST: Firebase disabled for LAN-only phase";return False
    if core.LOCAL_ONLY:
        st_cloud="ISOLATED TRIAL: Firebase disabled";return False
    if db is None:
        st_cloud="Cloud: unavailable/not configured; local changes remain pending";return False
    st_cloud="Cloud: sending pending changes..."
    push()
    # Read a harmless existing metadata identity to verify authenticated reachability even when no writes are pending.
    db.collection("meta").document("invoice_id_prefix_registry").get(timeout=15)
    last_push_at=time.time();last_cloud_error=""
    if first:
        # one full read: the listeners' initial snapshots are the first pull; "received" only after both completed
        WATCHES.extend(CLOUD_SYNC.first_sync(cloud_changed));cloud_changed();last_pull_at=time.time();pull_done+=1
    elif full_pull:
        pull(False);last_pull_at=time.time();pull_done+=1
    cloud_changed()
    cloud_completed+=1
    st_cloud="Cloud: server updated, device receipt unverified "+time.strftime("%H:%M:%S")
    return True

def cloud_loop():
    global st_cloud,cloud_now,cloud_pull_requested,cloud_retry_after,cloud_failures,last_cloud_error
    first,last=True,0
    while True:
        due=cloud_now or time.monotonic()-last>=300
        if due and time.monotonic()>=cloud_retry_after:
            with CLOUD_REQUEST_LOCK:
                cloud_now=False;full=cloud_pull_requested;cloud_pull_requested=False
            last=time.monotonic()
            try:
                if cloud_cycle(full,first):
                    first=False;cloud_failures=0;cloud_retry_after=0
                else:
                    with CLOUD_REQUEST_LOCK:
                        cloud_now=True;cloud_pull_requested|=full
                    cloud_retry_after=time.monotonic()+30
            except Exception:
                cloud_failures+=1
                last_cloud_error=type(sys.exc_info()[1]).__name__
                with CLOUD_REQUEST_LOCK:
                    cloud_now=True;cloud_pull_requested|=full
                cloud_retry_after=time.monotonic()+min(300,10*2**min(cloud_failures-1,5))
                st_cloud="Cloud unavailable (connection/auth/quota); local pending changes retained, retry with backoff"
        cloud_ev.wait(1)
        cloud_ev.clear()

def manual_sync():
    global st_lan
    st_lan="Network: sync requested, awaiting completion"
    request_cloud(True)
    if FINANCE_SERVICE:FINANCE_SERVICE.request()
    sync_now.set()
    reload_data()
    bump()


# ---------------- filters / queries (ported from App) ----------------
def date_filter(text):
    p = [x for x in text.strip().replace("-", "/").replace(".", "/").split("/") if x]
    try:
        if len(p) == 1:
            return int(p[0]), None, None
        if len(p) == 2:
            return int(p[1]), int(p[0]), None
        if len(p) == 3:
            return int(p[2]), int(p[1]), int(p[0])
    except ValueError:
        pass
    return None


def make_pred(f):
    s, cu, df = f.get("sq", "").strip().lower(), norm(f.get("cust", "")), date_filter(f.get("dv", ""))
    cc, cv = f.get("cfc", ""), f.get("cfv", "").strip().lower()
    cb = bool(f.get("cfb")) and bool(cc)
    selected_districts=set(f.get("districts",[]))
    rec, cutoff = bool(f.get("recent")), dt.date.today() - dt.timedelta(days=5)

    def ok(d):
        if selected_districts and d.get("District", "") not in selected_districts:return False
        if s and s not in str(d.get("Invoice Number", "")).lower() and s not in str(d.get("Sales Order No", "")).lower():
            return False
        if cu and cu not in norm(d.get("Customer Name", "")):
            return False
        if df and not (s or cu):
            p = pdate(d.get("Invoice Date"))
            if p and not (p.year == df[0] and (df[1] is None or p.month == df[1]) and (df[2] is None or p.day == df[2])):
                return False
        if rec:
            p = pdate(d.get("Invoice Date"))
            if p and p < cutoff:
                return False
        if cb and str(d.get(cc, "") or "").strip() != "":return False
        return not (cc and cv and not cb and cv not in str(d.get(cc, "")).lower())
    return ok, bool(s or cu or df or rec or selected_districts)


def details_rows(flt, f, snapshot=None):
    source = docs if snapshot is None else snapshot
    ok, any_q = make_pred(f)
    if flt is None and not any_q:
        return []
    out = [u for u, d in source.items() if (not flt or d.get("Invoice Status") == flt) and ok(d)]
    out.sort(key=core.arrival_key, reverse=True)
    return out


def rgr_rows(f, snapshot=None):
    source = docs if snapshot is None else snapshot
    # Unfinished RGR remains pending at any age, even with Last 5 days checked.
    # Keep invoice/customer/column search filters, but never hide it by invoice date.
    f = dict(f, recent=False, dv="")
    ok, _ = make_pred(f)
    out = [u for u, d in source.items()
           if str(d.get("Invoice Type", "")).strip().lower() == "rgr"
           and (not str(d.get("Cost Date Required", "")).strip() or not str(d.get("Cost Date", "")).strip()) and ok(d)]
    return sorted(out, key=core.arrival_key, reverse=True)


def lic_info():
    """License facts for the screen. Empty for the company MAIN/REPLICA programs."""
    if not core.TRIAL_LIMIT: return {"trial": False}
    import license_mgr
    return license_mgr.status(core)
def lic_full():
    return bool(core.TRIAL_LIMIT and lic_info().get("full"))

def route_match(f):
    car, line, drv = f.get("car", "").strip().lower(), f.get("line", "").strip(), f.get("drv", "").strip().lower()
    day = pdate(f.get("date", ""))
    return lambda d: ((not day or pdate(d.get("Distributed Date")) == day)
                      and (not car or str(d.get("Car No", "")).strip().lower() == car)
                      and (not line or str(d.get("Line", "")).strip() == line)
                      and (not drv or str(d.get("Driver name", "")).strip().lower() == drv))


def route_uids(rep_status, f, snapshot=None):
    source = docs if snapshot is None else snapshot
    ok = route_match(f)
    out = [u for u, d in source.items() if d.get("Invoice Status") == rep_status and ok(d)]
    return sorted(out, key=core.arrival_key, reverse=True)


def row_vals(d, cols):
    return [disp_date(d.get(c, "")) if c in DATE_COLS else str(d.get(c, "")) for c in cols]


def sheet_payload(uids, cols, snapshot=None):
    source = docs if snapshot is None else snapshot
    total, uids = len(uids), uids[-MAX_ROWS:]
    return {"total": total, "shown": len(uids),
            "rows": [{"uid": u, "v": row_vals(source[u], cols)} for u in uids]}


# ---------------- Excel imports (ported; files arrive as base64 from the browser) ----------------
class ExcelDateText(str):
    pass

# Column identity is derived only from names, never the workbook's position.
HEADER_ALIASES = {
    "Invoice Number": ("Invoice", "Invoice No", "Invoice No."),
    "Sales Order No": ("Sales order", "Sales order number", "Sales Order No."),
    "Customer Name": ("Name", "Customer"),
    "Invoice Date": ("Created date and time", "Created date/time", "Created", "Date"),
    "Invoice Value": ("Amount", "Invoice amount"),
    "Payment Terms": ("Terms of payment", "Terms"),
}
def header_key(value):
    return " ".join(str(value or "").replace("\ufeff", "").split()).casefold()
def header_columns(headers, fields, required=()):
    keys = [header_key(h) for h in headers]
    result = {}
    for field in fields:
        accepted = {header_key(field), *(header_key(a) for a in HEADER_ALIASES.get(field, ()))}
        # ERP exports may contain a separate generic Date beside their Created date.
        # A named Invoice Date/Created date is more specific; generic Date is last resort.
        if field=="Invoice Date":
            specific=accepted-{header_key("Date")}
            if any(key in specific for key in keys):accepted=specific
        matches = [i for i, key in enumerate(keys) if key in accepted]
        if len(matches)>1:
            return {}, "Ambiguous columns for " + field + ". Keep one named column. Nothing was imported."
        result[field] = matches[0] if matches else None
    missing = [f for f in required if result.get(f) is None]
    if missing:
        return {}, "Missing column header(s): " + ", ".join(missing) + ". Match the system column names. Nothing was imported."
    return result, ""

def named_value(row, index):
    return row[index] if index is not None and index < len(row) else ""

def read_xlsx_bytes(raw, date_columns=None):
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    rows=[]
    for row_index,row in enumerate(wb.active.iter_rows()):
        values=[]
        for column_index,cell in enumerate(row):
            value=cell.value
            if row_index and date_columns:
                header=str(rows[0][column_index] or "").strip().casefold() if column_index<len(rows[0]) else ""
                names,_ = header_columns(rows[0], DATE_COLS)
                name = next((n for n,i in names.items() if i==column_index), None)
                if name and isinstance(value,(int,float)) and not isinstance(value,bool):
                    from openpyxl.utils.datetime import from_excel
                    try:
                        converted=from_excel(value,wb.epoch)
                        if isinstance(converted,dt.datetime):
                            text=converted.isoformat(sep=" ",timespec="seconds") if value%1 else converted.strftime("%d/%m/%Y")
                            converted_text=ExcelDateText(text)
                            converted_text.source={"serial":repr(value),"epoch":wb.epoch.date().isoformat(),"cell":cell.coordinate}
                            value=converted_text
                    except (ValueError,OverflowError):pass
            if isinstance(value,dt.datetime):
                fmt=re.sub(r'"[^"]*"|\[[^\]]*\]',"",cell.number_format.lower())
                if "h" in fmt or "s" in fmt:value=value.isoformat(sep=" ",timespec="seconds" if "s" in fmt or value.second else "minutes")
                elif not (value.hour or value.minute or value.second):value=value.date()
            values.append(value)
        rows.append(tuple(values))
    wb.close()
    if len(rows) < 2:
        return None
    return rows[1:], rows[0]


def import_new(raw, user):
    res = read_xlsx_bytes(raw, BASE[:7])
    if not res:
        return {"ok": False, "msg": "No data rows found."}
    mapping, error = header_columns(res[1], BASE, ("Invoice Number",))
    if error: return {"ok": False, "msg": error}
    existing = {str(d.get("Invoice Number", "")).strip().casefold() for d in docs.values()}
    recs, skipped = [], 0
    for r in res[0]:
        rec = {c: "" for c in COLS}
        for c in BASE[:7]:
            if c=="ID": continue
            value = named_value(r, mapping[c])
            rec[c] = cell_str(value)
            if isinstance(value,ExcelDateText):rec.setdefault("_excel_date_source",{})[c]=value.source
        rec["_terms"] = cell_str(named_value(r,mapping.get("Payment Terms")))
        inv = rec["Invoice Number"]
        if not inv or inv.casefold() in existing:
            skipped += 1
            continue
        existing.add(inv.casefold())
        rec["Invoice Status"], rec["Entered By"] = "Undelivered", user
        rec["_district"] = auto_district(rec["Customer Name"])
        tm = norm(rec.get("_terms", ""))
        rec["_pt"] = next((v for v in get_list("payment_terms") if norm(v) == tm), "") if tm else ""
        recs.append(rec)
    if not recs:
        return {"ok": False, "msg": f"All {skipped} rows already exist or are empty."}
    return {"ok": True, "recs": recs, "skipped": skipped}


def classify_save(rec, user):
    with core.LOCK:
        required = ["Invoice Number", "District", "Forward To", "Invoice Type", "Payment Terms", "Brand Name"]
        missing = [name for name in required if not str(rec.get(name, "") or "").strip()]
        if missing:
            return {"ok": False, "msg": "Required: " + ", ".join(missing), "missing": missing}
        if any(str(d.get("Invoice Number", "")).strip().casefold() == str(rec["Invoice Number"]).strip().casefold() for d in docs.values()):
            return {"ok": False, "msg": "This invoice number already exists. Nothing was replaced."}
        r = dict(rec)
        if r.get("Invoice Status", "Undelivered") not in STATUSES:return {"ok":False,"msg":"Choose an existing Invoice Status."}
        for name in DATE_COLS:
            if r.get(name):r[name]=norm_date_text(str(r[name]))
        r.pop("_dispatch_enabled",None)
        r.pop("_terms", None)
        r.pop("_district", None)
        r.pop("_pt", None)
        uid = new_invoice_uid(r["Invoice Number"])
        r["ID"] = allocated_ids(user,[uid])[0]
        r["Entered By"] = user
        save_doc(uid, r)
        return {"ok": True, "id": r["ID"]}

LAST_IMPORT_UIDS = []
BATCHES = {}
IMPORT_OPTS = {"fixes": {}, "skip": set()}

def import_full(raw, user):
    res = read_xlsx_bytes(raw, BASE)
    if not res:
        return {"ok": False, "msg": "No data rows found."}
    rows, hdr = res
    mapping,error = header_columns(hdr, BASE, ("Invoice Number",))
    if error:return {"ok":False,"msg":error}
    existing = {str(d.get("Invoice Number", "")).strip().casefold() for d in docs.values()}
    new, skipped, blank, existing_count, missing_number = [], 0, 0, 0, 0
    fixes, skip_rows = dict(IMPORT_OPTS.get("fixes") or {}), set(IMPORT_OPTS.get("skip") or ())
    for rown, r in enumerate(rows, start=2):
        rec = {c: "" for c in COLS}
        for c, i in mapping.items():
            rec[c] = cell_str(named_value(r,i))
            if i is not None and i<len(r) and isinstance(r[i],ExcelDateText):rec.setdefault("_excel_date_source",{})[c]=r[i].source
        for fc, fv in (fixes.get(rown) or {}).items():
            rec[fc] = core.manual_date_text(fv) if fc in DATE_COLS and str(fv).strip() else str(fv).strip()
        inv = rec["Invoice Number"]
        if rown in skip_rows and inv:
            skipped += 1; continue
        if not inv:
            skipped += 1
            if any(cell_str(value) for value in r): missing_number += 1
            else: blank += 1
            continue
        if inv.casefold() in existing:
            skipped += 1; existing_count += 1
            continue
        existing.add(inv.casefold())
        rec["Entered By"] = user
        new.append(rec)
    if not new:
        return {"ok": False, "noop": True, "added": 0, "existing": existing_count, "blank": blank, "rows": len(rows), "missing_number": missing_number, "msg": f"No new invoices. Existing invoices skipped: {existing_count}. Empty rows ignored: {blank}. Rows without Invoice Number skipped: {missing_number}. Nothing was changed."}
    taken, pending, prepared = {str(d.get("ID")).upper() for d in docs.values()}, [], []
    now, occupied = time.time(), set(docs)
    for r in new:
        uid = make_uid(r["Invoice Number"])
        while uid in occupied:
            uid = make_uid(r["Invoice Number"]) + "_" + uuid.uuid4().hex[:12]
        occupied.add(uid)
        try:
            pfx,n = prefix_ids.parse(r["ID"])
            identity=pfx+str(n)
        except ValueError:identity=""
        if identity and identity not in taken:
            r["ID"]=ID_SERVICE.claim(identity,uid)
            taken.add(identity)
        else:
            r["ID"]="";pending.append((uid,r))
        prepared.append((uid,r))
    if pending:
        for (uid,r),identity in zip(pending,allocated_ids(user,[uid for uid,r in pending])):r["ID"]=identity
    items=[]
    for uid,r in prepared:
        r["updated"]=now;items.append((uid,r))
    db_put(items, 1, 1)
    docs.update(dict(items))
    LAST_IMPORT_UIDS[:] = [u for u, _ in items]
    bump()
    sync_now.set(); request_cloud()
    return {"ok": True, "added": len(new), "existing": existing_count, "blank": blank, "rows": len(rows), "missing_number": missing_number, "msg": f"Added {len(new)} invoices. Existing invoices skipped: {existing_count}. Empty rows ignored: {blank}. Rows without Invoice Number skipped: {missing_number}."}


# ---------------- import review: open each invoice like New Invoice, decide per field ----------------
# Nothing is written until the user presses the final button. Every difference is an explicit per-field choice.
# Technical protection only (not a business-policy list): the invoice number/ID are the match key, and the print
# status fields plus Entered By are written only by the print/entry flows (core.LOCKED). Everything else the app lets a
# user edit by hand can be chosen from the Excel value, through the same validation as a manual edit.
REVIEW_MAX = 400
NUMERIC_FIELDS = ("Invoice Value", "Return Value")
KEY_FIELDS = ("ID", "Invoice Number")

def _num_text(v):
    try: return float(str(v).replace(",", "").strip())
    except ValueError: return None

def _same_value(field, a, b):
    a, b = str(a or "").strip(), str(b or "").strip()
    if a == b: return True
    if field in DATE_COLS:
        pa, pb = pdate(a), pdate(b)
        return bool(pa and pb and pa == pb and norm_date_text(a) == norm_date_text(b))
    if field in NUMERIC_FIELDS:
        na, nb = _num_text(a), _num_text(b)
        return na is not None and nb is not None and na == nb
    return False

def field_problem(field, value):
    """Why this value would be refused as a manual edit, or '' if fine. Same rules the New Invoice screen applies."""
    v = str(value or "").strip()
    if not v: return ""
    if field == "Invoice Status" and v not in STATUSES: return f"'{v}' is not in the program's status list."
    if field in DATE_COLS:
        try: core.manual_date_text(v)
        except ValueError: return f"'{v}' is not a readable date (DD/MM/YYYY or YYYY-MM-DD)."
    if field in NUMERIC_FIELDS and _num_text(v) is None: return f"'{v}' is not a number."
    return ""

def _read_file_records(raw):
    res = read_xlsx_bytes(raw, BASE)
    if not res: return None
    rows, hdr = res
    mapping,error = header_columns(hdr, BASE, ("Invoice Number",))
    if error:return {"ok":False,"msg":error}
    missing = [c for c,i in mapping.items() if i is None]
    out = []
    for n,r in enumerate(rows,start=2):
        # Absent optional columns are not proposed as blank updates to existing invoices.
        rec = {c:cell_str(named_value(r,i)) for c,i in mapping.items() if i is not None}
        out.append((n,rec,any(cell_str(v) for v in r)))
    return out, missing

def pending_upload_count():
    return q("SELECT count(*) FROM inv WHERE dirty=1")[0][0]

def import_plan(raw):
    """Read-only. Never writes to the DB, cloud, or receipts."""
    parsed = _read_file_records(raw)
    if not parsed: return {"ok": False, "msg": "No data rows found."}
    if isinstance(parsed,dict):return parsed
    recs, missing = parsed
    dirty = {r[0] for r in q("SELECT uid FROM inv WHERE dirty=1")}
    by_num = {}
    for uid, d in list(docs.items()):
        n = str(d.get("Invoice Number", "")).strip().casefold()
        if n: by_num.setdefault(n, (uid, d))
    problems, review, seen = [], [], {}
    new = existing = blank = same = 0
    required = ["District", "Forward To", "Invoice Type", "Payment Terms", "Brand Name"]
    if missing:
        problems.append({"row": 1, "invoice": "", "level": "check", "reason": "Missing column header(s): " + ", ".join(missing) + ". Missing optional columns stay blank for new invoices and are not proposed as edits to existing invoices."})
    for n, rec, has_data in recs:
        if not has_data: blank += 1; continue
        inv = rec["Invoice Number"]
        if not inv:
            problems.append({"row": n, "invoice": "", "level": "skipped", "reason": "Invoice Number is empty; the row would be skipped."}); continue
        key = inv.casefold()
        if key in seen:
            problems.append({"row": n, "invoice": inv, "level": "skipped", "reason": f"Same Invoice Number as row {seen[key]}; this later row would be skipped."}); continue
        seen[key] = n
        if key in by_num:
            existing += 1
            uid, d = by_num[key]
            fields = []
            for f in COLS:
                if f in KEY_FIELDS or f not in rec: continue
                cur, xl = str(d.get(f, "") or ""), rec[f]
                if _same_value(f, cur, xl): continue
                item = {"name": f, "current": cur, "excel": xl, "problem": field_problem(f, xl),
                        "excel_blank": not xl.strip(), "protected": ("Written only by the print screens." if f in ("Print Status Sales Order", "Print Status Invoice") else "Set by the program when the invoice was entered.") if f in LOCKED else ""}
                fields.append(item)
            if fields:
                ctx = [{"name": f, "current": str(d.get(f, "") or ""), "excel": rec.get(f, ""), "in_file": f in rec} for f in COLS if f not in KEY_FIELDS]
                review.append({"kind": "existing", "row": n, "invoice": inv, "uid": uid, "base": d.get("updated", 0), "context": ctx,
                               "locked": "This invoice has changes not uploaded yet." if uid in dirty else "", "fields": fields})
            else:
                same += 1
        else:
            new += 1
            fields = []
            for f in BASE:
                if f in KEY_FIELDS: continue
                pr = field_problem(f, rec.get(f, ""))
                if not pr and f in required and not rec.get(f, "").strip(): pr = "Required on the New Invoice screen but empty in the file."
                if pr: fields.append({"name": f, "value": rec.get(f, ""), "excel": rec.get(f, ""), "problem": pr})
            if fields:
                ctx = [{"name": f, "value": rec.get(f, "")} for f in BASE if f not in KEY_FIELDS]
                review.append({"kind": "new", "row": n, "invoice": inv, "fields": fields, "context": ctx})
    return {"ok": True, "rows": len(recs), "blank": blank, "new": new, "existing": existing, "same": same,
            "problems": problems[:REVIEW_MAX], "problem_total": len(problems),
            "review": review[:REVIEW_MAX], "review_total": len(review), "pending_upload": pending_upload_count(),
            "msg": "Preview only. Nothing was saved or sent."}

def _validate_existing(uid, base, expect, changes):
    """Verify against the CURRENT record, not only the preview. Returns '' or a refusal reason."""
    d = docs.get(uid)
    if not d or d.get("_kind") in ("wh", "pi"): return "Invoice no longer found."
    if q("SELECT 1 FROM inv WHERE uid=? AND dirty=1", (uid,)): return "Has changes not uploaded yet. Nothing changed."
    if abs(float(d.get("updated", 0) or 0) - float(base or 0)) > 1e-6: return "Changed since the preview. Preview again."
    for f, v in changes.items():
        if f in KEY_FIELDS or f in LOCKED or f not in EDITABLE: return f"{f} is technically protected."
        if not _same_value(f, d.get(f, ""), (expect or {}).get(f, "")): return f"{f} changed since the preview. Preview again."
    return ""

def apply_updates(items, user):
    """items: [{uid, base, invoice, reason, expect:{field:current}, changes:{field:excelValue}}] - one entry per invoice, only the fields the user chose."""
    applied, rejected, uids = 0, [], []
    audit = []
    for it in items or []:
        uid, ch = str(it.get("uid", "")), dict(it.get("changes") or {})
        if not ch: continue
        inv = it.get("invoice", "")
        with core.LOCK:
            why = _validate_existing(uid, it.get("base"), it.get("expect"), ch)
            if why: rejected.append({"invoice": inv, "reason": why}); continue
            old = {f: str(docs[uid].get(f, "") or "") for f in ch}
            res = apply_invoice_changes(uid, ch, str(it.get("reason", "")))
        if res.get("ok"):
            applied += len(ch); uids.append(uid)
            audit += [{"invoice": inv, "field": f, "old": old[f], "new": str(ch[f])} for f in ch]
        else:
            rejected.append({"invoice": inv, "reason": res.get("msg") or ("Cancelling needs a reason." if res.get("need_reason") else "Refused.")})
    if audit:
        try:
            with open(os.path.join(core.DATA_DIR, "import_updates_audit.jsonl"), "a", encoding="utf-8") as f:
                for a in audit: f.write(json.dumps(dict(a, at=time.strftime("%Y-%m-%d %H:%M:%S"), user=user), ensure_ascii=False) + "\n")
        except OSError: pass
    return {"ok": True, "applied": applied, "rejected": rejected, "uids": uids}

def _check_new_fixes(fixes):
    for row, fields in (fixes or {}).items():
        for f, v in fields.items():
            if f not in BASE or f in KEY_FIELDS: return f"Row {row}: {f} cannot be set here."
            pr = field_problem(f, v)
            if pr: return f"Row {row}, {f}: {pr}"
    return ""

def import_commit(raw, user, request_id, expect_new, existing_items, new_fixes, skip_rows):
    plan = import_plan(raw)
    if not plan.get("ok"): return plan
    skip_rows = {int(x) for x in (skip_rows or [])}
    fixes = {int(k): v for k, v in (new_fixes or {}).items()}
    err = _check_new_fixes(fixes)
    if err: return {"ok": False, "msg": err + " Nothing was saved."}
    if plan["new"] != int(expect_new or 0):
        return {"ok": False, "msg": "The data changed since the preview (new invoice count differs). Nothing was saved. Preview again."}
    upd = apply_updates(existing_items, user) if existing_items else {"applied": 0, "rejected": [], "uids": []}
    LAST_IMPORT_UIDS[:] = []
    IMPORT_OPTS.update(fixes=fixes, skip=skip_rows)
    res = tracked_full_import(raw, user, request_id) if plan["new"] else {"ok": True, "added": 0, "msg": "No new invoices."}
    IMPORT_OPTS.update(fixes={}, skip=set())
    batch = uuid.uuid4().hex[:12]
    BATCHES[batch] = set(upd["uids"]) | set(LAST_IMPORT_UIDS if res.get("ok") else [])
    for u in BATCHES[batch]: CLOUD_SYNC.acks.pop(u, None)
    return {"ok": bool(res.get("ok") or res.get("noop") or not plan["new"]), "added": res.get("added", 0), "updated_fields": upd["applied"],
            "rejected_updates": upd["rejected"], "import_msg": res.get("msg", ""), "request_id": res.get("request_id", request_id),
            "batch": batch, "sync": sync_state(batch)}

last_push_at = last_pull_at = 0.0
pull_done = 0
last_cloud_error = ""

def batch_state(batch):
    """Upload truth for one batch: only a recorded server write counts as uploaded. 'Nothing pending' alone is not proof."""
    uids = BATCHES.get(batch)
    if uids is None:
        return None
    def ack(u):  # an ack counts only for the exact version now on this PC
        a = CLOUD_SYNC.acks.get(u); d = docs.get(u)
        if a and a[0] == "deleted" and not d: return "deleted"
        return a[0] if a and d and float(a[1] or 0) == float(d.get("updated", 0) or 0) else None
    acks = {u: ack(u) for u in uids}
    gone = [u for u in uids if u not in docs and not (CLOUD_SYNC.acks.get(u) or ("",))[0] == "deleted"]
    return {"total": len(uids), "written": sum(1 for u in uids if acks[u] == "written"),
            "server_newer": sum(1 for u in uids if acks[u] == "server_newer"),
            "deleted_elsewhere": sum(1 for u in uids if acks[u] == "deleted"),
            "waiting": sum(1 for u in uids if acks[u] is None and u not in gone), "removed_locally": len(gone)}

def cloud_connection():
    configured=db is not None and not core.LOCAL_ONLY
    age=time.time()-max(last_push_at,last_pull_at)
    connected=bool(configured and CLOUD_SYNC.live and not last_cloud_error and age<360)
    return {"connected":connected,"configured":configured,"last_success":max(last_push_at,last_pull_at),
            "reason":"Recent authenticated server connection" if connected else "Disconnected, not ready or last connection check failed"}

def sync_state(batch=None):
    return {"pending": pending_upload_count(), "cloud": st_cloud, "pushed_at": last_push_at, "pulled_at": last_pull_at,
            "pull_seq": pull_done, "pull_kept_local": CLOUD_SYNC.kept_local, "error": last_cloud_error,
            "configured": (db is not None and not core.LOCAL_ONLY), "batch": batch_state(batch) if batch else None}



def delivery_followup(view, today=None):
    """Read-only Undelivered review. Never applies dispatch or financial changes."""
    if view not in ('district', 'overdue', 'expected'):
        return {'ok': False, 'msg': 'Choose a Delivery Follow-up view.'}
    from decimal import Decimal
    today = today or dt.date.today()
    districts = {}
    with core.LOCK, STATE_LOCK:
        reload_data()
        for uid, source in docs.items():
            if str(source.get('Invoice Status', '')).strip() != 'Undelivered':
                continue
            invoice_date = pdate(source.get('Invoice Date', ''))
            age = (today - invoice_date).days if invoice_date else None
            expected = str(source.get('Expected Date', '') or '').strip()
            if view == 'overdue' and (age is None or age < 8):
                continue
            if view == 'expected' and (not expected or not pdate(expected)):
                continue
            history = [x for x in source.get('delivery_extensions', []) if isinstance(x, dict)] if isinstance(source.get('delivery_extensions', []), list) else []
            latest = history[-1] if history else None
            due = None
            if latest:
                try: due = dt.date.fromisoformat(latest['due_date'])
                except (KeyError, ValueError, TypeError): pass
            if due:
                remaining = (due-today).days
                state = 'Reply needed' if remaining <= 0 else 'Alert: 1 day left' if remaining == 1 else f'{remaining} days left'
                alert = remaining <= 1
            else:
                state = 'Reply needed' if age is not None and age >= 10 else 'Alert' if age is not None and age >= 8 else 'Within 10 days' if age is not None else 'Invoice Date missing / invalid'
                alert = age is not None and age >= 8
            try:
                from decimal import Decimal
                value = Decimal(str(source.get('Invoice Value', '') or '0').replace(',', ''))
                if not value.is_finite(): raise ValueError()
                amount = format(value, '.2f')
            except Exception:
                amount = ''
            district = str(source.get('District', '') or '').strip() or '(No district)'
            customer = str(source.get('Customer Name', '') or '').strip() or '(No customer)'
            row = {'uid':uid, 'number':str(source.get('Invoice Number', '')), 'invoice_date':disp_date(source.get('Invoice Date', '')),
                   'expected':disp_date(expected), '_sort_date':(pdate(expected) if view=='expected' else invoice_date).isoformat() if (pdate(expected) if view=='expected' else invoice_date) else '', 'value':amount, 'remarks':str(source.get('Remarks', '') or ''),
                   'age':age, 'state':state, 'alert':alert, 'due_date':due.isoformat() if due else '',
                   'extensions':history, 'updated':source.get('updated', 0)}
            districts.setdefault(district, {}).setdefault(customer, []).append(row)
    groups = []
    for district, customers in sorted(districts.items(), key=lambda x:x[0].casefold()):
        cg = []
        for customer, rows in sorted(customers.items(), key=lambda x:x[0].casefold()):
            rows.sort(key=lambda r: core.arrival_key(r['uid']), reverse=True)
            cg.append({'name':customer, 'rows':rows, 'count':len(rows), 'value':format(sum((Decimal(r['value']) for r in rows if r['value']), Decimal(0)), '.2f')})
        groups.append({'name':district, 'customers':cg, 'count':sum(c['count'] for c in cg), 'value':format(sum((Decimal(c['value']) for c in cg), Decimal(0)), '.2f')})
    return {'ok':True, 'view':view, 'as_of':today.isoformat(), 'districts':groups,
            'count':sum(g['count'] for g in groups), 'customers':sum(len(g['customers']) for g in groups)}


def delivery_extend(uid, days, note, user, expected, request_id, today=None):
    """Manual extension from save day. Preserve invoice dates/status and audit each reply."""
    if not isinstance(days, (str, int)) or isinstance(days, bool) or not re.fullmatch(r"[1-9][0-9]*", str(days).strip()):
        return {"ok": False, "msg": "Enter a whole number of extra days greater than zero."}
    days = int(str(days).strip())
    if days > 3650:
        return {"ok": False, "msg": "Use 3650 days or fewer."}
    if not isinstance(note, str) or not note.strip():
        return {"ok": False, "msg": "Write the reason for the delay."}
    if len(note) > 10000:
        return {"ok": False, "msg": "Delay reason is too long (maximum 10000 characters)."}
    if not isinstance(request_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{16,80}", request_id):
        return {"ok": False, "msg": "Reload this form before saving."}
    today = today or dt.date.today()
    with core.LOCK, STATE_LOCK:
        reload_data()
        source = docs.get(uid)
        if not source or str(source.get("Invoice Status", "")).strip() != "Undelivered":
            return {"ok": False, "msg": "This invoice is no longer Undelivered. Refresh the review."}
        history = [x for x in source.get("delivery_extensions", []) if isinstance(x, dict)] if isinstance(source.get("delivery_extensions", []), list) else []
        for x in history:
            if x.get("request_id") == request_id:
                if x.get("days") != days or x.get("note") != note.strip() or x.get("by") != user:
                    return {"ok": False, "msg": "This request was already saved with different values. Refresh."}
                return {"ok": True, "noop": True, "extension": x}
        try: same_version = abs(float(expected) - float(source.get("updated", 0))) <= 1e-6
        except (ValueError, TypeError): same_version = False
        if not same_version:
            return {"ok": False, "msg": "The invoice changed since this view opened. Refresh before adding days."}
        date = pdate(source.get("Invoice Date", ""))
        if not date or (today-date).days < 8:
            return {"ok": False, "msg": "Follow-up starts at 8 elapsed days from Invoice Date."}
        entry = {"request_id": request_id, "days": days, "note": note.strip(), "by": user,
                 "saved_on": now_str(), "saved_date": today.isoformat(),
                 "due_date": (today+dt.timedelta(days=days)).isoformat(),
                 "reminder_date": (today+dt.timedelta(days=days-1)).isoformat(),
                 "previous_due_date": history[-1].get("due_date", "") if history else (date+dt.timedelta(days=10)).isoformat()}
        history.append(entry)
        changed = dict(source, delivery_extensions=history)
        save_doc(uid, changed)
    return {"ok": True, "extension": entry}


# ---------------- cash receipt review (read-only; never changes status, payment or any field) ----------------
# Candidate set: every invoice whose Payment Terms text contains "cash", any invoice type, any status. Nothing is
# excluded silently; the summary shows coverage by term, type and status so the user can narrow it.
# "Possible receipt" = Remarks has a receipt word AND a number of 3+ digits outside dates. That is a heuristic, NOT a
# confirmed receipt format, and "possible" is never "verified" or "paid".
_RECEIPT_WORD = re.compile("\u0627\u064a\u0635\u0627\u0644|\u0633\u062f\u0627\u062f|receipt|rcpt|\u0648\u0635\u0644", re.I)
_NEGATION = re.compile("\u0628\u062f\u0648\u0646|\u0644\u0627 \u064a\u0648\u062c\u062f|\u0645\u0641\u064a\u0634|\u0644\u0645 |\\bno\\b|\\bnot\\b|\\bwithout\\b", re.I)
_DATE_IN_TEXT = re.compile(r"\d{1,4}\s*[-/.]\s*\d{1,2}\s*[-/.]\s*\d{1,4}")

def _norm_alef(t):
    return re.sub("[\u0623\u0625\u0622]", "\u0627", str(t or ""))

def classify_receipt_remark(text):
    t = _norm_alef(text)
    if not t.strip():
        return "blank", ""
    big = [m for m in re.findall(r"\d+", _DATE_IN_TEXT.sub(" ", t)) if len(m) >= 3]
    word = bool(_RECEIPT_WORD.search(t))
    if word and big:
        return "possible_receipt", big[0]
    return ("word_no_number" if word else "number_no_word" if big else "no_receipt_info"), (big[0] if big else "")

CASH_REASONS = {"blank": "Remarks is empty.", "word_no_number": "Remarks mentions a receipt but has no receipt number.",
                "number_no_word": "Remarks has a number but does not say it is a receipt.",
                "no_receipt_info": "Remarks has text but no receipt number.",
                "possible_receipt": "Possible receipt (word and number found). Not verified."}

def cash_receipt_review():
    cands = [(uid, d) for uid, d in list(docs.items()) if "cash" in str(d.get("Payment Terms", "")).lower()]
    numbers = collections.Counter()
    meta_rows = []
    for uid, d in cands:
        kind, num = classify_receipt_remark(d.get("Remarks", ""))
        if num: numbers[num] += 1
        meta_rows.append((uid, d, kind, num))
    coverage = collections.Counter((str(d.get("Payment Terms", "")), str(d.get("Invoice Type", "")), str(d.get("Invoice Status", ""))) for _, d in cands)
    counts, rows, table_rows = collections.Counter(), [], []
    for uid, d, kind, num in meta_rows:
        flags = []
        if kind == "possible_receipt":
            inv = str(d.get("Invoice Number", ""))
            if num and num in re.sub(r"\D", "", inv) and len(num) >= 3 and (num == inv or inv.endswith(num)): flags.append("number equals the invoice number")
            if _NEGATION.search(_norm_alef(d.get("Remarks", ""))): flags.append("wording may say there is no receipt")
            if numbers[num] > 1: flags.append("same number on another invoice")
        label = kind if not flags else "possible_receipt_check"
        counts[label] += 1
        table_rows.append({"values": [disp_date(d.get(col, "")) if col in DATE_COLS else str(d.get(col, "")) for col in BASE[:BASE.index("Payment Terms")+1]], "uid": uid, "customer": d.get("Customer Name", ""), "invoice": d.get("Invoice Number", ""),
                           "sales_order": d.get("Sales Order No", ""), "date": d.get("Invoice Date", ""),
                           "value": d.get("Invoice Value", ""), "terms": d.get("Payment Terms", ""),
                           "line": d.get("Line", ""), "driver": d.get("Driver name", ""), "car": d.get("Car No", ""),
                           "status": d.get("Invoice Status", ""), "type": d.get("Invoice Type", ""),
                           "remarks": str(d.get("Remarks", "")), "receipt_hint": label,
                           "collection_status": "unknown", "collected_date": d.get("Collected Date", ""),
                           "collected_fees": d.get("Collected Fees", "")})
        if label != "possible_receipt":
            rows.append({"uid": uid, "invoice": d.get("Invoice Number", ""), "date": d.get("Invoice Date", ""), "status": d.get("Invoice Status", ""),
                         "type": d.get("Invoice Type", ""), "terms": d.get("Payment Terms", ""),
                         "reason": CASH_REASONS.get(kind, "") + ((" Check: " + "; ".join(flags) + ".") if flags else ""),
                         "remarks": str(d.get("Remarks", ""))[:120]})
    if FINANCE_ENABLED:
        marks=localfinance.store(core.DATA_DIR).marks()
        for row in table_rows:row["manual_mark"]=marks.get(row["uid"],{"state":"unmarked","heads":[]})
    return {"ok": True, "candidates": len(cands), "by_label": dict(counts), "to_review": len(rows), "rows": rows,
            "table_columns": BASE[:BASE.index("Payment Terms")+1], "table_rows": sorted(table_rows, key=lambda x: core.arrival_key(x["uid"]), reverse=True),
            "coverage": [{"terms": k[0], "type": k[1], "status": k[2], "count": v} for k, v in sorted(coverage.items(), key=lambda x: -x[1])][:60],
            "msg": "Review list only. 'Possible receipt' is a guess from the wording, not proof of a receipt or of payment. No status or payment field is changed."}


# ---------------- district reminder after preparing invoices (read-only; never assigns, adds or changes anything) ----------------
# Grounded in the current workflow: invoices wait as "Undelivered" with no Distributed Date/Car/Driver; "Edit selected (bulk)"
# sets those fields (BULK_FIELDS) and the invoices become Proposal/inprocess. A district is "partly prepared" when some of its
# waiting invoices were just prepared and others were left. Candidate rule (proposal, not user-approved):
#   waiting = same District, Invoice Type "Commercial Invoice", Invoice Status "Undelivered", no Distributed Date, not in this save.
DISTRIBUTION_FIELDS = ("Distributed Date", "Car No", "Driver name")
WAITING_STATUS = "Undelivered"

def district_remaining(prepared_uids):
    prepared = [u for u in prepared_uids if u in docs]
    by_district = collections.defaultdict(list)
    for u in prepared:
        dist = str(docs[u].get("District", "")).strip()
        if dist: by_district[dist].append(u)
    today = dt.date.today()
    out = []
    for dist, ups in sorted(by_district.items()):
        rem = []
        for uid, d in docs.items():
            if uid in ups or str(d.get("District", "")).strip() != dist: continue
            if str(d.get("Invoice Type", "")).strip() != "Commercial Invoice" or d.get("Invoice Status") != WAITING_STATUS: continue
            if str(d.get("Distributed Date", "")).strip(): continue
            p = pdate(d.get("Invoice Date", ""))
            rem.append({"uid": uid, "invoice": d.get("Invoice Number", ""), "customer": d.get("Customer Name", ""),
                        "date": disp_date(d.get("Invoice Date", "")), "age_days": (today - p).days if p else None})
        if rem:
            rem.sort(key=lambda x: (str(x["customer"]).casefold(), str(x["invoice"])))
            out.append({"district": dist, "prepared": len(ups), "remaining": rem})
    return {"ok": True, "districts": out, "msg": "Reminder only. Nothing is assigned or changed. Leaving a customer out may be intentional."}


FULL_IMPORT_LOCK = threading.Lock()

def import_receipt(kind="full"):
    if kind not in {"full", "wh", "pi"}: return None
    try:
        with open(os.path.join(core.DATA_DIR, kind + "_import_receipt.json"), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def record_import(receipt, kind="full"):
    path = os.path.join(core.DATA_DIR, kind + "_import_receipt.json")
    try:
        temp = path + ".tmp"
        with open(temp, "w", encoding="utf-8") as f:
            json.dump(receipt, f, ensure_ascii=False)
        os.replace(temp, path)
        with open(os.path.join(core.DATA_DIR, "import_diagnostics.log"), "a", encoding="utf-8") as f:
            f.write(json.dumps(receipt, ensure_ascii=False) + "\n")
    except Exception:
        pass  # diagnostic failure never converts an already-committed import into a retry

def tracked_excel_import(kind, raw, user, request_id):
    if not FULL_IMPORT_LOCK.acquire(blocking=False):
        return {"ok": False, "msg": "An Excel import is already running. Wait for its result; do not submit another copy."}
    started = time.time()
    receipt = {"request_id": re.sub(r"[^a-zA-Z0-9_-]", "", str(request_id))[:64] or uuid.uuid4().hex,
               "started": time.strftime("%Y-%m-%d %H:%M:%S"), "state": "running", "bytes": len(raw), "kind": kind}
    record_import(receipt, kind)
    try:
        result = {"full": lambda: import_full(raw, user), "wh": lambda: wh_import(raw), "pi": lambda: pi_import(raw, user)}[kind]()
        receipt.update(state="complete", finished=time.strftime("%Y-%m-%d %H:%M:%S"), seconds=round(time.time()-started, 2), result=result)
        record_import(receipt, kind)
        return dict(result, request_id=receipt["request_id"])
    except Exception as error:
        result = {"ok": False, "msg": "Import failed: " + type(error).__name__ + ": " + str(error)}
        receipt.update(state="failed", finished=time.strftime("%Y-%m-%d %H:%M:%S"), seconds=round(time.time()-started, 2), result=result)
        record_import(receipt, kind)
        return dict(result, request_id=receipt["request_id"])
    finally:
        FULL_IMPORT_LOCK.release()


def full_import_receipt():
    return import_receipt("full")

def tracked_full_import(raw, user, request_id):
    return tracked_excel_import("full", raw, user, request_id)


def warehouse_invoice_index():
    """Read-only, exact normalized Sales Order joins. Never pair worksheet row positions."""
    candidates = {}
    for d in list(docs.values()):
        inv, so = str(d.get("Invoice Number", "")).strip(), str(d.get("Sales Order No", "")).strip()
        if inv and so: candidates.setdefault(norm(inv), []).append((0, inv, so, str(d.get("Invoice Date", ""))))
    for d in list(pinv_rows.values()):
        inv, so = str(d.get("inv", "")).strip(), str(d.get("so", "")).strip()
        if inv and so: candidates.setdefault(norm(inv), []).append((1, inv, so, str(d.get("created", ""))))
    result, conflicts = {}, set()
    for rows in candidates.values():
        orders = {norm(r[2]) for r in rows}
        if len(orders) != 1:
            conflicts.update(orders); continue
        rows.sort(reverse=True)
        selected = rows[0]
        created = next((r[3] for r in rows if r[3]), "")
        result.setdefault(norm(selected[2]), []).append((selected[1], created))
    return {so: sorted(set(values)) for so, values in result.items()}, conflicts

def warehouse_invoice_text(row, index):
    values = index.get(norm(row["so"]), [])
    return ", ".join(v[0] for v in values), " | ".join(disp_date(v[1]) for v in values if v[1])


def wh_import(raw):
    res = read_xlsx_bytes(raw)
    if not res:
        return {"ok": False, "msg": "No data rows found."}
    mapping,error=header_columns(res[1],["Sales Order No","Customer Name","Invoice Date"],("Sales Order No","Customer Name"))
    if error:return {"ok":False,"msg":error}
    so_col,cu_col,dt_col=(mapping[n] for n in ["Sales Order No","Customer Name","Invoice Date"])
    have, items, now = {r["so"] for r in wh_rows.values()}, [], time.time()
    for k, r in enumerate(res[0]):
        so = cell_str(r[so_col]) if so_col < len(r) else ""
        if not so or so in have: continue
        when = cell_str(r[dt_col]) if dt_col is not None and dt_col < len(r) else ""
        customer = cell_str(r[cu_col]) if cu_col is not None and cu_col < len(r) else ""
        items.append((wh_uid(so), {"_kind": "wh", "so": so, "dt": when, "cu": customer,
                                   "p": 0, "on": "", "by": "", "seq": now * 1000 + k, "updated": now}))
        have.add(so)
    if items:
        db_put(items, 1, 1)
        wh_rows.update(dict(items))
        bump()
        sync_now.set(); request_cloud()
    # A first import sheet means these delivery notes were printed outside the app:
    # mark the Sales Order print status on their invoices (evidence is the sheet, not an app print).
    sheet_sos = [cell_str(r[so_col]) for r in res[0] if so_col < len(r) and cell_str(r[so_col])]
    marked = mark_docs_printed("Print Status Sales Order", sheet_sos, "Sales Order No")
    return {"ok": True, "msg": f"{len(items)} new rows added."
                               + (f" Sales Order print status marked from this sheet on {marked} invoice(s)." if marked else "")}


def pi_import(raw, user):
    """Import invoice numbers plus source-grounded customer/created/order metadata.
    Print audit timestamps remain distinct. Nothing is sent to the printer."""
    res = read_xlsx_bytes(raw)
    if not res:
        return {"ok": False, "msg": "No data rows found."}
    mapping,error=header_columns(res[1],["Invoice Number","Sales Order No","Customer Name","Invoice Date"],("Invoice Number",))
    if error:return {"ok":False,"msg":error}
    idx=mapping["Invoice Number"]
    have, items, now = {r["inv"] for r in pinv_rows.values()}, [], time.time()
    by_inv = {r["inv"]: (uid, r) for uid, r in pinv_rows.items()}
    metadata_cols={key:mapping[field] for key,field in {"cu":"Customer Name","created":"Invoice Date","so":"Sales Order No"}.items()}
    added, refreshed = 0, 0
    on, today = now_str(), dt.date.today().strftime("%d/%m/%Y")
    sheet_invs = []
    for k, r in enumerate(res[0]):
        inv = cell_str(r[idx]) if len(r) > idx else ""
        if not inv:
            continue
        sheet_invs.append(inv)
        metadata = {key: cell_str(r[ix]) for key, ix in metadata_cols.items() if ix is not None and ix < len(r) and cell_str(r[ix])}
        if inv in have:
            old = by_inv.get(inv)
            if old and any(old[1].get(k, "") != v for k, v in metadata.items()):
                data = dict(old[1]); data.update(metadata, updated=now)
                items.append((old[0], data)); refreshed += 1
            continue
        added += 1
        items.append(("pi_" + re.sub(r"[^\w.\-]", "_", inv), {"_kind": "pi", "inv": inv, "p": 0, "on": "",
                                                              "date": "", "by": user, "seq": now * 1000 + k,
                                                              "updated": now, **metadata}))
        have.add(inv)
    marked = 0  # Import stores data only; successful Save PDF owns print audit.
    known = {str(d.get("Invoice Number", "")).strip().lower() for d in docs.values()}
    unmatched = sorted({v for v in sheet_invs if v.strip().lower() not in known})
    if items:
        db_put(items, 1, 1)
        pinv_rows.update(dict(items))
        bump()
        sync_now.set(); request_cloud()
    msg = f"{added} invoices imported, not marked Printed"
    if refreshed: msg += f"; source metadata updated on {refreshed} existing printed-invoice record(s)"
    if marked:
        msg += f"; {marked} invoice record(s) updated with Print Status Invoice = Printed"
    if unmatched:
        msg += (f"; {len(unmatched)} number(s) not found in the program (left unchanged): "
                + ", ".join(unmatched[:10]) + (" ..." if len(unmatched) > 10 else ""))
    return {"ok": True, "msg": msg + "."}


# ---------------- PDF actions (ported; printing still happens on this PC) ----------------
def open_file(path):
    if hasattr(os, "startfile"):
        os.startfile(path)
        return True
    return False


def pdf_route(rep_title, rep_status, f, save_only=False):
    uids = route_uids(rep_status, f)
    if not uids:
        return {"ok": False, "msg": "No invoices match these values."}
    rows = [dict(docs[u]) for u in uids]
    out_uids=set()
    for raw, in q("SELECT data FROM inv WHERE uid LIKE 'review_%'"):
        plan=json.loads(raw)
        if plan.get('_kind')!='review_plan':continue
        for uid,mark in plan.get('marks',{}).items():
            if mark.get('out') and uid in docs and all(str(docs[uid].get(field,'')).strip()==str(plan.get(k,'')).strip() for field,k in [('Driver name','driver'),('Distributed Date','date'),('Car No','car'),('Line','line')]):
                out_uids.add(uid)
    for uid,row in zip(uids,rows):row['_review_out']=uid in out_uids
    drv, car, line = f.get("drv", "").strip(), f.get("car", "").strip(), f.get("line", "").strip()
    name = f"{(drv.split()[0] if drv else 'NODRIVER').upper()}-{car or 'X'}-{line or 'X'}.pdf"
    path = unique_path(os.path.join(desktop(), re.sub(r'[\\/:*?"<>|\s]+', "_", name)))
    try:
        core.make_route_pdf(path, rep_title, f.get("date", ""), drv, car, line, rows, now_str(), include_ack=rep_status != "Proposal")
    except Exception as e:
        return {"ok": False, "msg": f"PDF error: {e}"}
    if save_only:
        return {"ok": True, "msg": f"Saved on Desktop: {os.path.basename(path)}"}
    ok = print_file(path, 1 if rep_status == "Proposal" else 2)
    return {"ok": True, "msg": f"Saved on Desktop: {os.path.basename(path)}"
                               + (" - sent to printer" if ok else " - press Ctrl+P to print")}


def pdf_ho(f):
    a, b = pdate(f.get("from", "")), pdate(f.get("to", ""))
    fw, ty, pt = (f.get(k, "").strip().lower() for k in ("fw", "ty", "pt"))
    rows = []
    for d in docs.values():
        p = pdate(d.get("Distributed Date"))
        if ((a or b) and not p) or (a and p < a) or (b and p > b):
            continue
        if (fw and str(d.get("Forward To", "")).strip().lower() != fw) \
                or (ty and str(d.get("Invoice Type", "")).strip().lower() != ty) \
                or (pt and str(d.get("Payment Terms", "")).strip().lower() != pt):
            continue
        rows.append(d)
    if not rows:
        return {"ok": False, "msg": "No invoices match these values."}
    fwn = f.get("fw", "")
    path = unique_path(os.path.join(desktop(), re.sub(r'[\\/:*?"<>|\s]+', "_",
                                                      f"HeadOffice_{fwn or 'ALL'}_{dt.date.today():%d-%m-%Y}.pdf")))
    try:
        core.make_ho_pdf(path, fwn, rows)
        open_file(path)
    except Exception as e:
        return {"ok": False, "msg": f"PDF error: {e}"}
    return {"ok": True, "msg": f"Saved on Desktop: {os.path.basename(path)}"}


def pdf_list(title, crit, uids, save_only=False):
    if not uids:
        return {"ok": False, "msg": "Nothing to save."}
    name = re.sub(r"\W+", "_", title)
    path = unique_path(os.path.join(desktop(), f"{name}_{time.strftime('%H%M%S')}.pdf"))
    try:
        core.make_list_pdf(path, title, crit, [docs[u] for u in uids])
    except Exception as e:
        return {"ok": False, "msg": f"PDF error: {e}"}
    if save_only:
        return {"ok": True, "msg": f"Saved on Desktop: {os.path.basename(path)}"}
    ok = print_file(path, 1)
    return {"ok": True, "msg": f"Saved on Desktop: {os.path.basename(path)}"
                               + (" - sent to printer" if ok else " - press Ctrl+P to print")}


def wh_sorted():
    return sorted(wh_rows.items(), key=lambda x: core.arrival_key(x[0]), reverse=True)


def warehouse_history(kind, number):
    """Read-only document history, includes all completion/print states."""
    if kind not in ("so", "invoice"):
        return {"ok": False, "msg": "Choose a document tab."}
    number = str(number or "").strip()
    if not number:
        return {"ok": False, "msg": "Enter a document number to search history."}
    key = "so" if kind == "so" else "inv"
    with core.LOCK, STATE_LOCK:
        reload_data()
        selected = wh_rows if kind == "so" else pinv_rows
        exact = [dict(row) for row in selected.values() if norm(row.get(key, "")) == norm(number)]
        found = exact
        if not found and re.fullmatch(r"[0-9]+", number):
            wanted = number.lstrip("0") or "0"
            found = [dict(row) for row in selected.values()
                     if re.search(r"([0-9]+)$", str(row.get(key, "")).strip())
                     and (re.search(r"([0-9]+)$", str(row.get(key, "")).strip()).group(1).lstrip("0") or "0") == wanted]
        rows = [{"number": r.get(key, ""), "customer": r.get("cu", ""),
                 "created": r.get("dt" if kind == "so" else "created", ""),
                 "printed": bool(r.get("p")), "paper_checked": bool(r.get("paper_checked")),
                 "paper_checked_by": r.get("paper_checked_by", ""),
                 "paper_checked_on": r.get("paper_checked_on", ""),
                 "paper_check_history": list(r.get("paper_check_history", []))} for r in found]
        return {"ok": True, "rows": rows, "count": len(rows),
                "msg": "Matching documents are shown below. Search the full number to narrow them." if len(rows)>1 else "Found." if rows else "Number not found in this tab."}


def paper_check(kind, number, checked, user):
    """Separate, exact existing-record paper checks. Never changes PDF/print audit."""
    if kind not in ("so", "invoice") or type(checked) is not bool:
        return {"ok": False, "msg": "Choose a valid paper-check tab and action. Nothing changed."}
    number = str(number or "").strip()
    if not number:
        return {"ok": False, "msg": "Enter a sales order number." if kind == "so" else "Enter an invoice number."}
    key, other_key = ("so", "inv") if kind == "so" else ("inv", "so")
    label = "sales order" if kind == "so" else "invoice"
    with core.LOCK, STATE_LOCK:
        reload_data()
        selected = wh_rows if kind == "so" else pinv_rows
        other = pinv_rows if kind == "so" else wh_rows
        matches = [(uid, dict(row)) for uid, row in selected.items() if norm(row.get(key, "")) == norm(number)]
        if not matches and re.fullmatch(r"[0-9]+", number):
            matches = [(uid, dict(row)) for uid, row in selected.items()
                       if re.search(r"([0-9]+)$", str(row.get(key, "")).strip())
                       and (re.search(r"([0-9]+)$", str(row.get(key, "")).strip()).group(1).lstrip("0") or "0") == (number.lstrip("0") or "0")]
            full_numbers = {str(row.get(key, "")).strip() for uid, row in matches}
            if len(full_numbers) > 1:
                candidates = []
                for full_number in sorted(full_numbers):
                    row = next(row for uid, row in matches if str(row.get(key, "")).strip() == full_number)
                    candidates.append({"number": full_number, "customer": row.get("cu", ""),
                                       "created": row.get("dt" if kind == "so" else "created", ""),
                                       "checked": bool(row.get("paper_checked", False))})
                return {"ok": False, "choose": True, "candidates": candidates,
                        "msg": "More than one " + label + " has numeric ending " + number + ". Choose the full number. Nothing was marked."}
            if matches:
                number = next(iter(full_numbers))
        if not matches:
            wrong = any(norm(row.get(other_key, "")) == norm(number) for row in other.values())
            return {"ok": False, "msg": ("That number belongs to the other tab. " if wrong else "Number not found in this tab. ") + "Enter an existing " + label + " number. Nothing was marked."}
        now, stamp, changed = time.time(), now_str(), []
        for uid, row in matches:
            if bool(row.get("paper_checked", False)) == checked:
                continue
            history = list(row.get("paper_check_history", []))
            history.append({"checked": checked, "by": user, "on": stamp, "at": now})
            row.update(paper_checked=checked, paper_checked_by=user, paper_checked_on=stamp,
                       paper_check_history=history, updated=now)
            changed.append((uid, row))
        if changed:
            db_put(changed, 1, 1)
            reload_data(); bump(); sync_now.set(); request_cloud()
        return {"ok": True, "duplicate": checked and not changed, "changed": len(changed), "checked": checked, "number": number,
                "msg": ("Paper checked" if checked else "Paper check removed") + " for " + label + " " + number + (". Saved locally; sync pending." if changed else (". This number was already entered before; nothing changed." if checked else ". This paper check was already removed; nothing changed."))}


def mark_docs_printed(col, values, key_field):
    """Set col='Printed' on invoice records whose key_field is in values (batch, syncs like any edit).
    Returns the count actually changed. Print statuses are audit fields: only set once, never cleared here."""
    want = {str(v).strip().lower() for v in values if str(v).strip()}
    if not want:
        return 0
    items = []
    for u, d in docs.items():
        if str(d.get(key_field, "")).strip().lower() in want and str(d.get(col, "")).strip() != "Printed":
            n = dict(d)
            n[col] = "Printed"
            n["updated"] = time.time()
            items.append((u, n))
    if items:
        db_put(items, 1, 1)
        docs.update(dict(items))
        bump()
        sync_now.set(); request_cloud()
    return len(items)


def wh_print(everything, user, save_only=False):
    rows = [(u, r) for u, r in wh_sorted() if everything or not r.get("p")]
    if not rows:
        return {"ok": False, "msg": "No new rows to print."}
    # Capture the exact rows and linked invoice versions before generating this PDF.
    rows=[(uid,dict(record)) for uid,record in rows]
    captured_invoices={uid:dict(record) for uid,record in docs.items()
                       if norm(record.get("Sales Order No","")) in {norm(row["so"]) for _,row in rows}}
    if save_only:
        # Verified local export: no printer call; status changes only after successful write.
        path = unique_path(os.path.join(desktop(), f"warehouse_{time.strftime('%Y%m%d_%H%M%S')}.pdf"))
    else:
        folder=os.path.join(core.DATA_DIR,"Trial_PDFs" if core.TEST_MODE else "Warehouse_PDFs")
        os.makedirs(folder,exist_ok=True)
        path=unique_path(os.path.join(folder,f"warehouse_{time.strftime('%Y%m%d_%H%M%S')}.pdf"))
    try:
        index, conflicts = warehouse_invoice_index()
        core.make_wh_pdf(path, [(r["so"], disp_date(r["dt"]), r["cu"], *warehouse_invoice_text(r, index)) for u, r in rows])
    except Exception as e:
        return {"ok": False, "msg": f"PDF error: {e}"}
    if not os.path.isfile(path) or os.path.getsize(path) < 5:
        return {"ok": False, "msg": "PDF was not saved. Print status is unchanged."}
    if not save_only:
        token=secrets.token_hex(24)
        PDF_VIEWS[token]=path
        if not everything:
            # Click-to-mark is the user's chosen audit convention, not paper confirmation.
            with core.LOCK,STATE_LOCK:
                captured=dict(rows)
                for uid,record in {**captured,**captured_invoices}.items():
                    current=q("SELECT data FROM inv WHERE uid=?",(uid,))
                    if not current or json.loads(current[0][0])!=record:
                        return {"ok":True,"pdf_url":"/api/pdf/view/"+token,"file_path":path,
                                "marked_printed":False,"msg":"PDF is ready, but records changed while it was generated. No print status was changed. Review and use Print new only again."}
                now,on=time.time(),now_str()
                updates=[]
                for uid,record in rows:
                    updates.append((uid,dict(record,p=1,on=record.get("on") or on,by=record.get("by") or user,updated=now)))
                for uid,record in captured_invoices.items():
                    if record.get("Print Status Sales Order")!="Printed":
                        updates.append((uid,dict(record,**{"Print Status Sales Order":"Printed","updated":now})))
                db_put(updates,1,1)
                reload_data();bump();sync_now.set();request_cloud()
            return {"ok":True,"pdf_url":"/api/pdf/view/"+token,"file_path":path,
                    "marked_printed":True,"msg":"Included rows marked Printed when Print new only was clicked. PDF is ready for manual printing; paper printing is not verified."}
        return {"ok":True,"pdf_url":"/api/pdf/view/"+token,"file_path":path,
                "marked_printed":False,"msg":"Reprint PDF is ready. Existing print audit is unchanged."}
    now, on, items = time.time(), now_str(), []
    for u, r in rows:
        n = dict(r, p=1, updated=now)
        if not r.get("p"):
            n["on"], n["by"] = on, user
        items.append((u, n))
    db_put(items, 1, 1)
    wh_rows.update(dict(items))
    marked = mark_docs_printed("Print Status Sales Order", [r["so"] for u, r in rows], "Sales Order No")
    bump()
    sync_now.set(); request_cloud()
    msg = f"Saved locally: {os.path.basename(path)}. Rows retained and marked Printed." if save_only else "Warehouse report sent to printer"
    if marked:
        msg += f" - {marked} invoice(s) marked Print Status Sales Order = Printed"
    return {"ok": True, "msg": msg}


def pi_filtered(f):
    day, qs = pdate(f.get("date", "")), f.get("q", "").strip().lower()
    rows = [r for uid,r in sorted(pinv_rows.items(),key=lambda x:core.arrival_key(x[0]),reverse=True)]
    return [r for r in rows if (not day or pdate(r.get("date")) == day) and (not qs or qs in r.get("inv", "").lower())]


def pi_pdf(f):
    rows = pi_filtered(f)
    if not rows:
        return {"ok": False, "msg": "Nothing to save."}
    crit = f"Printed on: {f.get('date', '').strip() or 'all days'}"
    name = re.sub(r"[^\w\-]+", "_", f"Invoices_Printed_{f.get('date', '').strip() or 'ALL'}")
    path = unique_path(os.path.join(desktop(), name + ".pdf"))
    try:
        core.make_pinv_pdf(path, crit, rows)
        if not os.path.isfile(path) or os.path.getsize(path) < 5:
            return {"ok": False, "msg": "PDF was not saved. Print status is unchanged."}
    except Exception as e:
        return {"ok": False, "msg": f"PDF error: {e}"}
    selected_ids = {id(r) for r in rows}
    changed = [(uid, dict(r, p=1, on=now_str(), date=dt.date.today().strftime("%d/%m/%Y"), updated=time.time())) for uid, r in list(pinv_rows.items()) if not r.get("p") and id(r) in selected_ids]
    if changed:
        db_put(changed, 1, 1); pinv_rows.update(dict(changed)); bump(); sync_now.set(); request_cloud()
    mark_docs_printed("Print Status Invoice", [r["inv"] for r in rows], "Invoice Number")
    return {"ok": True, "msg": f"Saved locally: {os.path.basename(path)}. Rows retained and marked Printed."}


def merge_file_payload_path(package):
    fd,path=tempfile.mkstemp(prefix="fictional_invoice_restore_",suffix=".json");os.close(fd)
    try:
        with open(path,"w") as f:json.dump(package,f)
        return merge_invoice_file(path,1)
    finally:os.remove(path)


def backup_now():
    last, now = float(meta("last_backup", 0)), time.time()
    rows = q("SELECT uid,data FROM inv WHERE updated>?", (last,))
    dels = q("SELECT uid,ts FROM dellan WHERE ts>?", (last,))
    finance_hash=localfinance.digest(localfinance.store(core.DATA_DIR).ops.operations()) if FINANCE_ENABLED else ""
    if not rows and not dels and not (FINANCE_ENABLED and finance_hash!=meta("finance_last_backup_hash", "")):
        return {"ok": True, "msg": "Nothing new since the last backup."}
    d = os.path.join(share_dir(), "backup")
    try:
        os.makedirs(d, exist_ok=True)
        fn = os.path.join(d, f"backup_{machine()}_{time.strftime('%Y%m%d_%H%M%S')}.json")
        with open(fn+".tmp", "w", encoding="utf-8") as f:
            payload={"connected_test_run":core.CONNECTED_TEST["run_id"] if core.CONNECTED_TEST else None,"from": machine(), "records": [[u, json.loads(x)] for u, x in rows], "deleted": [[u, ts] for u, ts in dels]}
            if FINANCE_ENABLED:
                fp=fn+".finance.tmp";localfinance.store(core.DATA_DIR).ops.backup(fp)
                with open(fp) as ff:payload["finance_v1"]=json.load(ff)
                os.remove(fp)
            json.dump(payload,f,ensure_ascii=False);f.flush();os.fsync(f.fileno())
        os.replace(fn+".tmp",fn)
    except Exception as e:
        return {"ok": False, "msg": str(e)}
    setmeta("last_backup", now)
    if FINANCE_ENABLED:
        setmeta("finance_last_backup_hash",finance_hash)
        return {"ok":True,"msg":f"Backup saved locally: {fn}. Includes invoice records and versioned expenses / collection marks. Finance sync: {finance_status()}."}
    return {"ok": True, "msg": f"{len(rows)} new/changed records and {len(dels)} deletions saved to:\n{fn}\n\n"
                               "The other PCs load it automatically."}


def pick_folder():
    """Native Windows 'Browse For Folder' dialog (no tkinter needed). Returns '' off Windows / cancelled."""
    if os.name != "nt":
        return ""
    try:
        import ctypes
        from ctypes import wintypes
        shell32, ole32 = ctypes.windll.shell32, ctypes.windll.ole32
        ole32.CoInitialize(None)
        BIF_RETURNONLYFSDIRS = 0x0001
        BIF_NEWDIALOGSTYLE = 0x0040

        class BROWSEINFOW(ctypes.Structure):
            _fields_ = [("hwndOwner", wintypes.HWND), ("pidlRoot", wintypes.LPVOID),
                        ("pszDisplayName", wintypes.LPWSTR), ("lpszTitle", wintypes.LPCWSTR),
                        ("ulFlags", wintypes.UINT), ("lpfn", wintypes.LPVOID),
                        ("lParam", wintypes.LPARAM), ("iImage", ctypes.c_int)]

        buf = ctypes.create_unicode_buffer(260)
        bi = BROWSEINFOW(ctypes.windll.user32.GetForegroundWindow(), None, buf, "Choose the shared network folder",
                         BIF_RETURNONLYFSDIRS | BIF_NEWDIALOGSTYLE | 0x10, None, 0, 0)
        pidl = shell32.SHBrowseForFolderW(ctypes.byref(bi))
        if not pidl:
            return ""
        out = ctypes.create_unicode_buffer(260)
        shell32.SHGetPathFromIDListW(pidl, out)
        ole32.CoTaskMemFree(pidl)
        return out.value
    except Exception:
        return ""


# ---------------- HTTP layer ----------------
def jdump(o):
    return json.dumps(o, ensure_ascii=False).encode("utf-8")


LIST_NAMES = lambda: sorted(set(LIST_FIELDS.values()) | {"customer_district"})
NEW_REQUIRED = ["Invoice Number", "Invoice Status", "District", "Forward To", "Invoice Type", "Payment Terms",
                "Brand Name"]
BULK_FIELDS = ["Invoice Status", "District", "Forward To", "Invoice Type", "Payment Terms", "Brand Name", "Car No",
               "Driver name", "Distribution Rep", "Distribution Rep1", "Distributed Date", "Line"]


class Hdl(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    # ---- plumbing ----
    def send_j(self, o, code=200):
        b = jdump(o)
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b)

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > 200 * 1024 * 1024:
            raise ValueError("body too large")
        return json.loads(self.rfile.read(n).decode("utf-8") or "{}")

    def user(self):
        c = self.headers.get("Cookie", "")
        m = re.search(r"dprogram=([0-9a-f]{32})", c)
        if not m:return None
        token=m.group(1)
        if token in AUTO_SESSION_EXPIRY:
            automatic=trial_autologin.status(SETTINGS,[r[0]for r in q("SELECT name FROM usr")])
            if time.time()>=AUTO_SESSION_EXPIRY[token] or not automatic["enabled"] or automatic['program_user']!=SESSIONS.get(token):
                SESSIONS.pop(token,None);AUTO_SESSION_EXPIRY.pop(token,None);return None
        user=SESSIONS.get(token)
        return user if user and q("SELECT 1 FROM usr WHERE name=?",(user,)) else None

    MIME = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8", ".png": "image/png", ".ico": "image/x-icon"}

    def local_only(self):
        """Security: answer only requests that really come to this PC's own address (blocks DNS-rebinding and other websites calling the program)."""
        host = self.headers.get("Host", ""); origin = self.headers.get("Origin", "")
        if not re.fullmatch(r"(127\.0\.0\.1|localhost)(:\d+)?", host):
            self.send_j({"ok": False, "msg": "Local requests only."}, 403); return False
        if origin and origin != "http://" + host:
            self.send_j({"ok": False, "msg": "Local same-origin request required."}, 403); return False
        return True

    def do_GET(self):
        if not self.local_only(): return
        pth = "/index.html" if self.path == "/" else self.path.split("?")[0]
        if pth.startswith("/static/") or pth == "/index.html":
            name = pth[len("/static/"):] if pth.startswith("/static/") else "index.html"
            if re.fullmatch(r"[\w.\-]+", name):
                p = os.path.join(HERE, "static", name)
                if os.path.isfile(p):
                    b = open(p, "rb").read()
                    self.send_response(200)
                    self.send_header("Content-Type", self.MIME.get(os.path.splitext(name)[1], "application/octet-stream"))
                    self.send_header("Content-Length", str(len(b)))
                    self.end_headers()
                    self.wfile.write(b)
                    return
        if pth.startswith("/api/pdf/view/"):
            if not self.user():return self.send_j({"ok":False,"msg":"Sign in to view this PDF."},401)
            token=pth.removeprefix("/api/pdf/view/")
            path=PDF_VIEWS.get(token) if re.fullmatch(r"[0-9a-f]{48}",token) else None
            if not path or not os.path.isfile(path):return self.send_j({"ok":False,"msg":"PDF link is unavailable. Use its saved file path or generate it again."},404)
            with open(path,"rb") as file:content=file.read()
            self.send_response(200)
            self.send_header("Content-Type","application/pdf")
            self.send_header("Content-Disposition",'inline; filename="'+os.path.basename(path)+'"')
            self.send_header("Content-Length",str(len(content)))
            self.send_header("Cache-Control","private, no-store")
            self.send_header("X-Content-Type-Options","nosniff")
            self.end_headers();self.wfile.write(content);return
        if self.path == "/api/instance":
            import desktop_app
            self.send_j({"application": "Distribution Program", "instance": desktop_app.INSTANCE, "trial": core.TEST_MODE, "version": VERSION})
            return
        if self.path == "/api/status":
            u = self.user()
            lb = float(meta("last_backup", 0) or 0)
            last_backup = ("manual " + time.strftime("%d/%m/%Y %H:%M", time.localtime(lb))) if lb else ""
            auto = meta("auto_bk", "")
            if auto:
                last_backup = (last_backup + "  |  " if last_backup else "") + f"auto {auto[6:8]}/{auto[4:6]}/{auto[:4]}"
            self.send_j({"logged": bool(u), "scope": "REPLICA" if core.REPLICA else "MAIN", "user": u, "lan": st_lan, "cloud": st_cloud, "test_mode": core.TEST_MODE, "trial_limit": core.TRIAL_LIMIT, "lic": lic_info(), "trial_printing":core.TRIAL_PRINTING, "connected_test":core.CONNECTED_TEST,"finance_enabled":FINANCE_ENABLED,"finance_sync":finance_status(), "sync_conflicts": q("SELECT count(*) FROM sync_conflicts")[0][0],
                         "v": data_version, "version": VERSION, "company": COMPANY, "title": LOGIN_TITLE, "received": dict(CLOUD_SYNC.recv), "connection": cloud_connection(), "usage": core.CLOUD_USAGE.status(), "project_usage": PROJECT_USAGE.status(),
                         "credit": CREDIT, "signature": SIGNATURE, "last_backup": last_backup,
                         "customer_mode": __import__("customer").active(sys.modules[__name__]), "customer_login": __import__("customer").login_required(sys.modules[__name__]), "users": ([] if (core.TRIAL_LIMIT and not __import__("customer").active(sys.modules[__name__])) else [r[0] for r in q("SELECT name FROM usr ORDER BY name")])})
            return
        if self.path == "/api/state":
            u = self.user()
            if not u:
                return self.send_j({"ok": False, "auth": True}, 401)
            self.send_j({"ok": True, "user": u, "permissions":access_control.get(core,u), "is_admin":access_control.is_admin(u), "fb_tools":__import__("firebase_tools").allowed(u), "version": VERSION, "test_mode": core.TEST_MODE, "trial_limit": core.TRIAL_LIMIT, "lic": lic_info(), "trial_printing":core.TRIAL_PRINTING, "credit": CREDIT, "signature": SIGNATURE,
                         "company": COMPANY, "title": LOGIN_TITLE, "connected_test":core.CONNECTED_TEST,"finance_enabled":FINANCE_ENABLED,"finance_sync":finance_status(), "mode": SETTINGS.get("mode", "light"),
                         "statuses": STATUSES, "cols": COLS, "base": BASE, "locked": sorted(LOCKED),
                         "editable": sorted(EDITABLE), "rgr_cols": RGR_COLS, "rep_cols": REP_COLS,
                         "list_fields": LIST_FIELDS, "date_cols": sorted(DATE_COLS), "exempt": sorted(EXEMPT),
                         "bulk_fields": BULK_FIELDS, "required": NEW_REQUIRED,
                         "lists": {k: get_list(k) for k in set(LIST_FIELDS.values()) | {"customers", "district"}},
                         "cd_map": dict(CD_MAP),
                         "list_names": LIST_NAMES(), "share": share_dir(),
                         "customer_mode": __import__("customer").active(sys.modules[__name__]), "users": ([] if (core.TRIAL_LIMIT and not __import__("customer").active(sys.modules[__name__])) else [r[0] for r in q("SELECT name FROM usr ORDER BY name")]),
                         "forward_to": get_list("forward_to"), "invoice_type": get_list("invoice_type"),
                         "payment_terms": get_list("payment_terms")})
            return
        self.send_j({"ok": False, "msg": "not found"}, 404)

    def do_POST(self):
        if not self.local_only(): return
        try:
            path = self.path
            if path in {"/api/trial-autologin/status","/api/trial-autologin/start","/api/trial-autologin/enable","/api/trial-autologin/disable"}:
                self.body_value = self.body()
                host=self.headers.get('Host','');origin=self.headers.get('Origin','')
                if not (host.startswith('127.0.0.1:')or host.startswith('localhost:'))or origin!='http://'+host:
                    return self.send_j({'ok':False,'msg':'Local same-origin request required'},403)
                users=[r[0]for r in q("SELECT name FROM usr")]
                if path.endswith('/enable'):
                    user=self.user()
                    if not user:return self.send_j({'ok':False,'auth':True},401)
                    try:answer=trial_autologin.enable(SETTINGS,user,users,self.body_value.get('minutes',60));save_settings()
                    except ValueError as error:return self.send_j({'ok':False,'msg':str(error)})
                    return self.send_j({'ok':True,**answer})
                if path.endswith('/disable'):
                    if not self.user():return self.send_j({'ok':False,'auth':True},401)
                    trial_autologin.disable(SETTINGS);save_settings();return self.send_j({'ok':True})
                answer=trial_autologin.status(SETTINGS,users)
                if path.endswith('/start') and self.user():
                    return self.send_j({'ok':True,'already_logged_in':True,'program_user':self.user()})
                if path.endswith('/status'):return self.send_j({'ok':True,**answer})
                if not answer['enabled']:return self.send_j({'ok':False,'msg':'Temporary auto-login is off or expired.'})
                token=secrets.token_hex(16);SESSIONS[token]=answer['program_user'];AUTO_SESSION_EXPIRY[token]=answer['expires_at']
                body=jdump({'ok':True,**answer});self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.send_header('Set-Cookie','dprogram='+token+'; Path=/; SameSite=Strict; HttpOnly; HttpOnly');self.end_headers();self.wfile.write(body);return
            if path == "/api/trial/start":
                if not core.TEST_MODE:
                    return self.send_j({"ok": False, "msg": "Trial entry is unavailable in normal mode."}, 403)
                self.body()
                if __import__("customer").login_required(sys.modules[__name__]):
                    return self.send_j({"ok": False, "msg": "Sign in with your own user name and password."}, 403)
                token = secrets.token_hex(16)
                SESSIONS[token] = ("Guest" if core.TRIAL_LIMIT else "ADMIN")
                data = jdump({"ok": True, "test_mode": True})
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Set-Cookie", f"dprogram={token}; Path=/; SameSite=Strict; HttpOnly")
                self.end_headers()
                self.wfile.write(data)
                return
            if path == "/api/login":
                b = self.body()
                if core.TRIAL_LIMIT and b.get("user", "").strip().upper() in ("ADMIN", "GUEST"):
                    return self.send_j({"ok": False, "msg": "Wrong user or password"}, 401)
                r = q("SELECT name,pw FROM usr WHERE upper(name)=upper(?)", (b.get("user", "").strip(),))
                if len(r)==1 and access_control.verify(b.get("pw", ""),r[0][1]):
                    t = secrets.token_hex(16)
                    SESSIONS[t] = r[0][0]
                    bts = jdump({"ok": True, "user": r[0][0]})
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(bts)))
                    self.send_header("Set-Cookie", f"dprogram={t}; Path=/; SameSite=Strict; HttpOnly")
                    self.end_headers()
                    self.wfile.write(bts)
                else:
                    self.send_j({"ok": False, "msg": "Wrong user or password"}, 401)
                return
            u = self.user()
            if not u:
                return self.send_j({"ok": False, "auth": True}, 401)
            b = self.body()
            ACTOR.user = u
            r = self.route(path, b, u)
            self.send_j(r if isinstance(r, dict) else {"ok": True})
        except Exception as e:
            try:
                self.send_j({"ok": False, "msg": (str(e)[str(e).index("Trial version limit"):] if "Trial version limit" in str(e) else f"{type(e).__name__}: {e}")}, 500)
            except Exception:
                pass

    def route(self, path, b, u):   # every action below maps 1:1 to a desktop-program feature
        global cloud_now,sys
        if path=="/api/access/view":
            key=access_control.view_key(b.get("view",""))
            return {"ok":key is None or key in access_control.get(core,u),"msg":"This Home button is not allowed for your user."}
        if path=="/api/users/permissions/get":
            if not access_control.is_admin(u):return {"ok":False,"msg":"Only ADMIN can manage permissions."}
            name=b.get("name","")
            if not q("SELECT 1 FROM usr WHERE name=?",(name,)):return {"ok":False,"msg":"User not found."}
            return {"ok":True,"allowed":access_control.get(core,name),"admin":access_control.is_admin(name),"revision":access_control.revision(core,name),"buttons":access_control.BUTTONS}
        if path=="/api/users/permissions/set":return access_control.save(sys.modules[__name__],u,b.get("name",""),b.get("allowed"),b.get("revision",0))
        needed=access_control.required(path,b)
        if needed and not any(x in access_control.get(core,u) for x in needed):return {"ok":False,"msg":"Access denied for your user."}
        if core.CONNECTED_TEST and not core.REPLICA and path.startswith('/api/import/'):
            return {"ok":False,"msg":"Connected test accepts manual TEST- invoices only, not real imports."}
        if core.CONNECTED_TEST and not core.REPLICA and path=='/api/new' and not str(b.get('fields',{}).get('Invoice Number','')).startswith('TEST-'):
            return {"ok":False,"msg":"Connected test invoice number must start TEST-."}
        if core.CONNECTED_TEST and not core.REPLICA and path=='/api/backup/load':
            try:
                package=json.loads(base64.b64decode(b.get('file','')))
                if package.get('connected_test_run')!=core.CONNECTED_TEST['run_id']:return {"ok":False,"msg":"Backup is outside this connected-test run."}
            except Exception:return {"ok":False,"msg":"Invalid connected-test backup."}
        if core.CONNECTED_TEST and not core.REPLICA and path in {"/api/share/set","/api/share/pick","/api/desktop/shortcut"}:return {"ok":False,"msg":"Connected test path/shortcut is fixed. No work-profile change allowed."}
        if path == "/api/license/status": return lic_info()
        if path == "/api/license/activate":
            import license_mgr
            if core.TRIAL_LIMIT and not access_control.is_admin(u): return {"ok": False, "msg": "Entering a license needs the administrator. Press Switch user and sign in as Admi1."}
            return license_mgr.activate(core, b.get("key", ""))
        if path.startswith("/api/drvdel/"):
            import drvdel,sys
            if (core.TEST_MODE or core.TRIAL_LIMIT) and not lic_full(): return {"ok":False,"msg":"Not available in the trial."}
            dd_list,dd_driver,dd_check=drvdel.install(sys.modules[__name__])
            if path=="/api/drvdel/list":return dd_list()
            if path=="/api/drvdel/driver":return dd_driver(b.get("driver"))
            if path=="/api/drvdel/check":return dd_check(b.get("driver"),b.get("number"),u)
            return {"ok":False,"msg":"Unknown action."}
        if path.startswith("/api/review/"):
            import reviewplans,sys
            plans,open_plan,save=reviewplans.install(sys.modules[__name__])
            if path=="/api/review/plans":return {"ok":True,"plans":plans()}
            if path=="/api/review/open":return open_plan(b.get("key"))
            if path=="/api/review/save":return save(b,u)
        if path == "/api/delivery/batch":
            ids=b.get("uids",[]);allowed={"Invoice Status","Car No","Driver name","Distribution Rep","Distributed Date","Line"}
            changes={k:str(v).strip() for k,v in b.get("changes",{}).items() if k in allowed and str(v).strip()}
            if not ids or len(set(ids))!=len(ids) or not changes:return {"ok":False,"msg":"Select invoices and enter changes."}
            if changes.get("Invoice Status","Undelivered") not in {"Undelivered","inprocess","Proposal"}:return {"ok":False,"msg":"Invalid dispatch status."}
            if "Distributed Date" in changes:
                try:changes["Distributed Date"]=core.manual_date_text(changes["Distributed Date"])
                except ValueError:return {"ok":False,"msg":"Invalid Distributed Date. Nothing changed."}
            with core.LOCK:
                for uid in ids:
                    d=docs.get(uid)
                    if not d or d.get("Invoice Status")!="Undelivered" or d.get("updated")!=b.get("expected",{}).get(uid):return {"ok":False,"msg":"An invoice changed since selection. Refresh and select again. Nothing changed."}
                for uid in ids:save_doc(uid,dict(docs[uid],**changes))
            return {"ok":True,"msg":str(len(ids))+" selected invoices updated."}
        if path == "/api/desktop/shortcut":
            import desktop_app
            return desktop_app.create_shortcut(core.TEST_MODE)
        if path in ("/api/app/exit/start","/api/app/exit/status"):
            global EXIT_FLOW
            if EXIT_FLOW is None:
                import exitflow,sys
                EXIT_FLOW=exitflow.ExitFlow(sys.modules[__name__])
            return {"ok":True,**(EXIT_FLOW.start() if path.endswith('/start') else EXIT_FLOW.get())}
        if path.startswith("/api/update/"):
            if not access_control.is_admin(u):return {"ok":False,"msg":"Only ADMIN can update the program."}
            import updater
            a=path[len("/api/update/"):]
            if core.TRIAL_LIMIT:
                _li=lic_info()
                if not (_li.get("licensed") and not _li.get("readonly") and not _li.get("tampered")):return {"ok":False,"msg":"Updates need a valid license. Open Settings > License to enter or renew it, or download the newest version from the official website."}
            try:
                if a=="status":return {"ok":True,"version":VERSION,"installed":updater.installed_tag(),**updater.status()}
                if a=="check":return {"ok":True,"running":VERSION,**updater.check(core.DATA_DIR)}
                if a=="apply":return updater.apply(core.DATA_DIR,b.get("fail_after") if os.environ.get("DPROGRAM_UPDATE_TEST")=="1" else None)
                if a=="rollback":return updater.rollback()
                if a=="restart":
                    if os.environ.get("DPROGRAM_UPDATE_TEST")!="1":
                        global RESTARTING
                        RESTARTING=True;updater.spawn_restart()
                        import desktop_app
                        threading.Timer(0.3,desktop_app.close_window).start()
                    threading.Timer(0.8,self.server.shutdown).start()
                    return {"ok":True}
            except (ValueError,OSError) as e:return {"ok":False,"msg":str(e)}
            return {"ok":False,"msg":"unknown action"}
        if path == "/api/app/quit":
            threading.Timer(0.3, self.server.shutdown).start()
            return {"ok": True}
        if path == "/api/drafts/get":
            prefix="input_draft:" + u + ":"
            rows=q("SELECT k,v FROM meta WHERE substr(k,1,?)=?", (len(prefix),prefix))
            return {"ok":True,"drafts":{k[len(prefix):]:json.loads(v) for k,v in rows}}
        if path == "/api/drafts/set":
            key=str(b.get("key", ""));entry=b.get("entry")
            if not key or len(key)>180 or not isinstance(entry,dict) or not isinstance(entry.get("updated"),(int,float)):
                return {"ok":False,"msg":"Invalid local draft"}
            if len(json.dumps(entry))>8000000:return {"ok":False,"msg":"Draft too large"}
            name="input_draft:" + u + ":" + key
            with core.LOCK:
                old=meta(name, "")
                if not old or float(json.loads(old).get("updated",0))<=float(entry["updated"]):setmeta(name,json.dumps(entry,ensure_ascii=False))
            return {"ok":True,"local_only":True}
        if path == "/api/sync/conflicts/resolve":
            cid = int(b.get("id", 0) or 0); keep = b.get("keep", "")
            rows = q("SELECT kind,key,data FROM sync_conflicts WHERE id=?", (cid,))
            if not rows: return {"ok": False, "msg": "This item was already cleared."}
            kind, uid, raw = rows[0]
            if keep not in ("was", "became", "reject"): return {"ok": False, "msg": "Choose which version to keep."}
            if keep == "was":
                if kind not in ("invoice_equal_timestamp", "invoice", "lan_previous_version") or uid not in docs:
                    return {"ok": False, "msg": "This version cannot be put back here."}
                if q("SELECT 1 FROM dellan WHERE uid=?", (uid,)): return {"ok": False, "msg": "This invoice is deleted here."}
                d = {k: v for k, v in json.loads(raw).items() if k != "updated"}
                save_doc(uid, d)   # a normal new save: newest timestamp, syncs like any edit
            if keep == "reject":
                gone = kind not in ("list", "list_equal_timestamp") and uid in docs
                if gone: delete_uids([uid], u)   # same delete as the Delete button: tombstone syncs to Firebase and the other PCs
                q("DELETE FROM sync_conflicts WHERE key=?", (uid,))
                q("DELETE FROM sync_conflicts WHERE id=?", (cid,))
                return {"ok": True, "msg": "Rejected. The invoice was deleted everywhere." if gone else "Rejected. The item was removed."}
            q("DELETE FROM sync_conflicts WHERE id=?", (cid,))
            return {"ok": True, "msg": "Saved version put back and sent to the other PCs." if keep == "was" else ("Rejected. The item was removed, nothing changed." if keep == "reject" else "Kept the version now in the program.")}
        if path == "/api/sync/conflicts":
            rows = q("SELECT id,kind,key,data,recorded FROM sync_conflicts ORDER BY id DESC LIMIT 100")
            def cur(k):
                x = q("SELECT data FROM inv WHERE uid=?", (k,))
                return json.loads(x[0][0]) if x else None
            return {"ok": True, "conflicts": [{"id": r[0], "kind": r[1], "key": r[2], "data": json.loads(r[3]), "recorded": r[4],
                                               "current": cur(r[2]) if r[1] not in ("list", "list_equal_timestamp") else None,
                                               "deleted_here": bool(q("SELECT 1 FROM dellan WHERE uid=?", (r[2],)))} for r in rows]}
        if core.TEST_MODE and path in {"/api/share/set", "/api/share/pick", "/api/backup/load"}:
            return {"ok": False, "msg": "ISOLATED TRIAL: real shared folders and backup restore are disabled."}
        if FINANCE_ENABLED and path == "/api/backup/load":
            try:
                package=json.loads(base64.b64decode(b.get("file","")))
            except Exception:package={}
            if "finance_v1" in package:
                fs=localfinance.store(core.DATA_DIR);fd,fp=tempfile.mkstemp(prefix="fictional_restore_",suffix=".json");os.close(fd)
                try:
                    with open(fp,"w") as ff:json.dump(package["finance_v1"],ff)
                    # Validate finance in a disposable store before merging any invoice records.
                    check=localfinance.Finance(":memory:")
                    try:check.ops.restore(fp);check.ledger()
                    finally:check.ops.db.close()
                    with core.LOCK,fs.lock,fs.ops.lock:
                        journal=restorejournal.CombinedRestore(core.DATA_DIR,core.cx,fs.ops.db)
                        def apply_restore():
                            n=merge_file_payload_path(package);fs.ops.restore(fp);return n
                        n=journal.run(apply_restore)
                    reload_data();finance_wake()
                    return {"ok":True,"msg":f"{n} invoice records loaded. Finance revisions merged locally. Upload and other-PC receipt are separate."}
                except Exception as e:return {"ok":False,"msg":str(e)}
                finally:os.remove(fp)
        if path=="/api/backup/load" and not FINANCE_ENABLED:
            try:
                if "finance_v1" in json.loads(base64.b64decode(b.get("file",""))):return {"ok":False,"msg":"Finance history present. Enable approved finance rollout before loading this backup."}
            except Exception:pass
        if core.TEST_MODE and path in {"/api/share/set", "/api/share/pick", "/api/backup/load"}:
            return {"ok": False, "msg": "ISOLATED TRIAL: real shared folders and backup restore are disabled."}
        if path == "/api/logout":
            c = self.headers.get("Cookie", "")
            m = re.search(r"dprogram=([0-9a-f]{32})", c)
            SESSIONS.pop(m.group(1), None) if m else None
            if m:AUTO_SESSION_EXPIRY.pop(m.group(1),None)
            trial_autologin.disable(SETTINGS);save_settings()
            return {"ok": True}
        if core.CONNECTED_TEST and not core.REPLICA and path in {"/api/share/set","/api/share/pick","/api/desktop/shortcut"}:return {"ok":False,"msg":"Connected test path/shortcut is fixed. No work-profile change allowed."}
        if path == "/api/theme":
            SETTINGS["mode"] = "dark" if b.get("mode") == "dark" else "light"
            save_settings()
            return {"ok": True}
        if path == "/api/sync":
            seq = pull_done
            manual_sync()
            if FINANCE_SERVICE:FINANCE_SERVICE.request()
            return {"ok": True, "seq": seq}
        if FINANCE_ENABLED and path.startswith("/api/finance/"):
            fs=localfinance.store(core.DATA_DIR)
            try:
                a=path[len("/api/finance/"):]
                if a=="conflicts":return {"ok":True,"conflicts":fs.conflicts()}
                if a=="reject":return fs.reject(b.get("entity"),b.get("expected",[]),u,b.get("request_id") or uuid.uuid4().hex)
                if a=="resolve":return fs.resolve(b.get("entity"),b.get("pick"),b.get("expected",[]),u,b.get("request_id") or uuid.uuid4().hex)
                if a=="mark":
                    uid=b.get("uid")
                    if uid not in docs or "cash" not in str(docs[uid].get("Payment Terms","")).lower():return {"ok":False,"msg":"Cash invoice not found."}
                    return fs.mark(uid,b.get("state"),u,b.get("request_id") or uuid.uuid4().hex,b.get("expected",[]))
            except (ValueError,KeyError) as e:return {"ok":False,"msg":str(e)}
        if path.startswith("/api/exp/"):
            xs = expenses.store(core.DATA_DIR)
            try:
                a = path[9:]
                if FINANCE_ENABLED:
                    fs=localfinance.store(core.DATA_DIR)
                    request=b.get("request_id") or uuid.uuid4().hex
                    if a=="ledger":return {"ok":True,**fs.ledger(),"finance_sync":finance_status()}
                    if a=="add":return fs.write(b.get("entry",{}),u,request)
                    if a=="edit":return fs.write(b.get("entry",{}),u,request,b.get("entry_id"),b.get("reason",""),b.get("expected"))
                    if a=="void":return fs.void(b.get("entry_id"),u,request,b.get("reason",""),b.get("expected"))
                    if a=="history":return {"ok":True,"revisions":fs.history("entry:"+b.get("entry_id",""))}
                    if a=="setting":return fs.setting(b.get("key"),b.get("value"),b.get("effective_from"),u,request,b.get("expected"))
                if a == "ledger": return {"ok": True, **expenses.ledger(xs)}
                if a == "add": return expenses.add(xs, b.get("entry", {}), u)
                if a == "edit": return expenses.edit(xs, b.get("entry_id", ""), b.get("entry", {}), u, b.get("reason", ""))
                if a == "void": return expenses.void(xs, b.get("entry_id", ""), u, b.get("reason", ""))
                if a == "history": return {"ok": True, "revisions": expenses.history(xs, b.get("entry_id", ""))}
                if a == "setting": return expenses.set_cfg(xs, b.get("key", ""), b.get("value", ""), b.get("effective_from", ""), u)
            except (ValueError,KeyError) as e:
                return {"ok": False, "msg": str(e)}
            return {"ok": False, "msg": "Unknown expense action."}
        if path.startswith("/api/fb/"):
            import firebase_tools as fbt
            if (core.TEST_MODE or core.TRIAL_LIMIT) and not lic_full(): return {"ok": False, "msg": "Not available in the trial."}
            if not fbt.allowed(u): return {"ok": False, "msg": "Only Admi1 can use this."}
            a = path[8:]
            if a == "status": return fbt.status()
            if a == "signin": return fbt.enable_signin()
            if a == "rules_text": return {"ok": True, "text": fbt.rules_text(b.get("admin_uid") or None)}
            if a == "rules_publish": return fbt.publish_rules(b.get("admin_uid") or None)
            if a == "rules_restore": return fbt.restore_rules()
            if a == "drivers": return fbt.drivers_list()
            if a == "driver_add": return fbt.driver_add(b)
            if a == "driver_edit": return fbt.driver_edit(b)
            if a == "driver_disable": return fbt.driver_set_disabled(b.get("uid"), bool(b.get("disabled")))
            if a == "driver_reset": return fbt.driver_reset(b.get("uid"), b.get("pw1"), b.get("pw2"))
            if a == "driver_delete": return fbt.driver_delete(b.get("uid"))
            if a == "open_folder":
                try:
                    import os as _o; _o.startfile(_o.path.dirname(_o.path.abspath(core.CREDENTIAL_PATH)))
                    return {"ok": True}
                except Exception as e: return {"ok": False, "msg": str(e)[:100]}
            return {"ok": False, "msg": "Unknown action."}
        if path == "/api/delivery/review":
            return delivery_followup(b.get("view", "district"))
        if path == "/api/delivery/extend":
            return delivery_extend(b.get("uid"), b.get("days"), b.get("note"), u, b.get("expected"), b.get("request_id"))
        if path == "/api/district/remaining":
            return district_remaining(b.get("uids", []))
        if path == "/api/review/cash":
            return cash_receipt_review()
        if path == "/api/usage/baseline":
            try:return {"ok":True,"project_usage":PROJECT_USAGE.set_manual(b)}
            except (ValueError,TypeError) as e:return {"ok":False,"msg":str(e)}
        if path == "/api/sync/status":
            return dict(sync_state(b.get("batch")), ok=True)
        if path == "/api/import/preview":
            return import_plan(base64.b64decode(b.get("file", "")))
        if path == "/api/import/commit":
            return import_commit(base64.b64decode(b.get("file", "")), u, b.get("request_id", ""), b.get("expect_new", 0), b.get("existing", []), b.get("new_fixes", {}), b.get("skip_rows", []))

        # ---- invoice queries ----
        if path == "/api/query/details":
            snapshot = docs.copy()
            return sheet_payload(details_rows(b.get("flt"), b.get("f", {}), snapshot), COLS, snapshot)
        if path == "/api/query/rgr":
            snapshot = docs.copy()
            return sheet_payload(rgr_rows(b.get("f", {}), snapshot), RGR_COLS, snapshot)
        if path == "/api/query/route":
            snapshot = docs.copy()
            uids = route_uids(b.get("rep", "Proposal"), b.get("f", {}), snapshot)
            p = sheet_payload(uids, REP_COLS, snapshot)
            p["ready"] = len(uids)
            return p
        if path == "/api/query/wh":
            index, conflicts = warehouse_invoice_index()
            all_rows = wh_sorted()
            linked = sum(bool(index.get(norm(r["so"]))) for _, r in all_rows)
            return {"ok": True, "rows": [[r["so"], disp_date(r["dt"]), r["cu"], "Printed" if r.get("p") else "",
                                          r.get("on", ""), r.get("by", ""), *warehouse_invoice_text(r, index), bool(r.get("paper_checked", False))] for _, r in all_rows],
                    "total": len(all_rows), "not_printed": sum(1 for _, r in all_rows if not r.get("p")),
                    "invoice_linked": linked, "invoice_unmatched": len(all_rows)-linked,
                    "invoice_conflicts": sum(norm(r["so"]) in conflicts for _, r in all_rows)}
        if path == "/api/query/pi":
            rows = pi_filtered(b.get("f", {}))
            who = sorted({r.get("by", "") for r in rows if r.get("by")})
            return {"ok": True, "rows": [[r["inv"], r.get("so", ""), r.get("cu", ""), disp_date(r.get("created", "")), "Printed" if r.get("p") else "", r.get("on", ""), r.get("by", ""), bool(r.get("paper_checked", False))] for r in rows],
                    "count": len(rows), "who": who}

        # ---- editing ----
        if path == "/api/notify":
            return notify_list(u)
        if path == "/api/notify/seen":
            return notify_seen(u, b.get("ids", []))
        if path == "/api/edit/all":
            return apply_invoice_changes(b.get("uid", ""), b.get("changes", {}), b.get("reason", ""))
        if path == "/api/edit":
            if b["uid"] not in docs:
                return {"ok": False, "msg": "Row no longer exists."}
            if b["name"] in LOCKED:
                return {"ok": False, "msg": f"'{b['name']}' is locked - it comes from the system"}
            if b["name"] not in EDITABLE:
                return {"ok": False, "msg": "This column is not editable."}
            return set_field(b["uid"], b["name"], b.get("value", ""), b.get("reason", ""))
        if path == "/api/bulk":
            ids = b.get("uids", [])
            ch = {c: str(v).strip() for c, v in b.get("changes", {}).items() if str(v).strip() and c in BULK_FIELDS}
            if not ids or not ch:
                return {"ok": False, "msg": "Select invoices and fill at least one field."}
            if "Distributed Date" in ch:
                try:ch["Distributed Date"] = core.manual_date_text(ch["Distributed Date"])
                except ValueError:return {"ok":False,"msg":"Distributed Date: enter a valid DD/MM/YYYY date (optional HH:MM:SS). Nothing was changed."}
            reason = b.get("reason", "").strip()
            if ch.get("Invoice Status") == "Cancelled" and not reason:
                return {"ok": False, "need_reason": True}
            for uid in ids:
                if uid not in docs:
                    continue
                d = dict(docs[uid])
                d.update(ch)
                if reason and docs[uid].get("Invoice Status") != "Cancelled":
                    with_reason(d, reason)
                save_doc(uid, d)
            return {"ok": True, "msg": f"{len(ids)} invoices updated."}
        if path == "/api/delete":
            ids = [x for x in b.get("uids", []) if x in docs or x in wh_rows or x in pinv_rows]
            if not ids:
                return {"ok": False, "msg": "Nothing selected."}
            delete_uids(ids, u)
            return {"ok": True, "msg": f"{len(ids)} deleted."}
        if path == "/api/new":
            g = {c: str(b.get("fields", {}).get(c, "")).strip() for c in BASE[1:]}
            miss = [c for c in NEW_REQUIRED if not g[c]]
            if miss:
                return {"ok": False, "msg": "Required: " + ", ".join(miss)}
            inv = g["Invoice Number"]
            if inv.lower() in {str(d.get("Invoice Number", "")).lower() for d in docs.values()}:
                return {"ok": False, "msg": "This invoice number already exists."}
            for c in DATE_COLS:
                if g.get(c):
                    try:g[c] = core.manual_date_text(g[c])
                    except ValueError:return {"ok":False,"field":c,"msg":c+": enter a valid DD/MM/YYYY date (optional HH:MM:SS). Nothing was changed."}
            if g["Invoice Status"] == "Cancelled":
                reason = b.get("reason", "").strip()
                if not reason:
                    return {"ok": False, "need_reason": True}
                with_reason(g, reason)
            uid = new_invoice_uid(inv)
            g["ID"], g["Entered By"] = allocated_ids(u,[uid])[0], u
            save_doc(uid, g)
            return {"ok": True, "msg": f"Saved with ID {g['ID']}."}

        # ---- imports ----
        if path == "/api/import/new":
            return import_new(base64.b64decode(b.get("file", "")), u)
        if path == "/api/import/classify":
            return classify_save(b.get("rec", {}), u)
        if path == "/api/import/status":
            return {"ok": True, "receipt": import_receipt(b.get("kind", "full"))}
        if path == "/api/import/full/status":
            return {"ok": True, "receipt": full_import_receipt()}
        if path == "/api/import/full":
            # Candidate: the unguarded one-step import is closed. The UI uses /api/import/preview then /api/import/commit.
            return {"ok": False, "msg": "Use Settings > Import full data (Excel). It shows a preview first; nothing was imported."}
            return tracked_full_import(base64.b64decode(b.get("file", "")), u, b.get("request_id", ""))
        if path == "/api/import/wh":
            return tracked_excel_import("wh", base64.b64decode(b.get("file", "")), u, b.get("request_id", ""))
        if path == "/api/import/pi":
            return tracked_excel_import("pi", base64.b64decode(b.get("file", "")), u, b.get("request_id", ""))
        if path == "/api/import/lists":
            name, text = b.get("name", ""), b.get("text", "")
            if name not in LIST_NAMES():
                return {"ok": False, "msg": "Unknown list."}
            items = [x.strip() for x in text.splitlines() if x.strip()]
            if name == "customer_district":
                items = [x for x in items if not norm(x).startswith("customer name")]
            items = list(dict.fromkeys(items))
            if not items:
                return {"ok": False, "msg": "Nothing to save."}
            with core.LOCK:
                q("INSERT OR REPLACE INTO lst VALUES(?,?,1)", (name, json.dumps(items, ensure_ascii=False)))
                setmeta("list_updated:" + name, time.time())
            reload_data()
            request_cloud()
            sync_now.set()
            return {"ok": True, "msg": f"{len(items)} items saved to '{name}'."}

        # ---- PDFs / printing ----
        if core.TRIAL_LIMIT and not getattr(self, "_pdfgate", False) and path in ("/api/pdf/route", "/api/pdf/ho", "/api/pdf/list", "/api/pdf/wh", "/api/pdf/pinv"):  # trial: each PDF print click counts as one operation
            try: core.trial_bump(1, pre_only=True)
            except ValueError as e: return {"ok": False, "msg": str(e)}
            self._pdfgate = True
            try: _pdf_res = self.route(path, b, u)
            finally: self._pdfgate = False
            if isinstance(_pdf_res, dict) and _pdf_res.get("ok"):
                try: core.trial_bump(1)
                except ValueError as e: return {"ok": False, "msg": str(e)}
            return _pdf_res
        if path == "/api/pdf/route":
            return pdf_route(b.get("title", "Invoice Report"), b.get("rep", "Proposal"), b.get("f", {}),
                             bool(b.get("save_only")))
        if path == "/api/pdf/ho":
            return pdf_ho(b.get("f", {}))
        if path == "/api/pdf/list":
            view = b.get("view", "details")
            if view == "rgr":
                uids = rgr_rows(b.get("f", {}))
            else:
                uids = details_rows(b.get("flt"), b.get("f", {}))
            f = b.get("f", {})
            crit = [f"Status: {b['flt']}"] if b.get("flt") else []
            for lab, v in (("Invoice/SO", f.get("sq", "")), ("Customer", f.get("cust", "")), ("Date", f.get("dv", ""))):
                if v.strip():
                    crit.append(f"{lab}: {v.strip()}")
            if f.get("cfc") and f.get("cfv", "").strip():
                crit.append(f"{f['cfc']}: {f['cfv'].strip()}")
            return pdf_list(b.get("title", "Invoice Search"), " | ".join(crit) or "All invoices", uids,
                            bool(b.get("save_only")))
        if path == "/api/warehouse/history":
            return warehouse_history(b.get("kind"), b.get("number"))
        if path == "/api/warehouse/paper-check":
            return paper_check(b.get("kind"), b.get("number"), b.get("checked"), u)
        if path == "/api/pdf/wh":
            return wh_print(bool(b.get("all")), u, bool(b.get("save_only")))
        if path == "/api/pdf/pinv":
            return pi_pdf(b.get("f", {}))
        if path == "/api/wh/clear":
            delete_uids(list(wh_rows))
            return {"ok": True, "msg": "Warehouse list cleared."}

        # ---- backup / share ----
        if path == "/api/backup/now":
            return backup_now()
        if path == "/api/backup/load":
            raw = base64.b64decode(b.get("file", ""))
            p = os.path.join(tempfile.gettempdir(), f"dprogram_restore_{int(time.time())}.json")
            with open(p, "wb") as fh:
                fh.write(raw)
            try:
                n = merge_file(p, 1)
            except Exception as e:
                return {"ok": False, "msg": str(e)}
            reload_data()
            bump()
            sync_now.set(); request_cloud()
            return {"ok": True, "msg": f"{n} invoices loaded."}
        if path == "/api/share/get":
            return {"ok": True, "share": ("" if core.TEST_MODE else share_dir()), "trial": bool(core.TEST_MODE)}
        if path == "/api/share/pick":
            return {"ok": True, "path": pick_folder()}
        if path == "/api/share/set":
            _p = b.get("path", "").strip().strip('"')
            if not _p: return {"ok": False, "msg": "Type or choose a folder first. Nothing was changed."}
            if not os.path.isdir(_p): return {"ok": False, "msg": "This folder cannot be reached from this PC:\n" + _p + "\nCheck the path or the network drive. Nothing was changed."}
            SETTINGS["share"] = _p
            save_settings()
            return {"ok": True, "msg": f"Shared folder set to:\n{SETTINGS['share']}"}

        # ---- users (ADMIN) ----
        if path == "/api/customer/key": return __import__("customer").save_key(sys.modules[__name__],u,b)
        if path == "/api/customer/phonecode": return __import__("customer").phone_code(sys.modules[__name__],u,b)
        if path == "/api/customer/restart": return __import__("customer").restart(sys.modules[__name__],u,self.server)
        if path == "/api/users/del" and core.TRIAL_LIMIT: return __import__("customer").del_user(sys.modules[__name__],u,b)
        if path == "/api/users/add" and core.TRIAL_LIMIT: return __import__("customer").add_user(sys.modules[__name__],u,b)
        if path == "/api/users/add":
            if not access_control.is_admin(u):
                return {"ok": False, "msg": "Only ADMIN can manage users."}
            n, p = b.get("name", "").strip().upper(), b.get("pw", "")
            if not n or not p:
                return {"ok": False, "msg": "Name and password are required."}
            try:ID_SERVICE.prefix(n)
            except Exception as error:return {"ok":False,"msg":str(error)}
            if q("SELECT 1 FROM usr WHERE upper(name)=upper(?)",(n,)):return {"ok":False,"msg":"This user already exists. Existing user was not changed."}
            q("INSERT INTO usr VALUES(?,?,?,1)", (n, access_control.hash_password(p), time.time()))
            request_cloud()
            sync_now.set()
            return {"ok": True}
        if path == "/api/users/chpw":
            if not access_control.is_admin(u):
                return {"ok": False, "msg": "Only ADMIN can manage users."}
            n, p = b.get("name", ""), b.get("pw", "")
            if not p:
                return {"ok": False, "msg": "Password is required."}
            if not q("SELECT 1 FROM usr WHERE name=?",(n,)):return {"ok":False,"msg":"User not found. Nothing changed."}
            q("UPDATE usr SET pw=?,updated=?,dirty=1 WHERE name=?", (access_control.hash_password(p), time.time(),n))
            request_cloud()
            sync_now.set()
            return {"ok": True}
        if path == "/api/users/del":
            if not access_control.is_admin(u):
                return {"ok": False, "msg": "Only ADMIN can manage users."}
            n = b.get("name", "")
            if n == "ADMIN":
                return {"ok": False, "msg": "ADMIN cannot be deleted."}
            q("DELETE FROM usr WHERE name=?", (n,))
            q("INSERT INTO del VALUES('users',?)", (n,))
            request_cloud()
            sync_now.set()
            return {"ok": True}
        return {"ok": False, "msg": "unknown action"}


def start_finance_service():
    global FINANCE_SERVICE
    if not FINANCE_ROLLOUT:return
    if core.CONNECTED_TEST and core.CONNECTED_TEST["phase"]=="lan":return
    fs=localfinance.store(core.DATA_DIR)
    # Gate checked at import and startup, with all legacy stores reconciled before enabling.
    if not core.CONNECTED_TEST:fs.migrate_legacy(os.path.join(core.DATA_DIR,"expenses.db"))
    fs.changed=finance_wake
    if db is None or core.TEST_MODE:return
    remote=finance_service.FirestoreSequenceRemote(db,core.firestore,core.FieldFilter)
    FINANCE_SERVICE=finance_service.Service(fs,remote,FINANCE_ROLLOUT["bootstrap_read_cap"],bump)
    import atexit
    atexit.register(FINANCE_SERVICE.close)
    FINANCE_SERVICE.start()


def main():
    import desktop_app
    if not desktop_app.claim_instance(core.DATA_DIR, core.TEST_MODE, VERSION):
        return
    import provision_admi1
    if not core.TRIAL_LIMIT:print(provision_admi1.install(core))
    if FINANCE_ENABLED:
        fs=localfinance.store(core.DATA_DIR)
        restorejournal.CombinedRestore(core.DATA_DIR,core.cx,fs.ops.db).recover()
    try:
        import updater
        UPDATE_GUARD=updater.startup_guard()
    except Exception:
        UPDATE_GUARD=None
    reload_data()
    migrate_wh()
    start_finance_service()
    if core.db is not None and not core.TEST_MODE:PROJECT_USAGE.start()
    threading.Thread(target=lan_loop, daemon=True).start()
    threading.Thread(target=cloud_loop, daemon=True).start()
    import socket as _s
    port = 0
    env_port = int(os.environ.get("DPROGRAM_PORT", "0") or 0)
    for p in ([env_port] if env_port else []) + [8730, 8731, 8732, 0]:
        try:
            srv = ThreadingHTTPServer(("127.0.0.1", p), Hdl)
            port = srv.server_address[1]
            break
        except OSError:
            continue
    url = f"http://127.0.0.1:{port}/"
    print(f"Distribution Program {VERSION} - {url}")
    try:
        with open(os.path.join(core.DATA_DIR, "server.log"), "a", encoding="utf-8") as lg:
            lg.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} started {url}\n")
    except Exception:
        pass
    desktop_app.publish_instance(url, core.TEST_MODE, VERSION)
    desktop_app.dplog('server listening %s'%url); _boot('server listening '+url)
    threading.Timer(0.6, lambda: desktop_app.open_window(url, core.DATA_DIR, core.TEST_MODE)).start()
    threading.Thread(target=window_close_watch,args=(srv,),daemon=True).start()
    try:
        srv.serve_forever()
    finally:
        desktop_app.dplog('server stopped')
        srv.server_close()
        if FINANCE_SERVICE:FINANCE_SERVICE.close()
        desktop_app._cleanup()
        if WINDOW_EXIT and not RESTARTING:
            try:
                if desktop_app.WATCH_PROFILE: desktop_app._free_profile(desktop_app.WATCH_PROFILE)
            except Exception: pass
            os._exit(0)
        if RESTARTING:os._exit(0)


RESTARTING=False
WINDOW_EXIT=False
SYNC_BEFORE_EXIT_SECONDS=45

def window_close_watch(srv):
    """Native window closed with its X button: sync like Quit (up to SYNC_BEFORE_EXIT_SECONDS), then end the whole program like End Task."""
    import desktop_app
    global WINDOW_EXIT,EXIT_FLOW
    while desktop_app.WATCH_PROC is None: time.sleep(0.5)
    p=desktop_app.WATCH_PROC
    try: p.wait()
    except Exception: return
    if RESTARTING: return
    desktop_app.dplog('window closed by user: sync then exit (limit %ss)'%SYNC_BEFORE_EXIT_SECONDS)
    WINDOW_EXIT=True
    # Whatever happens, the process must be gone shortly after the limit.
    t=threading.Timer(SYNC_BEFORE_EXIT_SECONDS+15,lambda:(desktop_app.dplog('hard exit after timeout'),os._exit(0)));t.daemon=True;t.start()
    try:
        if EXIT_FLOW is None:
            import exitflow,sys
            EXIT_FLOW=exitflow.ExitFlow(sys.modules[__name__])
        st=EXIT_FLOW.start()
        end=time.monotonic()+SYNC_BEFORE_EXIT_SECONDS
        while st.get('state')=='running' and time.monotonic()<end:
            time.sleep(0.3);st=EXIT_FLOW.get()
        desktop_app.dplog('sync before exit finished: %s'%st.get('state'))
    except Exception as e:
        desktop_app.dplog('sync before exit error %r'%(e,))
    srv.shutdown()
if __name__ == "__main__":
    try:
        main()
    except BaseException as _e:
        try:
            import traceback, desktop_app as _d
            _d.dplog('FATAL '+traceback.format_exc().replace('\n',' | '))
        except Exception: pass
        raise
