"""v54 per-user Home access. Existing accounts are never rewritten by installation."""
import hashlib,hmac,secrets,json,time
BUTTONS=[('delivery','Delivery Follow-up'),('search','Search Invoice'),('new','New Invoice'),('und','Undelivered'),('details','Invoice Details'),('reports','Invoice Report'),('wh','Warehouse Report'),('rgr','RGR Not Costed'),('inprocess','In Process Report'),('proposal','Proposal Report'),('plans','Plan Review'),('drvdel','Driver Deliveries'),('fbadmin','Firebase admin (Firebase and phone setup)'),('other','Other')]
KEYS={k for k,_ in BUTTONS}
def hash_password(value):
 salt=secrets.token_hex(16);digest=hashlib.pbkdf2_hmac('sha256',value.encode(),bytes.fromhex(salt),240000).hex()
 return 'pbkdf2_sha256$240000$'+salt+'$'+digest
def verify(value,stored):
 if stored.startswith('pbkdf2_sha256$'):
  try:
   _,n,salt,digest=stored.split('$');return hmac.compare_digest(hashlib.pbkdf2_hmac('sha256',value.encode(),bytes.fromhex(salt),int(n)).hex(),digest)
  except (ValueError,TypeError):return False
 return hmac.compare_digest(hashlib.sha256(value.encode()).hexdigest(),stored)
def is_admin(user):
 if str(user).upper()=='ADMIN':return True
 import core
 rows=core.q('SELECT items FROM lst WHERE name=?',(permission_uid(user),))
 try:return bool(rows and json.loads(rows[0][0]).get('role')=='admin')
 except (ValueError,TypeError):return False
def permission_uid(user):return 'user_access_v54_'+hashlib.sha256(str(user).casefold().encode()).hexdigest()
def get(core,user):
 if is_admin(user):return sorted(KEYS-{'fbadmin'})   # Firebase admin is never implied: only Admi1 grants it
 rows=core.q('SELECT items FROM lst WHERE name=?',(permission_uid(user),))
 if not rows:return sorted(KEYS-{'fbadmin'}) # Preserve every existing user's access until Admin chooses otherwise.
 try:return [x for x in json.loads(rows[0][0]).get('allowed',[]) if x in KEYS]
 except (ValueError,TypeError):return []
def has_fbadmin(core,user):
 try:
  rows=core.q('SELECT items FROM lst WHERE name=?',(permission_uid(user),))
  return bool(rows and 'fbadmin' in json.loads(rows[0][0]).get('allowed',[]))
 except (ValueError,TypeError):return False
def save(server,actor,user,allowed,expected):
 c=server.core
 if not is_admin(actor):return {'ok':False,'msg':'Only ADMIN can manage permissions.'}
 match=c.q('SELECT name FROM usr WHERE upper(name)=upper(?)',(user,))
 if len(match)!=1:return {'ok':False,'msg':'Choose one existing user.'}
 name=match[0][0]
 if is_admin(name):return {'ok':False,'msg':'ADMIN retains all permissions to prevent lockout.'}
 if not isinstance(allowed,list)or not set(allowed)<=KEYS:return {'ok':False,'msg':'Invalid permissions.'}
 uid=permission_uid(name)
 with c.LOCK:
  rows=c.q('SELECT items FROM lst WHERE name=?',(uid,));old=json.loads(rows[0][0])if rows else {}
  if old.get('updated',0)!=expected:return {'ok':False,'msg':'Permissions changed. Reopen this user before saving.'}
  if ('fbadmin' in allowed)!=('fbadmin' in get(c,name)):
   import firebase_tools
   if str(actor).casefold() not in firebase_tools.ALLOWED_USERS:return {'ok':False,'msg':'Only Admi1 can give or remove the Firebase admin permission.'}
  now=time.time();record={'user':name,'allowed':sorted(set(allowed)),'updated':now}
  c.q('INSERT OR REPLACE INTO lst VALUES(?,?,1)',(uid,json.dumps(record)))
  c.setmeta('list_updated:'+uid,now)
  server.bump();server.request_cloud();server.sync_now.set()
 return {'ok':True,'msg':'Permissions saved locally and queued for existing sync.'}
def revision(core,user):
 rows=core.q('SELECT items FROM lst WHERE name=?',(permission_uid(user),))
 return json.loads(rows[0][0]).get('updated',0) if rows else 0
def view_key(k):
 if k in {'home',''}:return None
 if k.startswith('group:'):
  try:return ['search','new','und','details','reports','wh','rgr'][int(k[6:])]
  except (ValueError,IndexError):return '__denied'
 if k=='s:Undelivered':return 'und'
 if k.startswith('s:'):return 'details'
 return {'rep:inprocess':'inprocess','rep:Proposal':'proposal','ho':'reports','rep':'reports','review':'plans'}.get(k,k)
def required(path,b):
 if path.startswith('/api/delivery/'):return ['delivery']
 if path in {'/api/review/plans','/api/review/open','/api/review/save'}:return ['plans']
 if path.startswith('/api/drvdel/'):return ['drvdel']
 if path.startswith('/api/finance/')or path.startswith('/api/exp/')or path in {'/api/review/cash','/api/sync/conflicts','/api/sync/conflicts/resolve'}:return ['other']
 if path=='/api/query/details':return ['und'] if b.get('flt')=='Undelivered' else ['search','details']
 if path=='/api/query/rgr':return ['rgr']
 if path in {'/api/query/route','/api/pdf/route'}:return ['proposal','reports'] if b.get('rep','Proposal')=='Proposal' else ['inprocess','reports']
 if path=='/api/pdf/ho':return ['reports']
 if path in {'/api/district/remaining','/api/delivery/review'}:return ['delivery']
 if path in {'/api/import/preview','/api/import/commit','/api/import/full','/api/import/full/status','/api/import/status'}:return ['details','new']
 if path=='/api/pdf/list':return ['rgr'] if b.get('view')=='rgr' else (['und'] if b.get('flt')=='Undelivered' else ['search','details'])
 if path.startswith('/api/warehouse/')or path in {'/api/query/wh','/api/query/pi','/api/pdf/wh','/api/pdf/pinv','/api/import/wh','/api/import/pi'}:return ['wh']
 if path in {'/api/new','/api/import/new','/api/import/classify'}:return ['new']
 if path in {'/api/edit','/api/edit/all','/api/bulk','/api/delete'}:return ['und','details','search','rgr','wh']
 return []
