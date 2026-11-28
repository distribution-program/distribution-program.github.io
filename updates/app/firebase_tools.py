"""Settings > Firebase and phone app (Admi1 only): connection check, sign-in switch, rules publish, driver accounts.
All Google calls go through plain HTTPS with the program's own service-account key. DP_FB_* env vars only exist so tests can point them at a local fake server."""
import json, os, re, time, urllib.request, urllib.error, urllib.parse
import core

COMPANY_PROJECT = "car-distribution"
def PRJ():
    """Company programs always use the company project. The public edition uses the project of the key file the customer put next to the program."""
    if not core.TRIAL_LIMIT: return COMPANY_PROJECT
    try:
        with open(core.CREDENTIAL_PATH, encoding="utf-8") as fh: return str(json.load(fh).get("project_id", "")).strip() or "-"
    except Exception: return "-"
EMAIL_DOMAIN = "drivers.distribution-program.app"
DEFAULT_ADMIN_UID = "" if core.TRIAL_LIMIT else "whtrByjUqyRtOCby1C8P284n4iG3"
ALLOWED_USERS = [x.strip().casefold() for x in os.environ.get("DP_FB_TOOLS_USERS", "admi1").split(",") if x.strip()]
DELIVER_KEYS = ["Invoice Status", "updated", "_rev", "Last Updated By", "Delivered By", "Delivered At"]
TEST_RUN = "utest_20261123_kw20"

def _env(k, d): return os.environ.get("DP_FB_" + k, d)

def allowed(user):
    """Admi1 by default. Another program user only if Admi1 gave him the 'Firebase admin' permission."""
    if core.TEST_MODE:
        # the public trial is unlocked for the Full edition license only (the trial has no users, so its single user qualifies)
        try:
            import license_mgr
            import access_control
            return bool(core.TRIAL_LIMIT and license_mgr.status(core).get("full") and access_control.is_admin(user))
        except Exception: return False
    if str(user or "").casefold() in ALLOWED_USERS: return True
    try:
        import access_control
        return access_control.has_fbadmin(core, user)
    except Exception: return False

def _token():
    t = _env("TOKEN", "")
    if t: return t
    import firebase_admin
    return firebase_admin.get_app().credential.get_access_token().access_token

def _call(method, url, body=None, timeout=25):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Authorization": "Bearer " + _token(), "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode() or "{}"
            return json.loads(raw)
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="replace")
        try: msg = json.loads(raw).get("error", {}).get("message", raw)
        except ValueError: msg = raw
        raise FbError(e.code, str(msg)[:300])
    except urllib.error.URLError as e:
        raise FbError(0, "No internet or Firebase not reachable: " + str(e.reason)[:120])

class FbError(Exception):
    def __init__(self, code, msg): super().__init__(msg); self.code = code; self.msg = msg

def _hint(e):
    if e.code in (401, 403):
        return e.msg + " | The key may not have permission. In Firebase console: Project settings > Service accounts > open the Google Cloud link > IAM > give the firebase-adminsdk account the role 'Firebase Admin' (one click), then try again."
    return e.msg

IT = lambda: _env("IT", "https://identitytoolkit.googleapis.com")
FR = lambda: _env("FR", "https://firebaserules.googleapis.com")

# ---------- connection ----------
def key_path(): return core.CREDENTIAL_PATH
def status():
    out = {"ok": True, "key_found": os.path.exists(key_path()), "project": PRJ(), "cloud": core.db is not None,
           "folder": os.path.dirname(os.path.abspath(key_path())), "signin": None, "rules": None, "drivers": None}
    out["db_project"] = getattr(core.db, "project", None) if core.db is not None else None
    if out["key_found"] and core.db is not None:
        try:
            cfg = _call("GET", f"{IT()}/admin/v2/projects/{PRJ()}/config")
            out["signin"] = bool(cfg.get("signIn", {}).get("email", {}).get("enabled"))
        except FbError as e: out["signin_error"] = _hint(e)
        try:
            rel = _call("GET", f"{FR()}/v1/projects/{PRJ()}/releases/cloud.firestore")
            out["rules"] = {"ruleset": rel.get("rulesetName"), "updated": rel.get("updateTime")}
        except FbError as e: out["rules_error"] = _hint(e)
        try: out["drivers"] = sum(1 for _ in _col().stream(timeout=8, retry=None))
        except Exception as e: out["drivers_error"] = str(e)[:120]
    return out

