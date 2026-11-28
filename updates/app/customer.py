"""Customer setup for the public edition with a Full license: own users, own Firebase key file.
Never active for the company programs (core.TRIAL_LIMIT is 0 there) or without a Full license."""
import json,os,re,time,shutil,secrets
def active(server):
    return bool(server.core.TRIAL_LIMIT and server.lic_full())
def own_users(core):
    return [r[0] for r in core.q("SELECT name FROM usr WHERE upper(name) NOT IN ('ADMIN','GUEST','ADMI1') ORDER BY name")]
def login_required(server):
    """Once the customer has created his own user, the built-in trial ADMIN no longer opens the program by itself."""
    return active(server) and server.core.db is not None
def make_admin_role(server,name):
    c=server.core;import access_control
    uid=access_control.permission_uid(name);now=time.time()
    c.q('INSERT OR REPLACE INTO lst VALUES(?,?,1)',(uid,json.dumps({'user':name,'role':'admin','allowed':sorted(access_control.KEYS-{'fbadmin'}),'updated':now})))
    c.setmeta('list_updated:'+uid,now)
def add_user(server,actor,b):
    import access_control
    if not active(server):return {'ok':False,'msg':'User management needs the Full license.'}
    if not access_control.is_admin(actor):return {'ok':False,'msg':'Only an administrator can manage users.'}
    c=server.core;n=str(b.get('name','')).strip().upper();p=str(b.get('pw',''))
    if not n or not p:return {'ok':False,'msg':'Name and password are required.'}
    if len(p)<6:return {'ok':False,'msg':'Password must be at least 6 characters.'}
    if not re.fullmatch(r"[A-Z0-9 ._-]{2,40}",n):return {'ok':False,'msg':'User name: English letters, digits, space . _ - (2 to 40).'}
    if n in ('ADMIN','GUEST','ADMI1'):return {'ok':False,'msg':'Choose a different name.'}
    if c.q('SELECT 1 FROM usr WHERE upper(name)=upper(?)',(n,)):return {'ok':False,'msg':'This user already exists. Nothing changed.'}
    first=False;role='admin' if b.get('admin') else 'user'
    c.q('INSERT INTO usr VALUES(?,?,?,1)',(n,access_control.hash_password(p),time.time()))
    if role=='admin':make_admin_role(server,n)
    try:server.request_cloud();server.sync_now.set()
    except Exception:pass
    return {'ok':True,'role':role,'first':first,'msg':'User created.'}
def check_key(text):
    try:d=json.loads(text)
    except Exception:return None,'This is not a valid JSON file.'
    if not isinstance(d,dict) or d.get('type')!='service_account':return None,'This is not a Firebase service account key file (type must be service_account).'
    for k in ('project_id','private_key','client_email'):
        if not str(d.get(k,'')).strip():return None,'The key file has no '+k+'.'
    if not str(d['private_key']).strip().startswith('-----BEGIN'):return None,'The private key in the file looks damaged.'
    if d['project_id']=='car-distribution':return None,'This public edition never connects to the company project.'
    return d,''
def save_key(server,actor,b):
    import access_control
    if not active(server):return {'ok':False,'msg':'Uploading a key file needs the Full license.'}
    if not access_control.is_admin(actor):return {'ok':False,'msg':'Only an administrator can upload the key file.'}
    d,err=check_key(str(b.get('text','')))
    if err:return {'ok':False,'msg':err}
    path=server.core.CREDENTIAL_PATH
    if os.path.exists(path):shutil.copyfile(path,path+'.bak-'+time.strftime('%Y%m%d-%H%M%S'))
    tmp=path+'.new'
    with open(tmp,'w',encoding='utf-8') as fh:json.dump(d,fh)
    os.replace(tmp,path)
    try:os.chmod(path,0o600)
    except Exception:pass
    return {'ok':True,'project':d['project_id'],'msg':'Key file saved for project '+d['project_id']+'. Restart the program once to connect.'}
