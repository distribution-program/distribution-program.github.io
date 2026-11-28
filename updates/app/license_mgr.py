"""License for the trial edition. Offline: a key is signed by the developer and checked here with the public key.
The key is bound to this PC (device code from the Windows machine id), so copying the program, the data folder or the key to another PC never works.
No licence is needed by the company MAIN/REPLICA programs: this only matters when DPROGRAM_TRIAL_LIMIT is set (the public trial)."""
import base64, hashlib, json, os, re, sys, time, datetime
import ed25519

# Several signing keys may be listed (for example the Windows tool and the phone issuer). To retire one, put its hex in REVOKED_KEYS in an update:
# keys signed by it stop working, keys signed by the others keep working.
PUBLIC_KEYS = [
    "76d15c574808db08c25bc6a617c237789ceec671a4e205342095ec4a5d4ef8f1",  # Distribution License (Windows)
    "65a36d40e6850241d3fd0a3799800795229fbb6cf2a97e65558743a43502a923",  # Distribution License (phone)
]
REVOKED_KEYS = []
PREFIX = "DPL1-"
EDITIONS = ("full", "lift")

def _b64e(b): return base64.urlsafe_b64encode(b).decode().rstrip("=")
def _b64d(s): return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))

def machine_id():
    """Stable id of this PC. DP_DEVICE_ID is only for tests."""
    t = os.environ.get("DP_DEVICE_ID")
    if t: return t
    try:
        import winreg
        k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography", 0, winreg.KEY_READ | getattr(winreg, "KEY_WOW64_64KEY", 0))
        return str(winreg.QueryValueEx(k, "MachineGuid")[0])
    except Exception: pass
    for f in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        try:
            v = open(f).read().strip()
            if v: return v
        except Exception: pass
    return ""

def device_code(mid=None):
    mid = machine_id() if mid is None else mid
    if not mid: return ""
    h = base64.b32encode(hashlib.sha256(("DPDEV1|" + mid.lower()).encode()).digest()).decode()[:12]
    return "-".join(h[i:i + 4] for i in (0, 4, 8))

def _norm_dev(s): return re.sub(r"[^A-Z0-9]", "", str(s or "").upper())

def parse(key):
    """Return (payload dict) if the signature is right, else raise ValueError with a plain message."""
    k = re.sub(r"\s+", "", str(key or ""))
    if not k.startswith(PREFIX) or "." not in k: raise ValueError("This is not a license key. Paste the whole key.")
    try:
        body, sig = k[len(PREFIX):].split(".", 1)
        raw, sg = _b64d(body), _b64d(sig)
        pl = json.loads(raw.decode("utf-8"))
    except Exception: raise ValueError("This is not a license key. Paste the whole key.")
    if not any(ed25519.verify(bytes.fromhex(pk), raw, sg) for pk in PUBLIC_KEYS if pk not in REVOKED_KEYS): raise ValueError("This license key is not valid. Check that you pasted all of it.")
    if not isinstance(pl, dict) or pl.get("v") != 1 or pl.get("edition") not in EDITIONS: raise ValueError("This license key is not valid.")
    return pl

def _today(): return datetime.date.today()

def check(key, seen=None, mid=None):
    """Full check of a key on this PC. Returns {ok, state, name, edition, expiry, device, msg}.
    state: valid | expired | clock | other_pc | invalid"""
    try: pl = parse(key)
    except ValueError as e: return {"ok": False, "state": "invalid", "msg": str(e)}
    mydev = device_code(mid)
    out = {"name": pl.get("name", ""), "edition": pl["edition"], "expiry": pl.get("expiry", ""), "device": pl.get("device", "")}
    if not mydev or _norm_dev(pl.get("device")) != _norm_dev(mydev):
        return dict(out, ok=False, state="other_pc", msg="This key is for another PC. Send your device code to the developer.")
    today = _today()
    try: seen_d = datetime.date.fromisoformat(seen) if seen else None
    except ValueError: seen_d = None
    if seen_d and today < seen_d - datetime.timedelta(days=1):
        return dict(out, ok=False, state="clock", msg="The PC date was moved back. Set the correct date and restart.")
    ex = pl.get("expiry", "")
    if ex:
        try:
            if today > datetime.date.fromisoformat(ex): return dict(out, ok=False, state="expired", msg="This license expired on " + ex + ". Ask the developer for a new key.")
        except ValueError: return dict(out, ok=False, state="invalid", msg="This license key is not valid.")
    return dict(out, ok=True, state="valid", msg="Licensed to " + out["name"] + (", valid until " + ex if ex else ", no expiry"))

# ---- state on this PC ----
# The trial counter and the last date seen are sealed: a checksum that only this PC can compute (it uses the machine id) is kept in the
# database AND in a second file outside the program folder. Lowering the counter, setting the clock back, or editing the seal is detected;
# deleting only the data folder does not give a new trial because the second file remembers.
import hmac
_SALT = "dp-trial-state-v1"
_cache = {"t": 0, "v": None}

