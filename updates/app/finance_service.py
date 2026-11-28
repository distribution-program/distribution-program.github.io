"""Finance lifecycle controller. No credentials, account creation or activation writes.
Only app startup with an explicit approved rollout file may construct a live remote.
"""
import os,json,time,threading
from finance_sequence import SequencedSync,FirestoreSequenceRemote

PLAN='dprogram-finance-sequence-v1'
def rollout(data_dir,test_mode=False):
 path=os.path.join(data_dir,'finance_rollout_v1.json')
 if test_mode or not os.path.isfile(path):return None
 with open(path,encoding='utf-8')as f:c=json.load(f)
 required={'plan','enabled','all_three_upgraded','legacy_source_reconciled','bootstrap_read_cap'}
 if set(c)!=required or c['plan']!=PLAN or c['enabled'] is not True or c['all_three_upgraded'] is not True or c['legacy_source_reconciled'] is not True:raise ValueError('Finance rollout not approved or incomplete. No migration performed.')
 cap=c['bootstrap_read_cap']
 if type(cap)is not int or cap<2 or cap>2000:raise ValueError('Invalid approved finance read cap')
 return c

class Service:
 def __init__(self,finance,remote,cap=2000,changed=lambda:None):
  self.finance=finance;self.sync=SequencedSync(finance.ops,remote,bootstrap_cap=cap);self.sync.changed=changed
  self.event=threading.Event();self.shutdown=threading.Event();self.worker=None;self.state_lock=threading.RLock();self.failures=0;self.error=None;self.last_success=None;self.retry_at=0;self.next_audit=0;self.blocked=False
 def status(self):
  return {'enabled':True,'ready':self.sync.ready,'pending':len(self.finance.ops.pending()),'checkpoint':self.sync.checkpoint(),'error':self.error or self.sync.error,'last_success':self.last_success,'server_confirmed_only':True,'blocked':self.blocked}
 def request(self):self.event.set()
 def start(self):
  if not self.worker:
   self.worker=threading.Thread(target=self._run,daemon=True,name='finance-sync');self.worker.start()
 def cycle(self):
  with self.state_lock:
   try:
    if self.blocked:return self.status()
    if not self.sync.stop or self.sync.rotate:self.sync.start()
    result=self.sync.push()
    if result.get('fatal'):raise ValueError(result['error'])
    if result['error']:raise RuntimeError(result['error'])
    self.sync.maintain();self.last_success=time.time();self.error=None;self.failures=0;self.retry_at=0;self.next_audit=time.monotonic()+300
    return self.status()
   except ValueError as e:
    self.error=str(e);self.sync.ready=False;self.blocked=True;self.sync.close();return self.status()
   except Exception as e:
    self.error=str(e);self.sync.ready=False;self.failures+=1;self.retry_at=time.monotonic()+min(300,10*2**min(self.failures-1,5));return self.status()
 def _run(self):
  while not self.shutdown.is_set():
   requested=self.event.wait(1);self.event.clear()
   now=time.monotonic()
   if self.blocked or now<self.retry_at:continue
   if requested or self.failures>0 or self.sync.rotate or not self.sync.stop or now>=self.next_audit:self.cycle()
 def close(self):
  self.shutdown.set();self.event.set()
  if self.worker:self.worker.join(timeout=15)
  self.sync.close()
