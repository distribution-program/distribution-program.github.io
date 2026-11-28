"""Distribution Program desktop window, shortcut and per-profile single-instance handling.
Designed & developed by Eng. Kirollos William (c) 2026.
No installer, admin privilege or security-policy changes.
"""
import os, sys, json, time, pathlib, subprocess, urllib.request, tempfile, atexit, uuid, re

_LOCK = None
_STATE = None
INSTANCE = uuid.uuid4().hex
LOGDIR = None
def dplog(msg):
    """Launcher log: <profile folder>\\launcher.log (kept small). Never raises."""
    try:
        if not LOGDIR: return
        p=os.path.join(LOGDIR,'launcher.log')
        if os.path.exists(p) and os.path.getsize(p)>300000: os.replace(p,p+'.old')
        with open(p,'a',encoding='utf-8') as lg: lg.write('%s pid=%s %s\n'%(time.strftime('%Y-%m-%d %H:%M:%S'),os.getpid(),msg))
    except Exception: pass

def notify(message):
    if os.name == 'nt':
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, str(message), 'Distribution Program', 0x40)
    else:
        print(message, file=sys.stderr)

def _read_status(url):
    try:
        if not url.startswith('http://127.0.0.1:'):
            return None
        with urllib.request.urlopen(url+'api/status', timeout=0.5) as r:
            obj=json.load(r)
        return obj if obj.get('company') and str(obj.get('title','')).startswith(('Distribution Program',)) else None
    except Exception:
        return None

def same_scope(status,data_dir):
    """Known MAIN and kw20 REPLICA may coexist. Unknown legacy scope fails closed."""
    here='REPLICA' if 'Firebase_Replica_' in str(data_dir) else 'MAIN'
    remote=status.get('scope')
    if not remote:
        ct=status.get('connected_test')
        remote='REPLICA' if isinstance(ct,dict) and ct.get('replica') else 'MAIN' if ct is None else 'UNKNOWN'
    return here==remote or remote=='UNKNOWN'

def claim_instance(data_dir, trial, version):
    """Lock only the selected profile. Never kill an older program or alter its data."""
    global _LOCK, _STATE, LOGDIR
    folder=pathlib.Path(data_dir);folder.mkdir(parents=True,exist_ok=True)
    LOGDIR=str(folder)
    dplog('START version=%s trial=%s exe=%s cwd=%s argv=%s data=%s env_test=%s env_limit=%s'%(version,trial,sys.executable,os.getcwd(),sys.argv,data_dir,os.environ.get('DPROGRAM_TEST_MODE'),os.environ.get('DPROGRAM_TRIAL_LIMIT')))
    _STATE=folder/'desktop_instance.json'
    # Windows byte-range locks deny reads as well as writes. Claim the byte
    # before inspecting/initializing it; a second launch must reach reuse logic.
    f=open(folder/'desktop_instance.lock','a+b');f.seek(0)
    try:
        if os.name=='nt':
            import msvcrt
            msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except (OSError,IOError):
        dplog('lock busy: another instance holds it, trying to reuse it')
        f.close()
        for _ in range(20):
            try:
                state=json.loads(_STATE.read_text())
                if not re.fullmatch(r'http://127\.0\.0\.1:[0-9]{1,5}/',state.get('url','')): raise ValueError('Invalid local endpoint')
                with urllib.request.urlopen(state['url']+'api/instance', timeout=0.5) as r: live=json.load(r)
                if live.get('instance')==state.get('instance') and live.get('trial')==trial:
                    dplog('reuse: live instance %s url=%s window_pid=%s'%(live.get('version'),state.get('url'),state.get('window_pid')))
                    if live.get('version') != version:
                        notify('An older Distribution Program version is still running for this profile. Close that program first, then start the updated version. No data was changed.')
                    elif not focus_existing(state):
                        open_window(state['url'],data_dir,trial)
                        # Stay alive while the window we just opened is open: the launcher that started THIS process ends it (and may end its
                        # children) as soon as it exits, which closed the new window at once on the second start.
                        wait_for_window()
                    return False
            except Exception:
                time.sleep(.15)
        dplog('reuse failed after 20 tries: no live instance answered')
        notify('Distribution Program is already starting or running for this profile. Wait a moment, then try its icon again. If it is stuck, close its existing command window. No data was changed.')
        return False
    # msvcrt permits locking a byte beyond EOF. Initialize only after owning it.
    if os.fstat(f.fileno()).st_size == 0:
        f.write(b'0');f.flush()
    _LOCK=f
    dplog('lock acquired, this is the first instance')
    # Older packages have no lock. Detect the known legacy listening ports before sync threads start.
    if os.name=='nt':
        for port in [8078,8079,8730,8731,8732]:
            old=_read_status('http://127.0.0.1:'+str(port)+'/')
            if old is not None and bool(old.get('test_mode'))==trial and same_scope(old,data_dir):
                notify('Another Distribution Program is still running for this profile. Close its command window (closing its browser tab is not enough), then start this updated version. No data was changed.')
                f.close();_LOCK=None
                return False
    return True

