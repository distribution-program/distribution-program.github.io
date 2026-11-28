"""Local immutable finance operation protocol. No network or invoice access."""
import sqlite3,json,hashlib,uuid,os,threading,functools,datetime
from decimal import Decimal

def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def digest(v):return hashlib.sha256(canonical(v).encode()).hexdigest()

class Ledger:
 def __init__(self,path,device):
  self.lock=threading.RLock();self.db=sqlite3.connect(path,check_same_thread=False);self.device=device
  self.db.executescript('CREATE TABLE IF NOT EXISTS op(id TEXT PRIMARY KEY,payload TEXT); CREATE TABLE IF NOT EXISTS outbox(id TEXT PRIMARY KEY); CREATE TABLE IF NOT EXISTS quarantine(id TEXT,payload TEXT,reason TEXT); CREATE TABLE IF NOT EXISTS migrated(source TEXT PRIMARY KEY,hash TEXT);');self.db.commit()
 def operations(self):return [json.loads(s) for s, in self.db.execute('SELECT payload FROM op ORDER BY id')]
 def _valid(self,o):
  if set(o)!={'v','id','entity','parents','value','actor','device','request'} or o['v']!=1:raise ValueError('Unsupported operation')
  if not all(isinstance(o[k],str) and o[k] for k in ['id','entity','actor','device','request']):raise ValueError('Missing identity')
  if not isinstance(o['parents'],list) or not all(isinstance(p,str) and p for p in o['parents']) or len(set(o['parents']))!=len(o['parents']) or o['id'] in o['parents']:raise ValueError('Bad parents')
  v=o['value']
  if not isinstance(v,dict):raise ValueError('Bad value')
  if o['entity'].startswith('entry:'):
   datetime.date.fromisoformat(v['date'])
   if 'entry_date' in v and v['date']!=v['entry_date']:raise ValueError('Entry dates disagree')
   if 'voided' in v and type(v['voided']) is not bool:raise ValueError('Invalid void state')
   for key in ('odometer','fuel_price','liters_receipt'):
    if str(v.get(key,'')).strip():
     d=Decimal(v[key])
     if not d.is_finite() or d<0 or (key!='odometer' and d==0) or d.as_tuple().exponent < -2:raise ValueError('Invalid '+key)
   if v['kind'] not in ('receipt','expense','return'):raise ValueError('Bad kind')
   a=Decimal(v['amount'])
   if not a.is_finite() or a<=0 or a.as_tuple().exponent < -2:raise ValueError('Bad amount')
  elif o['entity'].startswith('mark:'):
   if v.get('state') not in ('collected','not_yet'):raise ValueError('Bad collection mark')
  elif o['entity'].startswith('setting:'):
   if 'amount' in v:
    a=Decimal(v['amount'])
    if not a.is_finite() or a<0 or a.as_tuple().exponent < -2:raise ValueError('Bad setting amount')
    datetime.date.fromisoformat(v['date'])
   else:
    if not isinstance(v.get('value'),str) or not v['value'].strip() or v.get('key') not in ('currency','opening_balance','fuel_price'):raise ValueError('Bad setting')
    key=v['key'];expected='setting:'+key+(':'+v.get('effective_from','') if key!='currency' else '')
    if o['entity']!=expected:raise ValueError('Setting entity mismatch')
    if key!='currency':
     datetime.date.fromisoformat(v['effective_from']);a=Decimal(v['value'])
     if not a.is_finite() or a<0 or (key=='fuel_price' and a==0) or a.as_tuple().exponent < -2:raise ValueError('Invalid setting amount')
  else:raise ValueError('Bad entity')
 def _put(self,o,local=False):
  self._valid(o);raw=canonical(o);old=self.db.execute('SELECT payload FROM op WHERE id=?',(o['id'],)).fetchone()
  if old:
   if old[0]!=raw:
    self.db.execute('INSERT INTO quarantine VALUES(?,?,?)',(o['id'],raw,'ID payload mismatch'));return 'quarantined'
   return 'replay'
  for p in o['parents']:
   parent=self.db.execute('SELECT payload FROM op WHERE id=?',(p,)).fetchone()
   if parent and json.loads(parent[0])['entity']!=o['entity']:raise ValueError('Cross-entity parent')
  self.db.execute('INSERT INTO op VALUES(?,?)',(o['id'],raw))
  if local:self.db.execute('INSERT INTO outbox VALUES(?)',(o['id'],))
  return 'inserted'
 def create(self,entity,value,actor,request,parents=None):
  opid=hashlib.sha256((self.device+'|'+request).encode()).hexdigest()
  old=self.db.execute('SELECT payload FROM op WHERE id=?',(opid,)).fetchone()
  if old:
   o=json.loads(old[0])
   if (o['entity'],o['value'],o['actor'])!=(entity,value,actor):raise ValueError('Request reused with changed contents')
   return o
  o={'v':1,'id':opid,'entity':entity,'parents':parents if parents is not None else self.heads(entity),'value':value,'actor':actor,'device':self.device,'request':request}
  with self.db:
   self._put(o,True);self._graph()
  return o
 def receive(self,ops):
  # Validate complete batch before any write. Unknown parents remain pending, not silently treated as roots.
  for o in ops:self._valid(o)
  with self.db:
   result=[self._put(o) for o in ops];self._graph();return result
 def _graph(self):
  ops={o['id']:o for o in self.operations()};colors={}
  def visit(oid):
   if colors.get(oid)==1:raise ValueError('Cyclic revision graph')
   if colors.get(oid)==2:return
   colors[oid]=1;o=ops[oid]
   for p in o['parents']:
    if p in ops:
     if ops[p]['entity']!=o['entity']:raise ValueError('Cross-entity parent')
     visit(p)
   colors[oid]=2
  for oid in ops:visit(oid)
 def pending(self):return [json.loads(s) for s, in self.db.execute('SELECT payload FROM op JOIN outbox USING(id) ORDER BY id')]
 def ack(self,opid,confirmed_hash):
  row=self.db.execute('SELECT payload FROM op WHERE id=?',(opid,)).fetchone()
  if not row or digest(json.loads(row[0]))!=confirmed_hash:raise ValueError('Unverified acknowledgement')
  with self.db:self.db.execute('DELETE FROM outbox WHERE id=?',(opid,))
 def heads(self,entity):
  ops=[o for o in self.operations() if o['entity']==entity];parents={p for o in ops for p in o['parents']}
  return sorted(o['id'] for o in ops if o['id'] not in parents)
 def view(self):
  ops=self.operations();byid={o['id']:o for o in ops};entities=sorted({o['entity'] for o in ops});conflicts=[];missing=[];resolved={}
  tainted={i for i, in self.db.execute('SELECT DISTINCT id FROM quarantine')}
  for ent in entities:
   es=[o for o in ops if o['entity']==ent];heads=self.heads(ent)
   if any(p not in byid or byid[p]['entity']!=ent for o in es for p in o['parents']):missing.append(ent);continue
   if len(heads)!=1 or any(o['id'] in tainted for o in es):conflicts.append(ent);continue
   resolved[ent]=byid[heads[0]]['value']
  opening=resolved.get('setting:opening');balance=Decimal(opening['amount']) if opening else None
  for ent,v in resolved.items():
   if ent.startswith('entry:') and not v.get('voided') and balance is not None:
    if v['date']<opening['date']:missing.append(ent);continue
    balance+=(Decimal(v['amount']) if v['kind']=='receipt' else -Decimal(v['amount']))
  certain=not conflicts and not missing
  return {'resolved':resolved,'conflicts':conflicts,'pending_parents':missing,'balance':str(balance) if certain and balance is not None else None,'provisional':not certain,'pending_upload':len(self.pending())}
 def backup(self,path):
  content={'version':1,'operations':self.operations(),'quarantine':[list(x) for x in self.db.execute('SELECT * FROM quarantine ORDER BY id,payload')],'migrations':[list(x) for x in self.db.execute('SELECT * FROM migrated ORDER BY source')]}
  envelope={'manifest':{'count':len(content['operations']),'sha256':digest(content)},'content':content}
  temp=path+'.tmp'
  with open(temp,'w') as f:json.dump(envelope,f);f.flush();os.fsync(f.fileno())
  os.replace(temp,path)
 def restore(self,path):
  with open(path)as f:e=json.load(f)
  c=e['content']
  if c['version']!=1 or e['manifest']!={'count':len(c['operations']),'sha256':digest(c)}:raise ValueError('Backup integrity/version mismatch')
  for o in c['operations']:self._valid(o)
  with self.db:
   results=[self._put(o,True) for o in c['operations']];self._graph()
   for row in c['quarantine']:
    if not self.db.execute('SELECT 1 FROM quarantine WHERE id=? AND payload=? AND reason=?',row).fetchone():self.db.execute('INSERT INTO quarantine VALUES(?,?,?)',row)
   for source,h in c['migrations']:
    old=self.db.execute('SELECT hash FROM migrated WHERE source=?',(source,)).fetchone()
    if old and old[0]!=h:raise ValueError('Migration provenance mismatch')
    self.db.execute('INSERT OR IGNORE INTO migrated VALUES(?,?)',(source,h))
  return results
 def migrate(self,source,rows):
  h=digest(rows);old=self.db.execute('SELECT hash FROM migrated WHERE source=?',(source,)).fetchone()
  if old:
   if old[0]!=h:raise ValueError('Migration source changed')
   return
  # Caller retains the original backup. Deterministic IDs make interrupted/repeated migration idempotent.
  with self.db:
   for row in rows:
    for r in row['revisions']:
     entity='entry:'+row['entry_id'];request='migration:'+source+':'+row['entry_id']+':'+str(r['rev']);opid=hashlib.sha256(request.encode()).hexdigest();parents=[] if r['rev']==1 else [hashlib.sha256(('migration:'+source+':'+row['entry_id']+':'+str(r['rev']-1)).encode()).hexdigest()]
     self._put({'v':1,'id':opid,'entity':entity,'parents':parents,'value':r['value'],'actor':r['actor'],'device':'migration','request':request},True)
   self._graph();self.db.execute('INSERT INTO migrated VALUES(?,?)',(source,h))

# Serialize each profile's local transactions, including nested helper calls.
def _locked(method):
 @functools.wraps(method)
 def run(self,*a,**k):
  with self.lock:return method(self,*a,**k)
 return run
for _name in ('operations','create','receive','pending','ack','heads','view','backup','restore','migrate'):
 setattr(Ledger,_name,_locked(getattr(Ledger,_name)))
