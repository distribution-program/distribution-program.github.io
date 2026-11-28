"""In-app updater. Downloads only the changed program files (app/ folder) from a free host, checks each SHA-256,
backs up the files it replaces, swaps them, and restores the backup if anything fails.
Never touches connection files (launch_v39.py, windows_ca_v43.py, REPLICA_LOCATION.json, serviceAccountKey.json),
databases, certificates, the bundled python folder or anything outside app/.
Private repo later: put a read-only token in update_token.txt inside the data folder. No code change needed."""
import os, sys, json, time, hashlib, shutil, subprocess, threading, urllib.request, urllib.error

DEFAULT_BASE = "https://distribution-program.github.io/updates/"
APP_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(APP_DIR)
WORK_DIR = os.path.join(APP_DIR, "_update_work")  # backups, temp downloads and pending flag live here, so the program folder shows only the two EXE files
ALLOWED_EXT = (".py", ".js", ".html", ".css", ".txt", ".png", ".ico", ".svg")
BLOCKED_NAMES = {"launch_v39.py", "windows_ca_v43.py", "replica_location.json", "serviceaccountkey.json", "updater.py_never"}
STATE_LOCK = threading.Lock()
STATE = {"state": "idle", "msg": ""}


def _set(state, msg, **kw):
    with STATE_LOCK:
        STATE.clear(); STATE.update(state=state, msg=msg, **kw)


def status():
    with STATE_LOCK:
        return dict(STATE)


def _cfg(data_dir):
    base, token = DEFAULT_BASE, ""
    try:
        with open(os.path.join(data_dir, "update_config.json"), encoding="utf-8") as f:
            c = json.load(f)
        base = str(c.get("base_url") or base)
    except Exception:
        pass
    for folder in (data_dir, ROOT_DIR):  # the token file may sit in the data folder or beside launch_v39.py (next to the key)
        try:
            with open(os.path.join(folder, "update_token.txt"), encoding="utf-8") as f:
                token = f.read().strip()
            if token:
                break
        except Exception:
            pass
    if not base.startswith("https://") and not base.startswith("file:") and not base.startswith("http://127.0.0.1"):
        raise ValueError("Update address must be https")
    if not base.endswith("/"):
        base += "/"
    return base, token


