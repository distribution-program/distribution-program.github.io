"""Approved one-time second-admin provisioning, salted hash only."""
import json,sqlite3,hashlib,time
from pathlib import Path
NAME="Admi1"
KEYS=['delivery', 'search', 'new', 'und', 'details', 'reports', 'wh', 'rgr', 'inprocess', 'proposal', 'plans', 'other']
RECEIPT="v54_addon_admi1_completed"
PAYLOAD={'name': 'Admi1', 'hash': 'pbkdf2_sha256$240000$1b8eb314494e44e5b1eb93da70d8873f$f3987320058053dab07b87f62d2907b42f2ceda4447cdb94cde2f6cd00160a42'}
def apply(profile,payload):
 profile=Path(profile);dbfile=profile/'invoices_local.db'
 if not dbfile.is_file():raise ValueError('Existing profile database not found. Start the existing v54 application once first. Nothing changed.')
 lock=None
 cx=sqlite3.connect(str(dbfile),timeout=10)
 try:
  cx.execute('BEGIN IMMEDIATE')
  before=cx.execute('SELECT * FROM usr ORDER BY name').fetchall()
  found=cx.execute('SELECT name FROM usr WHERE upper(name)=upper(?)',(NAME,)).fetchall()
  done=cx.execute('SELECT v FROM meta WHERE k=?',(RECEIPT,)).fetchone()
  if found:
   cx.rollback()
   return 'Already provisioned here; existing account left unchanged.' if done else 'Name already exists. No account or password was overwritten. Ask for a collision check.'
  if payload.get('name')!=NAME or not str(payload.get('hash','')).startswith('pbkdf2_sha256$240000$'):raise ValueError('Invalid provisioning payload. Nothing changed.')
  uid='user_access_v54_'+hashlib.sha256(NAME.casefold().encode()).hexdigest()
  if cx.execute('SELECT 1 FROM lst WHERE name=?',(uid,)).fetchone():raise ValueError('An access record already exists for this name. Nothing changed.')
  now=time.time();record={'user':NAME,'role':'admin','allowed':KEYS,'updated':now}
  cx.execute('INSERT INTO usr(name,pw,updated,dirty) VALUES(?,?,?,1)',(NAME,payload['hash'],now))
  cx.execute('INSERT INTO lst(name,items,dirty) VALUES(?,?,1)',(uid,json.dumps(record)))
  cx.execute('INSERT OR REPLACE INTO meta(k,v) VALUES(?,?)',('list_updated:'+uid,str(now)))
  cx.execute('INSERT INTO meta(k,v) VALUES(?,?)',(RECEIPT,str(now)))
  after=cx.execute('SELECT * FROM usr WHERE name<>? ORDER BY name',(NAME,)).fetchall()
  if before!=after:raise ValueError('Existing-user preservation check failed. Rolling back.')
  cx.commit();return 'Admi1 added locally as a second admin. Existing users unchanged. Start v54 and let cloud sync finish; verify receipt on each other PC.'
 except Exception:
  cx.rollback();raise
 finally:cx.close()

def install(core):
    return apply(core.DATA_DIR,PAYLOAD)