def enable_signin():
    try:
        _call("PATCH", f"{IT()}/admin/v2/projects/{PRJ()}/config?updateMask=signIn.email.enabled,signIn.email.passwordRequired",
              {"signIn": {"email": {"enabled": True, "passwordRequired": True}}})
        cfg = _call("GET", f"{IT()}/admin/v2/projects/{PRJ()}/config")
        on = bool(cfg.get("signIn", {}).get("email", {}).get("enabled"))
        return {"ok": on, "msg": "Email/Password sign-in is ON." if on else "The change was sent but Firebase still shows it off."}
    except FbError as e: return {"ok": False, "msg": _hint(e)}

# ---------- rules ----------
def rules_text(admin_uid=None):
    admin = (admin_uid or core.meta("fb_admin_uid", "") or DEFAULT_ADMIN_UID)
    admin = str(admin).strip()
    if not re.fullmatch(r"[A-Za-z0-9]{10,64}", admin): raise ValueError("Admin uid looks wrong.")
    keys = ", ".join("'%s'" % k for k in DELIVER_KEYS)
    blk = """    match /@P@invoices/{doc} {
      allow read: if isManager('@P@driver_accounts') || isOwnDriver('@P@driver_accounts');
      allow update: if (isManager('@P@driver_accounts') || isOwnDriver('@P@driver_accounts'))
        && resource.data['Invoice Status'] == 'inprocess'
        && request.resource.data['Invoice Status'] == 'inprocess'
        && resource.data.get('Delivered By', '') == ''
        && request.resource.data.diff(resource.data).affectedKeys().hasOnly([@KEYS@])
        && (approvedUser() || request.resource.data['Delivered By'] == profile('@P@driver_accounts').name);
    }
    match /@P@lists/{doc} {
      allow read: if approvedUser();
    }
    match /@P@driver_accounts/{uid} {
      allow read: if request.auth != null && request.auth.uid == uid;
    }
    match /@P@driver_state/{key} {
      allow read: if isManager('@P@driver_accounts') || (hasProfile('@P@driver_accounts') && key == profile('@P@driver_accounts').name.replace('/', '_'));
      allow create, update: if (isManager('@P@driver_accounts') || (hasProfile('@P@driver_accounts') && key == profile('@P@driver_accounts').name.replace('/', '_')))
        && request.resource.data.keys().hasOnly(['rev', 'updated'])
        && request.resource.data.rev is int;
    }
"""
    body = "".join(blk.replace("@P@", p).replace("@KEYS@", keys) for p in ("", TEST_RUN + "_"))
    head = """rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    function approvedUser() {
      return request.auth != null
        && request.auth.uid == '@ADMIN@';
    }
    function profile(col) {
      return get(/databases/$(database)/documents/$(col)/$(request.auth.uid)).data;
    }
    function hasProfile(col) {
      return request.auth != null
        && exists(/databases/$(database)/documents/$(col)/$(request.auth.uid))
        && profile(col).get('disabled', false) != true;
    }
    function isManager(col) {
      return approvedUser() || (hasProfile(col) && profile(col).get('role', '') == 'manager');
    }
    function isOwnDriver(col) {
      return hasProfile(col) && profile(col).get('role', 'driver') == 'driver'
        && resource.data['Driver name'] == profile(col).name;
    }
""".replace("@ADMIN@", admin)
    tail = """    match /{document=**} {
      allow read, write: if false;
    }
  }
}
"""
    return head + body + tail

def _backup_dir():
    d = os.path.join(core.DATA_DIR, "rules_backups"); os.makedirs(d, exist_ok=True); return d