def _sec(): return hashlib.sha256(("DPSTATE1|" + (machine_id() or "x") + "|" + _SALT).encode()).digest()
def _seal(used, seen): return "%d|%s|%s" % (used, seen, hmac.new(_sec(), ("%d|%s" % (used, seen)).encode(), hashlib.sha256).hexdigest()[:32])
def _unseal(s):
    try:
        u, sn, m = str(s).strip().split("|")
        if hmac.compare_digest(m, hmac.new(_sec(), ("%d|%s" % (int(u), sn)).encode(), hashlib.sha256).hexdigest()[:32]): return int(u), sn
    except Exception: pass
    return None

def state_file():
    p = os.environ.get("DP_STATE_FILE")
    if p: return p
    base = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(base, "DistributionProgramTrial", "state.dat")
def _file_get():
    try:
        with open(state_file(), encoding="utf-8") as f: return f.read().strip() or None
    except Exception: return None
def _file_put(s):
    try:
        p = state_file(); os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f: f.write(s)
    except Exception: pass

def _meta_get(core, k):
    r = core.cx.execute("SELECT v FROM meta WHERE k=?", (k,)).fetchone()
    return r[0] if r else None
def _meta_put(core, k, v):
    with core.LOCK:
        core.cx.execute("INSERT OR REPLACE INTO meta VALUES(?,?)", (k, v)); core.cx.commit()

def _counter(core):
    """Return (used, seen_date, tampered). Reseals when the counter or the date moved forward."""
    raw = int(_meta_get(core, "trial_ops") or 0)
    recs = [_meta_get(core, "trial_seal"), _file_get()]
    used, seen, bad = 0, "", False
    for r in recs:
        if not r: continue
        d = _unseal(r)
        if d is None: bad = True
        else:
            used = max(used, d[0]); seen = max(seen, d[1])
    used = max(used, raw)
    today = _today().isoformat()
    if bad: return used, seen, True
    new_seen = seen if (seen and today < seen) else today   # never move the date back
    s = _seal(used, new_seen)
    if s != recs[0] or s != recs[1]:
        _meta_put(core, "trial_seal", s); _file_put(s)
        if used != raw: _meta_put(core, "trial_ops", str(used))
    return used, seen, False

def status(core, force=False):
    """Current license state for the trial edition. Cached for 30 seconds."""
    now = time.time()
    if not force and _cache["v"] is not None and now - _cache["t"] < 30: return _cache["v"]
    lim = core.TRIAL_LIMIT
    used, seen, bad = _counter(core)
    tampered = bad or bool(getattr(core, "TAMPERED", False))
    key = _meta_get(core, "license_key")
    lic = check(key, seen or None) if key else None
    licensed = bool(lic and lic["ok"]) and not getattr(core, "TAMPERED", False)
    v = {"trial": bool(lim), "limit": lim, "used": used, "left": max(0, lim - used), "licensed": licensed,
         "full": bool(licensed and lic["edition"] == "full"), "edition": lic["edition"] if lic else "", "name": lic["name"] if lic else "",
         "expiry": lic["expiry"] if lic else "", "lic_state": lic["state"] if lic else "none", "lic_msg": lic["msg"] if lic else "",
         "device": device_code(), "readonly": False, "tampered": tampered}
    if lim and not licensed and (used >= lim or tampered or (lic and lic["state"] in ("expired", "clock"))):
        v["readonly"] = True   # trial finished, license ended or the trial data was edited: read and print only
        if tampered and not v["lic_state"] in ("expired", "clock"): v["lic_state"], v["lic_msg"] = "tampered", "The trial data was changed. Enter a license key to continue."
    _cache["t"], _cache["v"] = now, v
    return v

def activate(core, key):
    if not core.TRIAL_LIMIT: return {"ok": False, "msg": "A license is only used by the trial edition."}
    r = check(key, _meta_get(core, "license_seen"))
    if not r["ok"]: return {"ok": False, "msg": r["msg"]}
    _meta_put(core, "license_key", re.sub(r"\s+", "", key))
    st = status(core, True); apply_triggers(core)
    return {"ok": True, "msg": r["msg"], "status": st}

def apply_triggers(core):
    """The trial delete counter only runs while the PC is not licensed."""
    if not core.TRIAL_LIMIT: return
    st = status(core)
    with core.LOCK:
        if st["licensed"]:
            core.cx.executescript("DROP TRIGGER IF EXISTS trial_del_guard; DROP TRIGGER IF EXISTS trial_del_count;")
        else:
            core.cx.executescript("""DROP TRIGGER IF EXISTS trial_del_guard; DROP TRIGGER IF EXISTS trial_del_count;
            CREATE TRIGGER trial_del_guard BEFORE DELETE ON inv WHEN %s
            BEGIN SELECT RAISE(ABORT,'Trial version limit reached: %d operations (add, edit, delete or print). Enter a license key to continue.'); END;
            CREATE TRIGGER trial_del_count AFTER DELETE ON inv
            BEGIN UPDATE meta SET v=CAST(CAST(v AS INTEGER)+1 AS TEXT) WHERE k='trial_ops'; END;""" % (("1" if st["readonly"] else "CAST((SELECT v FROM meta WHERE k='trial_ops') AS INTEGER) >= %d" % core.TRIAL_LIMIT), core.TRIAL_LIMIT))
        core.cx.commit()
