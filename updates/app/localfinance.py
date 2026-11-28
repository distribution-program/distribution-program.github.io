"""Local immutable finance adapter. No automatic real-profile migration.
Live transport is started separately only by the approved app rollout gate.
"""
import sys,os,tempfile,time,uuid,json,sqlite3,threading
from decimal import Decimal
import expenses as X
from finance_protocol import Ledger,digest

class Finance:
 def __init__(self,path):
  self.lock=threading.RLock()
  self.ops=Ledger(path,'pending')
  self.ops.db.execute('CREATE TABLE IF NOT EXISTS profile(key TEXT PRIMARY KEY,value TEXT)')
  row=self.ops.db.execute("SELECT value FROM profile WHERE key='device'").fetchone()
  if not row:
   row=(uuid.uuid4().hex,);self.ops.db.execute("INSERT INTO profile VALUES('device',?)",row);self.ops.db.commit()
  self.ops.device=row[0]
 def _request(self,request):
  return next((o for o in self.ops.operations() if o['device']==self.ops.device and o['request']==request),None)
 def migrate_legacy(self,path):
  # No normal-profile caller until rollout approval. Retain an exact SQLite backup first.
  if not os.path.isfile(path):return {'entries':0,'settings':0}
  import hashlib
  source=sqlite3.connect(path)
  try:
   revisions=source.execute('SELECT * FROM exp_rev ORDER BY entry_id,rev').fetchall()
   configs=source.execute('SELECT key,value,effective_from,by_user,at FROM exp_cfg ORDER BY at,rowid').fetchall()
   fingerprint=digest({'revisions':revisions,'configs':configs})
   marker='legacy-expenses:v1'
   old=self.ops.db.execute('SELECT hash FROM migrated WHERE source=?',(marker,)).fetchone()
   if old:
    if old[0]!=fingerprint:raise ValueError('Legacy expense store changed after migration. Reconcile before continuing.')
    return {'entries':0,'settings':0,'already_migrated':True}
   backup=path+'.before_finance_v1'
   if not os.path.exists(backup):
    target=sqlite3.connect(backup)
    try:source.backup(target)
    finally:target.close()
   with self.ops.lock,self.ops.db:
    for row in revisions:
     e=X._row(row);entity='entry:'+e['entry_id'];request=marker+':'+e['entry_id']+':'+str(e['rev'])
     oid=digest({'migration':request});parents=[] if e['rev']==1 else [digest({'migration':marker+':'+e['entry_id']+':'+str(e['rev']-1)})]
     v={k:e[k] for k in ('kind','entry_date','amount','category','driver','vehicle','note','receipt_ref','odometer','fuel_price','fuel_price_source','liters_receipt','reason','at')};v.update(date=e['entry_date'],voided=bool(e['voided']),place='',payment_method='')
     self.ops._put({'v':1,'id':oid,'entity':entity,'parents':parents,'value':v,'actor':e['by_user'] or 'legacy','device':'migration','request':request},True)
    prior={}
    for i,(key,value,date,actor,at) in enumerate(configs):
     entity='setting:'+key+(':'+date if key!='currency' else '');oid=digest({'migration':marker+':setting:'+str(i)});v={'key':key,'value':value,'effective_from':date,'at':at}
     self.ops._put({'v':1,'id':oid,'entity':entity,'parents':prior.get(entity,[]),'value':v,'actor':actor or 'legacy','device':'migration','request':marker+':setting:'+str(i)},True);prior[entity]=[oid]
    self.ops._graph();self.ops.db.execute('INSERT INTO migrated VALUES(?,?)',(marker,fingerprint))
   return {'entries':len(revisions),'settings':len(configs),'backup':backup}
  finally:source.close()
 def state(self):return self.ops.view()
 def _materialize(self):
  state=self.ops.view();mem=X.Store(':memory:');X.init(mem)
  byid={o['id']:o for o in self.ops.operations()}
  # Only resolved operations are used; conflicts are exposed, never guessed.
  for entity,v in state['resolved'].items():
   op=byid[self.ops.heads(entity)[0]]
   if entity.startswith('setting:') and 'key' in v:
    mem.q('INSERT INTO exp_cfg VALUES(?,?,?,?,?)',(v['key'],v['value'],v['effective_from'],op['actor'],v.get('at',0)))
   elif entity.startswith('entry:'):
    fields={k:v.get(k,'') for k in ('kind','entry_date','amount','category','driver','vehicle','note','receipt_ref','odometer','fuel_price','fuel_price_source','liters_receipt')}
    X._write(mem,entity[6:],1,fields,v.get('voided',False),op['actor'],v.get('reason',''))
    mem.q('UPDATE exp_rev SET at=? WHERE entry_id=?',(v.get('at',0),entity[6:]))
  return mem,state
 def ledger(self):
  with self.lock,self.ops.lock:
   mem,state=self._materialize()
   try:r=X.ledger(mem)
   finally:mem.cx.close()
   conflicts=[x for x in state['conflicts']+state['pending_parents'] if not x.startswith('mark:')]
   if conflicts:
    r['balance']=None
    for e in r['entries']:e['balance_after']=None
   r.update(conflicts=conflicts,provisional=bool(conflicts),pending_upload=len(self.ops.pending()),note='Saved on this profile. Server confirmation is separate from device receipt.')
   previous={}
   for e in r['entries']:
    if e.get('vehicle') and str(e.get('odometer','')).strip():
     prior=previous.get(e['vehicle']);e['previous_odometer']=prior
     e['odometer_distance']=str(Decimal(e['odometer'])-Decimal(prior)) if prior is not None and Decimal(e['odometer'])>Decimal(prior) else None
     previous[e['vehicle']]=e['odometer']
    e['revision_ids']=self.ops.heads('entry:'+e['entry_id'])
    source=state['resolved'].get('entry:'+e['entry_id'],{})
    for key in ('place','payment_method'):e[key]=source.get(key,'')
   return r
 def setting(self,key,value,date,user,request,expected=None):
  with self.lock,self.ops.lock:
   mem,state=self._materialize()
   try:
    X.set_cfg(mem,key,value,date,user);normalized=str(value).strip() if key=='currency' else str(X._dec(value,key,positive=key!='opening_balance'))
   finally:mem.cx.close()
   entity='setting:'+key+(':'+date if key!='currency' else '')
   val={'key':key,'value':normalized,'effective_from':date if key!='currency' else '', 'at':time.time()}
   # Setting revisions also carry explicit parents, never selected by wall clock.
   prior=self._request(request)
   if prior:
    if any(prior['value'].get(k)!=val.get(k) for k in ('key','value','effective_from')):raise ValueError('Request reused with changed contents')
    return {'ok':True}
   self._cas(entity,expected)
   self.ops.create(entity,val,user,request,parents=expected)
   return {'ok':True}
 def _cas(self,entity,expected):
  if expected is not None and sorted(expected)!=self.ops.heads(entity):raise ValueError('Changed since opening. Reload before saving; nothing applied.')
  if len(self.ops.heads(entity))>1:raise ValueError('Resolve the conflict before editing.')
 def write(self,entry,user,request,eid=None,reason='',expected=None):
  with self.lock,self.ops.lock:
   eid=eid or digest({'device':self.ops.device,'request':request});entity='entry:'+eid
   if not self._request(request):self._cas(entity,expected)
   if self.ops.heads(entity) and not reason.strip() and not self._request(request):raise ValueError('A reason is required for an edit.')
   mem,state=self._materialize()
   if any(ent.startswith('setting:') for ent in state['conflicts']+state['pending_parents']):
    mem.cx.close();raise ValueError('Resolve settings conflicts before entering money.')
   try:v=X._check(mem,entry);X._opening_guard(mem,v)
   finally:mem.cx.close()
   for key in ('place','payment_method'):v[key]=str(entry.get(key,'')).strip()
   if str(entry.get('odometer','')).strip():
    if not v['vehicle']:raise ValueError('Vehicle is required with an odometer reading.')
    v['odometer']=str(X._dec(entry['odometer'],'Odometer',positive=False))
   v['payment_method']='Cash'
   v.update(date=v['entry_date'],voided=False,at=time.time(),reason=reason or 'created')
   prior=self._request(request)
   if prior:
    check=dict(prior['value']);check['at']=v['at']
    if check!=v or prior['entity']!=entity:raise ValueError('Request reused with changed contents')
    return {'ok':True,'entry_id':eid}
   old=state['resolved'].get(entity)
   if old and old.get('voided'):raise ValueError('Voided entry cannot be edited.')
   self.ops.create(entity,v,user,request,parents=expected)
   return {'ok':True,'entry_id':eid}
 def void(self,eid,user,request,reason,expected=None):
  with self.lock,self.ops.lock:
   entity='entry:'+eid
   prior=self._request(request)
   if prior:
    if prior['entity']!=entity or not prior['value'].get('voided') or prior['value'].get('reason')!=reason.strip():raise ValueError('Request reused with changed contents')
    return {'ok':True}
   self._cas(entity,expected);v=dict(self.ops.view()['resolved'].get(entity) or {})
   if not v:raise ValueError('Entry not found.')
   if v.get('voided'):raise ValueError('Already voided.')
   if not reason.strip():raise ValueError('A reason is required.')
   v.update(voided=True,reason=reason.strip());self.ops.create(entity,v,user,request,parents=expected);return {'ok':True}
 def mark(self,uid,state,user,request,expected):
  with self.lock,self.ops.lock:
   entity='mark:'+uid
   prior=self._request(request)
   if prior:
    if prior['entity']!=entity or prior['value']!={'state':state}:raise ValueError('Request reused with changed contents')
    return {'ok':True}
   self._cas(entity,expected)
   self.ops.create(entity,{'state':state},user,request,parents=expected);return {'ok':True}
 def marks(self):
  s=self.ops.view();out={}
  for ent in {o['entity'] for o in self.ops.operations() if o['entity'].startswith('mark:')}:
   out[ent[5:]]={'state':s['resolved'].get(ent,{}).get('state','conflict'),'heads':self.ops.heads(ent)}
  return out
 def history(self,entity):
  ops=[o for o in self.ops.operations() if o['entity']==entity];ops.sort(key=lambda o:(len(o['parents']),o['value'].get('at',0)))
  return [dict(o['value'],rev=i+1,operation=o['id'],parents=o['parents'],by_user=o['actor']) for i,o in enumerate(ops)]
 def conflicts(self):
  state=self.ops.view();ids=state['conflicts']+state['pending_parents'];return [{'entity':ent,'heads':self.ops.heads(ent),'versions':[o for o in self.ops.operations() if o['id'] in self.ops.heads(ent)],'pending_parent':ent in state['pending_parents']} for ent in ids]
 def reject(self,entity,expected,user,request):
  with self.lock,self.ops.lock:
   if not entity.startswith('entry:'):raise ValueError('Reject is only for expense entries.')
   heads=self.ops.heads(entity)
   if sorted(expected)!=heads:raise ValueError('Conflict changed. Reload.')
   if len(heads)<2:raise ValueError('This entry is not in conflict.')
   ops=[o for o in self.ops.operations() if o['id'] in heads];ops.sort(key=lambda o:o['value'].get('at',0))
   v=dict(ops[-1]['value']);v.update(voided=True,reason='Rejected (conflict)',at=time.time())
   self.ops.create(entity,v,user,request,parents=heads);return {'ok':True}
 def resolve(self,entity,pick,expected,user,request):
  with self.lock,self.ops.lock:
   heads=self.ops.heads(entity)
   if sorted(expected)!=heads:raise ValueError('Conflict changed. Reload.')
   if len(heads)<2 or pick not in heads:raise ValueError('Pick a current conflicting revision.')
   selected=next(o for o in self.ops.operations() if o['id']==pick)
   self.ops.create(entity,selected['value'],user,request,parents=heads);return {'ok':True}

STORES={}
def store(data_dir):
 path=os.path.join(data_dir,'finance_candidate.db')
 if path not in STORES:STORES[path]=Finance(path)
 return STORES[path]

# Local saves return immediately. The callback may only schedule transport work.
def _notify(method):
 def run(self,*a,**k):
  result=method(self,*a,**k)
  if getattr(self,'changed',None):self.changed()
  return result
 return run
for _method in ('write','void','mark','setting','resolve','reject'):
 setattr(Finance,_method,_notify(getattr(Finance,_method)))