def _get(url, token, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": "Distribution-Program-updater", "Cache-Control": "no-cache"})
    if token:
        req.add_header("Authorization", "token " + token)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_target(rel):
    """Return the absolute path for a manifest entry, or raise. Only app/ files of an allowed type."""
    if not isinstance(rel, str) or "\\" in rel or rel.startswith("/") or ":" in rel:
        raise ValueError("Unsafe path in update list: " + str(rel)[:60])
    parts = rel.split("/")
    if len(parts) < 2 or parts[0] != "app" or any(p in ("", ".", "..") or p.startswith("_update") for p in parts):
        raise ValueError("Update list may only change files inside app/: " + rel[:60])
    name = parts[-1].lower()
    if name in BLOCKED_NAMES or not name.endswith(ALLOWED_EXT) or name.endswith((".db", ".pem", ".cmd")):
        raise ValueError("File type or name not allowed in an update: " + rel[:60])
    full = os.path.abspath(os.path.join(ROOT_DIR, *parts))
    if not full.startswith(os.path.join(ROOT_DIR, "app") + os.sep):
        raise ValueError("Unsafe path in update list: " + rel[:60])
    return full


def installed_tag():
    try:
        with open(os.path.join(APP_DIR, "installed_update.json"), encoding="utf-8") as f:
            return json.load(f).get("version", "")
    except Exception:
        return ""


def check(data_dir):
    """Read the manifest and list the files that differ from this install."""
    base, token = _cfg(data_dir)
    try:
        m = json.loads(_get(base + "updates.json", token).decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code in (401, 403, 404) and not token:
            raise ValueError("Update key file not found. Put the file update_token.txt in the program folder (next to MAIN.exe): " + os.path.dirname(APP_DIR) + " then press Update again. Nothing changed.")
        if e.code in (401, 403, 404):
            raise ValueError("Update site refused the update key (answer " + str(e.code) + "). The update_token.txt in " + os.path.dirname(APP_DIR) + " may be wrong or expired. Nothing changed.")
        raise ValueError("Update site answered " + str(e.code) + ". Nothing changed.")
    except Exception as e:
        raise ValueError("Cannot reach the update site (" + type(e).__name__ + "). Nothing changed.")
    if not isinstance(m, dict) or m.get("format") != 1 or not isinstance(m.get("files"), dict) or not str(m.get("version", "")).strip():
        raise ValueError("Update list is not valid. Nothing changed.")
    changed = []
    for rel, info in m["files"].items():
        full = safe_target(rel)
        sha = str((info or {}).get("sha256", "")).lower()
        if len(sha) != 64:
            raise ValueError("Update list has a bad checksum for " + rel)
        if not os.path.isfile(full) or _sha(full) != sha:
            changed.append({"path": rel, "size": int((info or {}).get("size", 0) or 0), "sha256": sha})
    return {"version": str(m["version"]), "notes": str(m.get("notes", ""))[:400], "current": installed_tag(),
            "changed": changed, "available": bool(changed), "total_size": sum(c["size"] for c in changed)}


def _unhide(path):
    """Windows refuses to overwrite a file that has the Hidden or Read-only flag. Clear both before writing."""
    if os.name != "nt" or not os.path.exists(path):
        return
    try:
        import ctypes
        a = ctypes.windll.kernel32.GetFileAttributesW(path)
        if a != -1 and a & 0x3:
            ctypes.windll.kernel32.SetFileAttributesW(path, a & ~0x3)
    except Exception:
        pass


def _backup_root():
    return os.path.join(WORK_DIR, "backups")


def _restore(backup_dir, files):
    for rel in files:
        src = os.path.join(backup_dir, *rel.split("/"))
        dst = os.path.join(ROOT_DIR, *rel.split("/"))
        if os.path.isfile(src):
            _unhide(dst)
            shutil.copy2(src, dst)
        elif os.path.isfile(dst):
            os.remove(dst)  # file did not exist before the update


def apply(data_dir, fail_after=None):
    """Download, verify, back up, swap. Restores on any failure. fail_after is a test hook (swap this many files then fail)."""
    info = check(data_dir)
    if not info["changed"]:
        _set("uptodate", "Already up to date.", version=info["version"])
        return {"ok": True, "uptodate": True, "version": info["version"]}
    base, token = _cfg(data_dir)
    stamp = time.strftime("%Y%m%d_%H%M%S") + "_%03d" % (int(time.time() * 1000) % 1000)
    tmp = os.path.join(WORK_DIR, "tmp_" + stamp)
    backup = os.path.join(_backup_root(), stamp)
    done = []
    try:
        os.makedirs(tmp)
        n = len(info["changed"])
        for i, c in enumerate(info["changed"], 1):
            _set("downloading", "Downloading file %d of %d" % (i, n), done=i - 1, total=n)
            data = _get(base + c["path"], token, 60)
            if hashlib.sha256(data).hexdigest() != c["sha256"]:
                raise ValueError("Checksum mismatch for " + c["path"] + ". Nothing was changed.")
            dst = os.path.join(tmp, *c["path"].split("/"))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, "wb") as f:
                f.write(data)
            if c["path"].endswith(".py"):
                compile(data, c["path"], "exec")  # syntax check before anything is replaced
        _set("installing", "Backing up and replacing files", total=n)
        os.makedirs(backup)
        for c in info["changed"]:
            real = safe_target(c["path"])
            if os.path.isfile(real):
                b = os.path.join(backup, *c["path"].split("/"))
                os.makedirs(os.path.dirname(b), exist_ok=True)
                shutil.copy2(real, b)
        with open(os.path.join(backup, "files.json"), "w", encoding="utf-8") as f:
            json.dump({"files": [c["path"] for c in info["changed"]], "from": installed_tag(), "to": info["version"]}, f)
        for k, c in enumerate(info["changed"]):
            if fail_after is not None and k >= fail_after:
                raise RuntimeError("Forced test failure")
            real = safe_target(c["path"])
            os.makedirs(os.path.dirname(real), exist_ok=True)
            shutil.copy2(os.path.join(tmp, *c["path"].split("/")), real + ".new")
            _unhide(real)
            os.replace(real + ".new", real)
            done.append(c["path"])
        for c in info["changed"]:
            if _sha(safe_target(c["path"])) != c["sha256"]:
                raise RuntimeError("Verification after copy failed for " + c["path"])
        _unhide(os.path.join(APP_DIR, "installed_update.json"))
        with open(os.path.join(APP_DIR, "installed_update.json"), "w", encoding="utf-8") as f:
            json.dump({"version": info["version"], "at": stamp}, f)
        os.makedirs(WORK_DIR, exist_ok=True)
        with open(os.path.join(WORK_DIR, "update_pending.json"), "w", encoding="utf-8") as f:
            json.dump({"backup": backup, "stamp": stamp, "confirmed": False, "starts": 0}, f)
        shutil.rmtree(tmp, ignore_errors=True)
        _set("restart", "Update installed. Restarting.", version=info["version"], files=len(done))
        return {"ok": True, "version": info["version"], "files": len(done), "backup": backup}
    except Exception as e:
        try:
            _restore(backup, done + [c["path"] for c in info["changed"] if c["path"] not in done]) if os.path.isdir(backup) else None
        except Exception as e2:
            _set("failed", "Update failed and restore had a problem: " + str(e2)[:120] + ". Backup folder: " + backup)
            return {"ok": False, "msg": "Update failed and restore had a problem. Backup folder: " + backup}
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(backup, ignore_errors=True)  # a failed attempt must not count as the "last update" backup
        _set("failed", "Update failed: " + str(e)[:160] + ". Old version restored.")
        return {"ok": False, "msg": "Update failed: " + str(e)[:160] + ". The old version was restored."}


def latest_backup():
    root = _backup_root()
    if not os.path.isdir(root):
        return None
    for d in sorted(os.listdir(root), reverse=True):
        p = os.path.join(root, d)
        if os.path.isfile(os.path.join(p, "files.json")):
            return p
    return None


def rollback():
    p = latest_backup()
    if not p:
        return {"ok": False, "msg": "No backup found."}
    with open(os.path.join(p, "files.json"), encoding="utf-8") as f:
        meta = json.load(f)
    _restore(p, meta["files"])
    try:
        _unhide(os.path.join(APP_DIR, "installed_update.json"))
        with open(os.path.join(APP_DIR, "installed_update.json"), "w", encoding="utf-8") as f:
            json.dump({"version": meta.get("from", ""), "at": "rollback"}, f)
        os.remove(os.path.join(WORK_DIR, "update_pending.json"))
    except OSError:
        pass
    return {"ok": True, "restored": len(meta["files"]), "backup": p}


def startup_guard(confirm_after=25):
    """Call at program start. If the last update never reached a healthy start twice, restore the backup."""
    pf = os.path.join(WORK_DIR, "update_pending.json")
    try:
        with open(pf, encoding="utf-8") as f:
            p = json.load(f)
    except Exception:
        return None
    if p.get("confirmed"):
        return None
    p["starts"] = int(p.get("starts", 0)) + 1
    if p["starts"] > 2:
        r = rollback()
        return {"rolled_back": True, **r}
    with open(pf, "w", encoding="utf-8") as f:
        json.dump(p, f)

    def ok():
        try:
            p["confirmed"] = True
            with open(pf, "w", encoding="utf-8") as f:
                json.dump(p, f)
        except OSError:
            pass
    t = threading.Timer(confirm_after, ok); t.daemon = True; t.start()
    return {"checking": True}


def restart_cmd():
    """Command that starts the program again exactly like the launcher did (same python, same environment)."""
    return [sys.executable, os.path.join(APP_DIR, "server.py")]


def spawn_restart(delay=1):
    """Start the new program only after THIS process has fully exited (wait for its exact PID), then start it again.
    Windows-safe: no inherited std handles (pythonw has none), tries to leave the launcher's job object, retries, and logs to restart.log."""
    try:
        import core as _c; _d=_c.DATA_DIR
    except Exception:
        _d=ROOT_DIR
    logp=os.path.join(_d, "restart.log")
    code=("import time,subprocess,sys,os\n"
          "pid=%d\n"
          "LOG=%r\n"
          "def log(m):\n"
          "    try:\n"
          "        open(LOG,'a').write(time.strftime('%%Y-%%m-%%d %%H:%%M:%%S ')+str(m)+'\\n')\n"
          "    except Exception: pass\n"
          "def alive():\n"
          "    if os.name=='nt':\n"
          "        import ctypes\n"
          "        h=ctypes.windll.kernel32.OpenProcess(0x100000,False,pid)\n"
          "        if not h: return False\n"
          "        r=ctypes.windll.kernel32.WaitForSingleObject(h,0);ctypes.windll.kernel32.CloseHandle(h);return r==258\n"
          "    try: os.kill(pid,0);return True\n"
          "    except OSError: return False\n"
          "end=time.time()+40\n"
          "while alive() and time.time()<end: time.sleep(0.3)\n"
          "time.sleep(%d+1.5)\n"
          "cmd=%r\n"
          "if os.name=='nt':\n"
          "    w=os.path.join(os.path.dirname(cmd[0]),'pythonw.exe')\n"
          "    if os.path.exists(w): cmd=[w]+cmd[1:]\n"
          "flagsets=[0x00000008|0x00000200|0x01000000,0x00000008|0x00000200,0x00000200,0] if os.name=='nt' else [0]\n"
          "ok=False\n"
          "for fl in flagsets:\n"
          "    try:\n"
          "        dn=subprocess.DEVNULL\n"
          "        subprocess.Popen(cmd,cwd=%r,stdin=dn,stdout=dn,stderr=dn,close_fds=True,creationflags=fl)\n"
          "        log('restarted flags=%%s cmd=%%s'%%(fl,cmd));ok=True;break\n"
          "    except Exception as e:\n"
          "        log('start failed flags=%%s: %%r'%%(fl,e))\n"
          "if not ok: log('could not restart: open the program from its icon')\n"
          ) % (os.getpid(), logp, delay, restart_cmd(), ROOT_DIR)
    exe = sys.executable
    if os.name == "nt":
        w = os.path.join(os.path.dirname(exe), "pythonw.exe")
        if os.path.exists(w): exe = w
    flagsets = [0x00000008 | 0x00000200 | 0x01000000, 0x00000008 | 0x00000200, 0x00000200, 0] if os.name == "nt" else [0]
    last = None
    for fl in flagsets:
        try:
            dn = subprocess.DEVNULL
            subprocess.Popen([exe, "-c", code], cwd=ROOT_DIR, env=os.environ.copy(), stdin=dn, stdout=dn, stderr=dn, creationflags=fl, close_fds=True)
            return
        except Exception as e:
            last = e
    raise last
