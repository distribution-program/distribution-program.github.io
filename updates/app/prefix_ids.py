"""Immutable user-prefix registry and atomic sequence/ID claims.
The existing supplied Admin client owns cloud access. No client, login or network on import.
"""
import hashlib,json,re,threading,uuid
class NotReady(ValueError):pass

def parse(value):
 s=str(value).strip().upper()
 m=re.fullmatch(r'([A-Z]{1,2})([1-9][0-9]*)',s)
 if m:return m[1],int(m[2])
 if re.fullmatch(r'[1-9][0-9]*',s):return '',int(s)
 raise ValueError('ID must be a positive legacy number or assigned prefix plus positive number')

def choose_prefix(username,assigned):
 parts=str(username).strip().upper().split()
 if not parts:raise ValueError('Username required')
 candidates=[parts[0][0]]+([parts[0][:2]]if len(parts[0])>1 else [])+([parts[1][0]]if len(parts)>1 else [])
 for p in candidates:
  if re.fullmatch('[A-Z]{1,2}',p)and p not in assigned:return p
 raise ValueError('No unused prefix. Ask ADMIN to choose another username before creating this user.')

def key(value):
 try:p,n=parse(value);return p,n
 except ValueError:return '~',0

class Service:
 def __init__(self,core,ready,documents):self.c=core;self.isready=ready;self.documents=documents;self.lock=threading.RLock()
 def check(self):
  if not self.c.LOCAL_ONLY and not self.isready():raise NotReady('Initial cloud synchronization is not ready. No new ID or invoice saved. Connect and wait, then retry.')
 def prefix(self,user):
  user=str(user).strip().upper();c=self.c;self.check()
  def apply(reg):
   mapping=dict((reg or{}).get('users',{}))
   if user not in mapping:
    # Existing named defaults are provisioned together, giving the approved K/E/G/A assignments.
    for name in ['ADMIN','EHAB SOBHY','GAMAL YOUSEEF','KIROLLOS WILLIAM',user]:
     if name not in mapping:mapping[name]=choose_prefix(name,set(mapping.values()))
   return mapping,mapping[user]
  with self.lock:
   if c.LOCAL_ONLY:
    mapping,p=apply(json.loads(c.meta('invoice_id_prefix_registry','{}')));c.setmeta('invoice_id_prefix_registry',json.dumps({'users':mapping}));return p
   ref=c.db.collection('meta').document('invoice_id_prefix_registry')
   @c.firestore.transactional
   def run(tx):
    mapping,p=apply(ref.get(transaction=tx).to_dict());tx.set(ref,{'users':mapping});return p
   return run(c.db.transaction())
 def floor(self,prefix):
  values=[]
  for row in list(self.documents().values()):
   try:p,n=parse(row.get('ID',''))
   except ValueError:continue
   if p==prefix:values.append(n)
  return max(values or[0])
 def reserve_batch(self,user,uids):
  if not uids:return []
  if len(set(uids))!=len(uids):raise ValueError('Duplicate invoice identity')
  self.check();p=self.prefix(user);floor=self.floor(p);c=self.c
  with self.lock:
   if c.LOCAL_ONLY:
    with c.LOCK:
     n=max(int(c.meta('prefix_counter_'+p,0)),floor);out=[]
     for uid in uids:
      receipt='prefix_receipt_'+hashlib.sha256(uid.encode()).hexdigest();old=c.meta(receipt,'')
      if old:out.append(old);continue
      n+=1;identity=p+str(n);c.setmeta(receipt,identity);c.setmeta('id_claim_'+identity,uid);out.append(identity)
     c.setmeta('prefix_counter_'+p,n);return out
   counter=c.db.collection('meta').document('prefix_counter_'+p)
   receipts=[c.db.collection('meta').document('prefix_receipt_'+hashlib.sha256(uid.encode()).hexdigest())for uid in uids]
   @c.firestore.transactional
   def run(tx):
    old=[r.get(transaction=tx).to_dict()for r in receipts]
    n=max(int((counter.get(transaction=tx).to_dict()or{}).get('n',0)),floor);out=[];changes=[]
    for uid,ref,record in zip(uids,receipts,old):
     if record:out.append(record['id']);continue
     n+=1;identity=p+str(n);out.append(identity);changes.append((uid,ref,identity))
    # Counter + receipts + claims in one transaction; every claimant also touches this counter.
    tx.set(counter,{'n':n})
    for uid,ref,identity in changes:
     tx.set(ref,{'id':identity,'uid':uid,'prefix':p});tx.set(c.db.collection('meta').document('id_claim_'+identity),{'uid':uid,'id':identity})
    return out
   return run(c.db.transaction())
 def allocate(self,user,uids):
  # Durable disjoint device leases preserve offline/LAN creation after a safe online reservation.
  if self.c.LOCAL_ONLY:return self.reserve_batch(user,uids)
  self.check() # every process must finish its initial sync, even if it has an old cached lease
  c=self.c;user=str(user).strip().upper()
  with self.lock,c.LOCK:
   receiptkey=lambda uid:'prefix_local_invoice_'+hashlib.sha256(uid.encode()).hexdigest()
   leasekey='prefix_device_lease_'+hashlib.sha256(user.encode()).hexdigest()
   leases=json.loads(c.meta(leasekey,'[]'));out=[];needed=[u for u in uids if not c.meta(receiptkey(u),'')]
   if len(leases)<len(needed):
    # Never fabricate numbers. An empty/exhausted lease requires initial cloud sync and successful reservation.
    self.check()
    count=max(100,len(needed)-len(leases));batch=uuid.uuid4().hex
    leases.extend(self.reserve_batch(user,['lease_'+batch+'_'+str(i)for i in range(count)]))
    c.setmeta(leasekey,json.dumps(leases))
   for uid in uids:
    prior=c.meta(receiptkey(uid),'')
    if prior:out.append(prior);continue
    identity=leases.pop(0)
    # Persist consumption before saving the invoice. A crash can leave a gap, never a reused ID.
    c.setmeta(leasekey,json.dumps(leases));c.setmeta(receiptkey(uid),identity);out.append(identity)
   return out
 def claim(self,identity,uid,user=None):
  """Manual/import ID editing remains available. A durable claim prevents reuse across devices."""
  self.check();identity=str(identity).strip().upper();p,n=parse(identity);c=self.c
  if p and user is not None and p!=self.prefix(user):raise ValueError('Use your assigned ID prefix, or retain an existing legacy numeric ID')
  for other,row in list(self.documents().items()):
   if other!=uid and str(row.get('ID','')).upper()==identity:raise ValueError('This ID already exists. Nothing was changed.')
  with self.lock:
   if c.LOCAL_ONLY:
    with c.LOCK:
     old=c.meta('id_claim_'+identity,'')
     if old and old!=uid:raise ValueError('This ID was already reserved, including deleted invoices')
     c.setmeta('id_claim_'+identity,uid)
     if p:c.setmeta('prefix_counter_'+p,max(n,int(c.meta('prefix_counter_'+p,0))))
     return identity
   ref=c.db.collection('meta').document('id_claim_'+identity);counter=c.db.collection('meta').document('prefix_counter_'+p)if p else None
   @c.firestore.transactional
   def run(tx):
    old=ref.get(transaction=tx).to_dict();count=counter.get(transaction=tx).to_dict()if counter else None
    if old and old.get('uid')!=uid:raise ValueError('This ID was already reserved, including deleted invoices')
    tx.set(ref,{'uid':uid,'id':identity})
    if counter:tx.set(counter,{'n':max(n,int((count or{}).get('n',0)))})
    return identity
   return run(c.db.transaction())