WINDOW_PROC=None
WATCH_PROC=None  # native window helper only: when it ends the whole program must end (a browser app window can hand off and exit early)
WATCH_PROFILE=None
def remember_window(proc):
    """Keep the window process (exact PID) so Update can close it and a second launch can find it."""
    global WINDOW_PROC
    WINDOW_PROC=proc
    try:
        if _STATE and _STATE.exists():
            d=json.loads(_STATE.read_text());d['window_pid']=proc.pid
            t=_STATE.with_suffix('.tmp');t.write_text(json.dumps(d),encoding='utf-8');os.replace(t,_STATE)
    except Exception: pass

def close_window():
    p=WINDOW_PROC
    if p is None: return
    try:
        if p.poll() is None:
            p.terminate()
            try: p.wait(3)
            except Exception: p.kill()
    except Exception: pass

def wait_for_window():
    p=WINDOW_PROC
    if p is None: return
    dplog('second start: waiting for the window it opened (pid %s)'%getattr(p,'pid','?'))
    try:
        p.wait()
    except Exception as e:
        dplog('wait error %r'%(e,))
    dplog('second start: its window was closed')

def focus_existing(state):
    """Second launch: show the already open window (restore if minimised, bring to front). False = no window found."""
    if os.name!='nt': return False
    try:
        import ctypes
        from ctypes import wintypes
        u=ctypes.windll.user32; pid=state.get('window_pid'); found=[]
        if not pid: return False
        proto=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
        def cb(h,_):
            p=wintypes.DWORD(0);u.GetWindowThreadProcessId(h,ctypes.byref(p))
            if p.value==pid and u.GetWindowTextLengthW(h) and u.IsWindowVisible(h): found.append(h)
            return True
        u.EnumWindows(proto(cb),0)
        if not found: return False
        h=found[0]
        if u.IsIconic(h): u.ShowWindow(h,9)
        u.ShowWindow(h,5);u.SetForegroundWindow(h)
        try: u.FlashWindow(h,True)
        except Exception: pass
        return True
    except Exception: return False

def publish_instance(url, trial, version):
    if _STATE:
        temp=_STATE.with_suffix('.tmp')
        temp.write_text(json.dumps({'url':url,'trial':trial,'version':version,'pid':os.getpid(),'instance':INSTANCE}),encoding='utf-8')
        os.replace(temp,_STATE)

def _cleanup():
    if _STATE and _LOCK:
        try:
            if json.loads(_STATE.read_text()).get('instance')==INSTANCE: _STATE.unlink()
        except Exception: pass
    if _LOCK:
        try: _LOCK.close()
        except Exception: pass
atexit.register(_cleanup)

