"""Source-only finance transport adapter. Never creates a client or connects itself.
Caller must supply an approved remote and install returned callback. No live app wiring.
"""
from finance_protocol import digest

class Transport:
 def __init__(self,ledger,remote,receive_limit=1000):
  self.ledger=ledger;self.remote=remote;self.receive_limit=receive_limit;self.ready=False;self.error=None;self.stop=None
 def push(self):
  confirmed=0
  for op in self.ledger.pending():
   try:
    # create-once: remote must never overwrite an operation with the same ID.
    remote=self.remote.create_once(op)
    if digest(remote)!=digest(op):
     self.ledger.receive([remote]);raise ValueError('Remote operation identity mismatch; review quarantine.')
    self.ledger.ack(op['id'],digest(remote));confirmed+=1
   except Exception as e:self.error=str(e);return {'confirmed':confirmed,'pending':len(self.ledger.pending()),'error':self.error}
  self.error=None;return {'confirmed':confirmed,'pending':len(self.ledger.pending()),'error':None}
 def receive(self,ops):
  try:self.ledger.receive(ops)
  except Exception as e:self.error=str(e);self.ready=False;raise
 def start(self):
  # Subscribe before paged bootstrap so concurrent new IDs cannot fall behind a cursor.
  self.stop=self.remote.listen(self.receive)
  try:
   page,cursor,total=self.remote.first_page(min(200,self.receive_limit+1))
   if total>self.receive_limit:raise ValueError('Initial finance history exceeds the approved read budget. No full scan started.')
   seen=0
   while True:
    seen+=len(page)
    if seen>self.receive_limit:raise ValueError('Initial finance read cap reached. Reconciliation incomplete.')
    self.receive(page)
    if cursor is None:break
    page,cursor=self.remote.next_page(cursor,min(200,self.receive_limit-seen+1))
   self.ready=True;self.error=None;return {'ready':True,'received':seen}
  except Exception as e:
   self.ready=False;self.error=str(e)
   if self.stop:self.stop();self.stop=None
   raise
 def reconcile(self):
  # F5 asks for missing IDs using approved transport inventory, never invoice collection.
  # Backend must cap discovery and not claim completion on partial response.
  ops,complete=self.remote.missing({o['id'] for o in self.ledger.operations()},self.receive_limit)
  self.receive(ops)
  self.ready=bool(complete);self.error=None if complete else 'Finance reconciliation incomplete; read cap reached.'
  return {'ready':self.ready,'received':len(ops),'error':self.error}
 def close(self):
  if self.stop:self.stop();self.stop=None
  self.ready=False

class FirestoreRemote:
 """Not active. Injected collection must be a separately approved finance collection.
  Sketch only: inventory discovery/listener quota semantics must be finalized before activation.
  No invoice/LAN mutation, no client construction, no credentials.
 """
 def __init__(self,collection):self.collection=collection
 def create_once(self,operation):
  ref=self.collection.document(operation['id'])
  try:ref.create(operation)
  except Exception:
   # Lost ack/already-exists: read identity, never replace. Auth/network errors propagate.
   snapshot=ref.get()
   if not snapshot.exists:raise
   return snapshot.to_dict()
  return operation
 # Deliberately no live listen/bootstrap/reconcile implementation until read-budget,
 # access and compatibility plan is approved. Missing methods block startup, not fake sync.
