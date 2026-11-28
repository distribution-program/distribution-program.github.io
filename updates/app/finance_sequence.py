"""Bounded sequential finance transport. Constructing this module starts no network."""
import threading,time
from finance_protocol import digest

class SequencedSync:
 def __init__(self,ledger,remote,checkpoint_key='finance_seq_v1',bootstrap_cap=2000):
  if type(bootstrap_cap) is not int or bootstrap_cap<2:raise ValueError('Read cap must be at least 2')
  self.ledger=ledger;self.remote=remote;self.key=checkpoint_key;self.cap=bootstrap_cap;self.lock=threading.RLock();self.stop=None;self.ready=False;self.error=None;self.rotate=False;self.generation=0;self.fatal=None
  self.changed=lambda:None
  with ledger.lock,ledger.db:
   ledger.db.execute('CREATE TABLE IF NOT EXISTS receive_log(seq INTEGER PRIMARY KEY,op_id TEXT UNIQUE,hash TEXT)')
   ledger.db.execute('CREATE TABLE IF NOT EXISTS sync_meta(key TEXT PRIMARY KEY,value TEXT)')
 def checkpoint(self):
  with self.ledger.lock:
   r=self.ledger.db.execute('SELECT value FROM sync_meta WHERE key=?',(self.key,)).fetchone();return int(r[0]) if r else 0
 def accept(self,envelopes):
  # Persist operations, receive sequence and contiguous checkpoint atomically.
  with self.lock,self.ledger.lock,self.ledger.db:
   for env in envelopes:
    if not isinstance(env,dict) or set(env)!={'v','seq','operation','hash'} or env['v']!=1 or type(env['seq']) is not int or env['seq']<1:raise ValueError('Invalid sequenced envelope')
    op=env['operation'];h=digest(op)
    if h!=env['hash']:raise ValueError('Envelope hash mismatch')
    self.ledger._valid(op)
    r=self.ledger.db.execute('SELECT op_id,hash FROM receive_log WHERE seq=?',(env['seq'],)).fetchone()
    if r and r!=(op['id'],h):raise ValueError('Server sequence collision')
    old=self.ledger.db.execute('SELECT seq,hash FROM receive_log WHERE op_id=?',(op['id'],)).fetchone()
    if old and old!=(env['seq'],h):raise ValueError('Operation assigned different sequence')
    result=self.ledger._put(op)
    if result=='quarantined':raise ValueError('Operation payload identity mismatch')
    self.ledger.db.execute('INSERT OR IGNORE INTO receive_log VALUES(?,?,?)',(env['seq'],op['id'],h))
   self.ledger._graph();cp=self.checkpoint()
   while self.ledger.db.execute('SELECT 1 FROM receive_log WHERE seq=?',(cp+1,)).fetchone():cp+=1
   self.ledger.db.execute('INSERT OR REPLACE INTO sync_meta VALUES(?,?)',(self.key,str(cp)))
  self.changed()
 def push(self):
  confirmed=0
  for op in self.ledger.pending():
   try:
    env=self.remote.append_once(op)
    if digest(env['operation'])!=digest(op):raise ValueError('Remote ID payload mismatch')
    self.accept([env]);self.ledger.ack(op['id'],digest(op));confirmed+=1
   except Exception as e:
    self.error=str(e)
    if isinstance(e,(ValueError,KeyError,TypeError)):self.fatal=self.error
    return {'confirmed':confirmed,'pending':len(self.ledger.pending()),'error':self.error,'fatal':bool(self.fatal)}
  self.error=None;return {'confirmed':confirmed,'pending':len(self.ledger.pending()),'error':None}
 def catch_up(self):
  if self.fatal:raise ValueError(self.fatal)
  start=self.checkpoint();received=0
  try:
   target=self.remote.head()
   if target<start:raise ValueError('Remote finance head is behind local checkpoint. Stop and reconcile.')
   if target-start>self.cap:raise ValueError('Finance catch-up exceeds approved read cap. Pending, no full scan.')
   while self.checkpoint()<target:
    before=self.checkpoint();page=self.remote.page(before,min(200,self.cap-received))
    if not page:raise ValueError('Finance server sequence gap. Reconciliation incomplete.')
    self.accept(page);received+=len(page)
    if self.checkpoint()==before:raise ValueError('Finance sequence gap. Reconciliation incomplete.')
    if received>=self.cap and self.checkpoint()<target:raise ValueError('Finance read cap reached.')
   if self.fatal:raise ValueError(self.fatal)
   self.ready=True;self.error=None;return {'ready':True,'received':received,'checkpoint':self.checkpoint()}
  except Exception as e:self.ready=False;self.error=str(e);raise
 def start(self):
  if self.fatal:raise ValueError(self.fatal)
  self.close();self.generation+=1;generation=self.generation;after=self.checkpoint();self.rotate=False
  try:
   if self.remote.head()-after>self.cap:raise ValueError('Finance bootstrap exceeds approved read cap.')
   def fail(error):
    if generation==self.generation:
     self.error=str(error);self.ready=False;self.rotate=True
     if isinstance(error,(ValueError,KeyError,TypeError)):self.fatal=self.error
     self.changed()
   def receive(envs):
    if generation!=self.generation:return
    try:
     self.accept(envs)
     # A new subscription starts after durable checkpoint. Never grow one indefinitely.
     if self.checkpoint()-after>=max(1,self.cap//2):self.rotate=True
    except Exception as e:fail(e)
   self.stop=self.remote.listen_after(after,receive,self.cap,fail)
   return self.catch_up()
  except Exception as e:self.close();self.error=str(e);raise
 def maintain(self):
  if self.rotate or not self.stop:return self.start()
  return self.catch_up()
 def close(self):
  self.generation+=1
  if self.stop:
   stop=self.stop;self.stop=None;stop()
  self.ready=False

class FirestoreSequenceRemote:
 """Injected SDK client. IAM, not client Security Rules, controls the server SDK."""
 def __init__(self,db,firestore_module,FieldFilter,ops_name='finance_v1_ops',meta_name='finance_v1_meta'):
  self.db=db;self.fs=firestore_module;self.filter=FieldFilter;self.ops=db.collection(ops_name);self.meta=db.collection(meta_name).document('head')
 def _head(self,data):
  if data is None:return 0
  if set(data)!={'v','seq'} or data['v']!=1 or type(data['seq']) is not int or data['seq']<0:raise ValueError('Finance server head/version invalid')
  return data['seq']
 def append_once(self,op):
  ref=self.ops.document(op['id'])
  @self.fs.transactional
  def write(tx):
   old=ref.get(transaction=tx)
   if old.exists:
    env=old.to_dict()
    if digest(env['operation'])!=digest(op):raise ValueError('Remote immutable operation mismatch')
    return env
   head=self.meta.get(transaction=tx)
   if not head.exists and list(self.ops.limit(1).stream(transaction=tx)):raise ValueError('Finance head missing for existing operations. Stop and reconcile.')
   seq=self._head(head.to_dict())+1
   env={'v':1,'seq':seq,'operation':op,'hash':digest(op)}
   tx.create(ref,env);tx.set(self.meta,{'v':1,'seq':seq});return env
  try:return write(self.db.transaction(max_attempts=5))
  except ValueError as error:
   # SDK wraps exhausted ABORTED transaction retries in ValueError. This is
   # transient contention, not corrupt data. Preserve the cause, retry later.
   from google.api_core.exceptions import Aborted
   if isinstance(error.__cause__,Aborted):raise RuntimeError('Finance transaction contention; pending retry') from error
   raise
 def head(self):return self._head(self.meta.get().to_dict())
 def page(self,after,limit):
  return [s.to_dict() for s in self.ops.where(filter=self.filter('seq','>',after)).order_by('seq').limit(limit).stream()]
 def listen_after(self,after,callback,cap,on_error):
  def receive(snapshots,changes,read_time):
   try:
    envs=[]
    for change in changes:
     name=getattr(change.type,'name',str(change.type))
     if name=='REMOVED':raise ValueError('Immutable finance operation was removed')
     if name in ('ADDED','MODIFIED'):envs.append(change.document.to_dict())
    if len(snapshots)>cap:raise RuntimeError('Finance live receive cap reached; re-arm from checkpoint.')
    if envs:callback(envs)
   except Exception as e:on_error(e)
  watch=self.ops.where(filter=self.filter('seq','>',after)).order_by('seq').limit(cap+1).on_snapshot(receive)
  return watch.unsubscribe