def browser_candidates():
    """Prefer Chrome, then Edge, using verified installed executable paths only."""
    if os.name!='nt': return []
    candidates=[]
    try:
        import winreg
        for exe in ('chrome.exe','msedge.exe'):
            for hive in (winreg.HKEY_CURRENT_USER,winreg.HKEY_LOCAL_MACHINE):
                try:
                    with winreg.OpenKey(hive,'SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\'+exe) as k:
                        candidates.append(winreg.QueryValue(k,None).strip('"'))
                except OSError: pass
    except ImportError: pass
    # Keep Chrome ahead of Edge even if both are in standard installation paths.
    for vendor in ('Google/Chrome/Application/chrome.exe','Microsoft/Edge/Application/msedge.exe'):
        for root in ('LOCALAPPDATA','PROGRAMFILES','PROGRAMFILES(X86)'):
            if os.environ.get(root): candidates.append(os.path.join(os.environ[root],*vendor.split('/')))
    found=list(dict.fromkeys(p for p in candidates if os.path.isfile(p)))
    return sorted(found,key=lambda p: 0 if pathlib.Path(p).name.lower()=='chrome.exe' else 1)

def _free_profile(prof):
    """Windows: stop only leftover WebView2 processes that use THIS program's own WebView2Profile folder."""
    if os.name != 'nt': return
    try:
        ps = ("Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine.Contains($env:DP_PROFILE) } "
              "| ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }")
        env = dict(os.environ); env['DP_PROFILE'] = prof
        dplog('cleanup: stopping leftover WebView2 processes of '+prof)
        subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-WindowStyle', 'Hidden', '-Command', ps], env=env, timeout=15,
                       creationflags=0x08000000, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(0.5)
    except Exception: pass


def native_window(url, data_dir, is_windows=None):
    """Experimental: show the program in its own native window (Microsoft WebView2) instead of a browser window.
    Returns True when a native window is running or was used and closed. False means: use the browser window.
    Switch off by creating an empty file named native_window.off beside MAIN.exe / REPLICA.exe."""
    if is_windows is None: is_windows = os.name == 'nt'
    if not is_windows or os.environ.get('DPROGRAM_NO_NATIVE') == '1': return False
    try:
        app = pathlib.Path(__file__).resolve().parent
        bundle = app.parent
        exe = app / 'DistributionProgramWindow.exe'
        if not exe.is_file() or (bundle / 'native_window.off').exists(): return False
        title = 'Distribution Program Trial' if os.environ.get('DPROGRAM_TRIAL_LIMIT') else 'Distribution Program REPLICA' if os.environ.get('DPROGRAM_REPLICA_CONFIG') else 'Distribution Program'
        icon = bundle / 'dp.ico'
        prof = os.path.join(data_dir, 'WebView2Profile')
        args = [str(exe), '-url', url, '-title', title, '-data', prof]
        if icon.is_file(): args += ['-icon', str(icon)]
        for attempt in range(2):
            # A window helper or browser process left over from a stopped run keeps the profile busy and the new window closes at once.
            _free_profile(prof)
            try: errf = open(os.path.join(data_dir, 'window_helper.log'), 'ab')
            except Exception: errf = subprocess.DEVNULL
            proc = subprocess.Popen(args, creationflags=0x08000000 if os.name == 'nt' else 0, stdout=errf, stderr=errf, stdin=subprocess.DEVNULL)
            dplog('native window helper started pid=%s attempt=%s'%(proc.pid,attempt+1))
            remember_window(proc)
            quick = False
            for _ in range(40):  # a missing/blocked WebView2 runtime, or a busy profile, ends the helper within a moment
                time.sleep(0.1)
                if proc.poll() is not None:
                    quick = True
                    break
            if not quick:
                dplog('native window running')
                global WATCH_PROC,WATCH_PROFILE
                WATCH_PROC=proc;WATCH_PROFILE=prof
                return True
            try:
                with open(os.path.join(data_dir, 'window.log'), 'a', encoding='utf-8') as lg:
                    lg.write(time.strftime('%Y-%m-%d %H:%M:%S') + ' native window ended within 4 s, code ' + str(proc.returncode) + ', attempt ' + str(attempt + 1) + '\n')
            except Exception: pass
            time.sleep(1.0)
        dplog('native window failed twice, using Edge/Chrome app window')
        return False  # fall back to the Edge/Chrome app window so the program always opens
    except Exception as e:
        dplog('native_window error: %r'%(e,))
        return False

def maximize_window_later(title_part='Distribution Program', seconds=12):
    """Windows only: when the program window appears, maximize it (always opens full screen)."""
    if os.name != 'nt': return
    import threading
    def work():
        try:
            import ctypes
            from ctypes import wintypes
            u = ctypes.windll.user32
            found = []
            proto = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            def cb(h, _):
                if u.IsWindowVisible(h):
                    n = u.GetWindowTextLengthW(h)
                    if n:
                        b = ctypes.create_unicode_buffer(n + 1); u.GetWindowTextW(h, b, n + 1)
                        if b.value.startswith(title_part) and not u.IsZoomed(h): found.append(h)
                return True
            end = time.time() + seconds
            while time.time() < end:
                found.clear(); u.EnumWindows(proto(cb), 0)
                if found:
                    for h in found: u.ShowWindow(h, 3)
                    return
                time.sleep(0.4)
        except Exception:
            pass
    threading.Thread(target=work, daemon=True).start()

def open_window(url, data_dir, trial):
    if os.environ.get('DPROGRAM_NO_BROWSER')=='1': return True
    if native_window(url, data_dir): return True
    dplog('opening browser app window; candidates=%s'%(browser_candidates(),))
    for browser in browser_candidates():
        try:
            # A separate user-owned profile keeps normal/trial browser state apart.
            args=[browser,'--app='+url,'--user-data-dir='+os.path.join(data_dir,'BrowserProfile'),
                  '--no-first-run','--no-default-browser-check','--start-maximized','--disable-features=Translate,msEdgeTranslate','--disable-extensions']
            remember_window(subprocess.Popen(args,creationflags=0x08000000 if os.name=='nt' else 0))
            dplog('browser app window started: '+browser)
            maximize_window_later()
            return True
        except OSError: pass
    import webbrowser
    webbrowser.open(url)
    if os.name=='nt':
        notify('Chrome or Edge was not available to open a standalone window. Distribution Program opened in your default browser instead. Use Desktop icon to create the launcher shortcut. No browser was installed or security policy changed.')
    return False

def create_shortcut(trial=False):
    if os.name!='nt':
        return {'ok':False,'msg':'Desktop shortcuts are available on Windows. The shortcut starts the local program, not just its web address.'}
    import ctypes
    buf=ctypes.create_unicode_buffer(32768)
    result=ctypes.windll.shell32.SHGetFolderPathW(None,0x10,None,0,buf)
    if result!=0 or not buf.value:
        return {'ok':False,'msg':'Windows could not locate your Desktop. No shortcut was created.'}
    bundle=pathlib.Path(__file__).resolve().parent.parent
    replica=bool(os.environ.get('DPROGRAM_REPLICA_CONFIG'))
    target=bundle/('Distribution Program Trial.exe' if os.environ.get('DPROGRAM_TRIAL_LIMIT') else 'REPLICA.exe' if replica else 'MAIN.exe')
    if not target.is_file():
        return {'ok':False,'msg':'MAIN.exe / REPLICA.exe was not found beside the app folder. Keep the extracted folder together.'}
    name='Distribution Program Trial' if os.environ.get('DPROGRAM_TRIAL_LIMIT') else 'Distribution Program REPLICA' if replica else ('Distribution Program Isolated Trial' if trial else 'Distribution Program')
    shortcut=pathlib.Path(buf.value)/(name+'.lnk')
    def vb(s): return '"'+str(s).replace('"','""')+'"'
    script='\r\n'.join([
        'Set sh = CreateObject("WScript.Shell")',
        'Set link = sh.CreateShortcut('+vb(shortcut)+')',
        'link.TargetPath = '+vb(target),
        'link.Arguments = '+vb('--trial' if trial else ''),
        'link.WorkingDirectory = '+vb(bundle),
        'link.IconLocation = '+vb(str(bundle/'dp.ico')+',0'),
        'link.Description = '+vb(name+' - starts the local application'),
        'link.Save'])
    fd,path=tempfile.mkstemp(suffix='.vbs');os.close(fd)
    try:
        pathlib.Path(path).write_bytes(b'\xff\xfe'+script.encode('utf-16le'))
        p=subprocess.run(['cscript.exe','//nologo',path],capture_output=True,timeout=15,creationflags=0x08000000)
        if p.returncode or not shortcut.exists():
            return {'ok':False,'msg':'Windows did not create the shortcut. Your company policy may restrict shortcuts/scripts. No policy was changed. You can still start Distribution Program from its extracted folder.'}
        return {'ok':True,'msg':name+' shortcut created on your Desktop. Keep this extracted Distribution Program folder in place. The shortcut starts its server before opening the window. Closing the window leaves the local program running; use Quit to stop it.'}
    except Exception:
        return {'ok':False,'msg':'Windows could not create the shortcut. No security settings were changed. You can still start the app from its extracted folder.'}
    finally:
        try: os.remove(path)
        except OSError: pass