def current_rules():
    rel = _call("GET", f"{FR()}/v1/projects/{PRJ()}/releases/cloud.firestore")
    rs = _call("GET", f"{FR()}/v1/{rel['rulesetName']}")
    files = rs.get("source", {}).get("files", [])
    return rel["rulesetName"], "\n".join(f.get("content", "") for f in files)

def publish_rules(admin_uid=None):
    try:
        text = rules_text(admin_uid)
        backup = None
        try:
            name, old = current_rules()
            backup = os.path.join(_backup_dir(), "rules_backup_" + time.strftime("%d-%m-%Y_%H%M%S") + ".txt")
            with open(backup, "w", encoding="utf-8") as f: f.write(old)
        except FbError as e:
            if e.code != 404: return {"ok": False, "msg": "Could not save the old rules first, so nothing was published. " + _hint(e)}
        if admin_uid: core.setmeta("fb_admin_uid", str(admin_uid).strip())
        rs = _call("POST", f"{FR()}/v1/projects/{PRJ()}/rulesets", {"source": {"files": [{"name": "firestore.rules", "content": text}]}})
        rname = f"projects/{PRJ()}/releases/cloud.firestore"
        body = {"release": {"name": rname, "rulesetName": rs["name"]}}
        try: _call("PATCH", f"{FR()}/v1/{rname}", body)
        except FbError as e:
            if e.code != 404: raise
            _call("POST", f"{FR()}/v1/projects/{PRJ()}/releases", body["release"])
        return {"ok": True, "msg": "Published at " + time.strftime("%H:%M:%S"), "backup": backup}
    except FbError as e: return {"ok": False, "msg": _hint(e)}
    except ValueError as e: return {"ok": False, "msg": str(e)}

def restore_rules():
    try:
        files = sorted(os.listdir(_backup_dir()))
        if not files: return {"ok": False, "msg": "No saved old rules on this PC."}
        with open(os.path.join(_backup_dir(), files[-1]), encoding="utf-8") as f: text = f.read()
        if not text.strip(): return {"ok": False, "msg": "The last saved rules file is empty."}
        rs = _call("POST", f"{FR()}/v1/projects/{PRJ()}/rulesets", {"source": {"files": [{"name": "firestore.rules", "content": text}]}})
        rname = f"projects/{PRJ()}/releases/cloud.firestore"
        _call("PATCH", f"{FR()}/v1/{rname}", {"release": {"name": rname, "rulesetName": rs["name"]}})
        return {"ok": True, "msg": "Previous rules restored (" + files[-1] + ")."}
    except FbError as e: return {"ok": False, "msg": _hint(e)}

# ---------- drivers ----------
def _col():
    if core.db is None: raise RuntimeError("Not connected to Firebase.")
    return core.db.collection("driver_accounts")

def _clean_user(u):
    u = str(u or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9._-]{3,30}", u): raise ValueError("Username: 3 to 30 letters, numbers, dot, dash or underscore. No spaces.")
    return u

def _email(u): return u.casefold() + "@" + EMAIL_DOMAIN

def _pw(p):
    p = str(p or "")
    if len(p) < 6: raise ValueError("Password must be at least 6 characters.")
    return p

def _doc(uid):
    s = _col().document(uid).get()
    return s.to_dict() if s.exists else None

def drivers_list():
    try:
        rows = []
        for s in _col().stream():
            d = s.to_dict() or {}
            rows.append({"uid": s.id, "username": d.get("username", ""), "name": d.get("name", ""), "car": d.get("car", ""),
                         "line": d.get("line", ""), "phone": d.get("phone", ""), "role": d.get("role") or "driver", "disabled": bool(d.get("disabled")),
                         "created": d.get("created", "")})
        rows.sort(key=lambda r: r["username"].casefold())
        return {"ok": True, "drivers": rows}
    except Exception as e: return {"ok": False, "msg": str(e)[:200]}

