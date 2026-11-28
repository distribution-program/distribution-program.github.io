"""Per-profile, per-device Firestore operation ESTIMATE. Never queries cloud usage."""
import datetime as dt
import threading
import time
import os
from zoneinfo import ZoneInfo

class Usage:
 def __init__(self,core,clock=time.time):
  self.c=core;self.clock=clock;self.lock=threading.RLock();self.active=False;self.error='Cloud not connected'
  with open(os.path.join(os.path.dirname(__file__),'zones','Los_Angeles'),'rb') as f:self.zone=ZoneInfo.from_file(f,key='America/Los_Angeles')
  core.q('CREATE TABLE IF NOT EXISTS device_cloud_usage(day TEXT PRIMARY KEY, reads INTEGER, writes INTEGER, deletes INTEGER, started REAL)')
 def day(self):return dt.datetime.fromtimestamp(self.clock(),self.zone).date().isoformat()
 def add(self,reads=0,writes=0,deletes=0):
  with self.c.LOCK,self.lock:
   day=self.day();self.c.cx.execute('INSERT OR IGNORE INTO device_cloud_usage VALUES(?,0,0,0,?)',(day,self.clock()))
   self.c.cx.execute('UPDATE device_cloud_usage SET reads=reads+?,writes=writes+?,deletes=deletes+? WHERE day=?',(reads,writes,deletes,day));self.c.cx.commit()
 def status(self):
  with self.c.LOCK,self.lock:
   day=self.day();r=self.c.q('SELECT reads,writes,deletes,started FROM device_cloud_usage WHERE day=?',(day,));v=r[0] if r else (0,0,0,self.clock())
   tomorrow=dt.date.fromisoformat(day)+dt.timedelta(days=1);reset=dt.datetime.combine(tomorrow,dt.time(),self.zone).timestamp()
   return dict(day=day,reads=v[0],writes=v[1],deletes=v[2],started=v[3],reset_at=reset,active=self.active,error=self.error,estimate=True,limits=dict(reads=50000,writes=20000,deletes=20000))
 def install(self,client):
  api=client._firestore_api
  if getattr(api,'_dprogram_usage',False):return
  def wrap_stream(name):
   original=getattr(api,name)
   def call(*a,**kw):
    stream=original(*a,**kw);owner=self
    class CountedStream:
     def __init__(self):self.iterator=iter(stream);self.n=0;self.closed=False
     def __getattr__(self,key):return getattr(stream,key)
     def __iter__(self):return self
     def __next__(self):
      try:response=next(self.iterator)
      except StopIteration:
       if name=='run_query' and not self.n and not self.closed:owner.add(reads=1)
       self.closed=True;raise
      if name=='listen':
       if response.document_change.document.name or response.document_delete.document or response.document_remove.document:owner.add(reads=1)
      elif name=='batch_get_documents':owner.add(reads=1);self.n+=1
      elif name=='run_query' and response.document.name:owner.add(reads=1);self.n+=1
      return response
    return CountedStream()
   setattr(api,name,call)
  for name in ['batch_get_documents','run_query','listen']:wrap_stream(name)
  for name in ['commit','batch_write']:
   original=getattr(api,name)
   def call(*a,_original=original,**kw):
    response=_original(*a,**kw);request=kw.get('request') or (a[0] if a else None);writes=getattr(request,'writes',None)
    if writes is None and isinstance(request,dict):writes=request.get('writes',[])
    for w in writes or []:
     deletion=w.get('delete') if isinstance(w,dict) else getattr(w,'delete','')
     self.add(deletes=1) if deletion else self.add(writes=1)
    return response
   setattr(api,name,call)
  original=api.get_document
  def get(*a,**kw):
   response=original(*a,**kw);self.add(reads=1);return response
  api.get_document=get;api._dprogram_usage=True;self.active=True;self.error=''