def restart(server,actor,httpd):
    import access_control,updater,threading
    if not active(server) or not access_control.is_admin(actor):return {'ok':False,'msg':'Not allowed.'}
    server.RESTARTING=True
    try:
        updater.spawn_restart()
        server._boot('restart requested: helper spawned')
    except Exception as e:
        server._boot('restart helper FAILED: %r'%(e,))
        server.RESTARTING=False
        return {'ok':False,'msg':'Could not restart automatically. Close the program and open it again from its icon. The key file is saved.'}
    import desktop_app
    threading.Timer(0.3,desktop_app.close_window).start();threading.Timer(0.8,httpd.shutdown).start()
    return {'ok':True}

def phone_code(server,actor,b):
    import access_control,base64,firebase_tools
    if not active(server):return {'ok':False,'msg':'Needs the Full license.'}
    if not access_control.is_admin(actor):return {'ok':False,'msg':'Only an administrator.'}
    prj=firebase_tools.PRJ();key=str(b.get('apiKey','')).strip();co=str(b.get('company','')).strip()
    if b.get('load'):
        # reopen the screen: give back what was saved (only if it belongs to the Firebase project that is connected now)
        try:sv=json.loads(server.core.meta('phone_code_cfg','') or '{}')
        except Exception:sv={}
        if sv and sv.get('project')==prj and sv.get('code'):return {'ok':True,'saved':True,'apiKey':sv.get('apiKey',''),'company':sv.get('company',''),'code':sv['code'],'project':prj}
        return {'ok':True,'saved':False}
    if prj in ('','-'):return {'ok':False,'msg':'Upload the Firebase key file and restart first.'}
    if not re.fullmatch(r'AIza[0-9A-Za-z_-]{35}',key):return {'ok':False,'msg':'The Web API key looks wrong. It starts with AIza and has 39 characters (Firebase console > Project settings > General).'}
    if not co or len(co)>60:return {'ok':False,'msg':'Type your company name (up to 60 characters).'}
    raw=json.dumps({'v':1,'project':prj,'apiKey':key,'domain':firebase_tools.EMAIL_DOMAIN,'company':co},separators=(',',':'),ensure_ascii=False).encode('utf-8')
    code='DPC1-'+base64.urlsafe_b64encode(raw).decode().rstrip('=')
    try:server.core.setmeta('phone_code_cfg',json.dumps({'project':prj,'apiKey':key,'company':co,'code':code},ensure_ascii=False))   # kept so the screen shows them again next time
    except Exception:pass
    return {'ok':True,'code':code,'project':prj}

def del_user(server,actor,b):
    import access_control
    c=server.core
    if not active(server):return {'ok':False,'msg':'User management needs the Full license.'}
    if not access_control.is_admin(actor):return {'ok':False,'msg':'Only an administrator can manage users.'}
    n=str(b.get('name',''))
    rows=c.q('SELECT name FROM usr WHERE name=?',(n,))
    if not rows:return {'ok':False,'msg':'User not found. Nothing changed.'}
    n=rows[0][0]
    if n.upper() in ('ADMIN','GUEST'):return {'ok':False,'msg':'This built-in user cannot be deleted.'}
    if n.upper()==str(actor).upper():return {'ok':False,'msg':'You cannot delete the user you are signed in as. Sign in as another administrator first.'}
    left=[r[0] for r in c.q("SELECT name FROM usr WHERE upper(name) NOT IN ('ADMIN','GUEST') AND name<>?",(n,)) if access_control.is_admin(r[0])]
    if not left:return {'ok':False,'msg':'This is the last administrator. Create another administrator first, so nobody is locked out.'}
    c.q('DELETE FROM usr WHERE name=?',(n,));c.q("INSERT INTO del VALUES('users',?)",(n,))
    try:server.request_cloud();server.sync_now.set()
    except Exception:pass
    return {'ok':True,'msg':'User deleted.'}