def driver_add(b):
    try:
        user = _clean_user(b.get("username")); pw = _pw(b.get("password"))
        name = str(b.get("name") or "").strip()
        role = str(b.get("role") or "driver").strip().lower()
        if role not in ("driver", "manager"): raise ValueError("Role must be Driver or Distribution manager.")
        if not name: raise ValueError("Name is required.")
        for r in drivers_list().get("drivers", []):
            if r["username"].casefold() == user.casefold(): raise ValueError("This username already exists.")
        acc = _call("POST", f"{IT()}/v1/projects/{PRJ()}/accounts", {"email": _email(user), "password": pw, "displayName": name, "emailVerified": True})
        uid = acc["localId"]
        _col().document(uid).set({"username": user, "name": name, "role": role, "car": (str(b.get("car") or "").strip() if role == "driver" else ""), "line": (str(b.get("line") or "").strip() if role == "driver" else ""),
                                  "phone": str(b.get("phone") or "").strip(), "disabled": False, "created": time.strftime("%d/%m/%Y %H:%M:%S"), "updated": time.time()})
        return {"ok": True, "msg": ("User " if role == "manager" else "Driver ") + user + " created.", "uid": uid}
    except FbError as e: return {"ok": False, "msg": _hint(e)}
    except (ValueError, RuntimeError) as e: return {"ok": False, "msg": str(e)}
    except Exception as e: return {"ok": False, "msg": "Saved nothing: " + str(e)[:160]}

def driver_edit(b):
    try:
        uid = b.get("uid"); d = _doc(uid)
        if not d: raise ValueError("Driver not found.")
        name = str(b.get("name", d.get("name", ""))).strip()
        if not name: raise ValueError("Driver name is required.")
        role = str(b.get("role", d.get("role") or "driver")).strip().lower()
        if role not in ("driver", "manager"): raise ValueError("Role must be Driver or Distribution manager.")
        upd = {"role": role, "name": name, "car": str(b.get("car", d.get("car", ""))).strip(), "line": str(b.get("line", d.get("line", ""))).strip(),
               "phone": str(b.get("phone", d.get("phone", ""))).strip(), "updated": time.time()}
        _call("POST", f"{IT()}/v1/projects/{PRJ()}/accounts:update", {"localId": uid, "displayName": name})
        _col().document(uid).update(upd)
        return {"ok": True, "msg": "Driver saved."}
    except FbError as e: return {"ok": False, "msg": _hint(e)}
    except (ValueError, RuntimeError) as e: return {"ok": False, "msg": str(e)}

def driver_set_disabled(uid, flag):
    try:
        d = _doc(uid)
        if not d: raise ValueError("Driver not found.")
        body = {"localId": uid, "disableUser": bool(flag)}
        _call("POST", f"{IT()}/v1/projects/{PRJ()}/accounts:update", body)
        _col().document(uid).update({"disabled": bool(flag), "updated": time.time()})
        return {"ok": True, "msg": ("Disabled at " if flag else "Enabled at ") + time.strftime("%H:%M:%S")}
    except FbError as e: return {"ok": False, "msg": _hint(e)}
    except (ValueError, RuntimeError) as e: return {"ok": False, "msg": str(e)}

def driver_reset(uid, pw1, pw2):
    try:
        if pw1 != pw2: raise ValueError("The two passwords are not the same.")
        pw = _pw(pw1)
        if not _doc(uid): raise ValueError("Driver not found.")
        _call("POST", f"{IT()}/v1/projects/{PRJ()}/accounts:update", {"localId": uid, "password": pw, "validSince": str(int(time.time()))})
        return {"ok": True, "msg": "New password saved. The driver is signed out and logs in with the new one."}
    except FbError as e: return {"ok": False, "msg": _hint(e)}
    except (ValueError, RuntimeError) as e: return {"ok": False, "msg": str(e)}

def driver_delete(uid):
    try:
        if not _doc(uid): raise ValueError("Driver not found.")
        _call("POST", f"{IT()}/v1/projects/{PRJ()}/accounts:delete", {"localId": uid})
        _col().document(uid).delete()
        return {"ok": True, "msg": "Driver login deleted. Invoices were not touched."}
    except FbError as e: return {"ok": False, "msg": _hint(e)}
    except (ValueError, RuntimeError) as e: return {"ok": False, "msg": str(e)}
