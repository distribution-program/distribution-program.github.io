"""Asynchronous controlled Quit, never treat queued sync as completion."""
import threading,time
class ExitFlow:
 def __init__(self,s):self.s=s;self.lock=threading.Lock();self.state={'state':'idle'}
 def pending(self):
  s=self.s
  return {'finance':s.finance_status()['pending'] if getattr(s,'FINANCE_ENABLED',False) else 0,'lan':s.q('SELECT count(*) FROM inv WHERE lan=1')[0][0]+s.q('SELECT count(*) FROM dellan WHERE lan=1')[0][0],
   'cloud':sum(s.q(query)[0][0]for query in ('SELECT count(*) FROM inv WHERE dirty=1','SELECT count(*) FROM lst WHERE dirty=1','SELECT count(*) FROM usr WHERE dirty=1','SELECT count(*) FROM del'))}
 def start(self):
  with self.lock:
   if self.state['state']=='running':return dict(self.state)
   if getattr(self.s.core,'CONNECTED_TEST',None):
    self.state={'state':'trial_local_only','msg':'Connected test: check pending counts on all three PCs before ending this test session. No claim of production sync is made.'};return dict(self.state)
   if self.s.core.TEST_MODE:
    self.state={'state':'trial_local_only','msg':'Isolated trial: live network/cloud sync is disabled. Local saves remain on this PC. Quit will stop this trial, not confirm synchronization.'};return dict(self.state)
   self.state={'state':'running','msg':'Sync Now before Quit. Keep this window open.'}
   threading.Thread(target=self.run,daemon=True).start();return dict(self.state)
 def run(self):
  s=self.s
  try:
   lan_before=s.lan_completed;cloud_before=s.cloud_completed
   s.manual_sync();deadline=time.monotonic()+45
   while time.monotonic()<deadline:
    p=self.pending()
    if not p['lan']and not p['cloud'] and not p['finance'] and (not getattr(s,'FINANCE_ROLLOUT',None) or s.finance_status()['ready']) and s.lan_completed>lan_before and (s.db is None or s.cloud_completed>cloud_before):
     with self.lock:self.state={'state':'ready','msg':'Pending changes published. Other-device receipt is not confirmed. Ready to close.'}
     return
    if p['cloud']and s.db is None:raise RuntimeError('Cloud is not configured; pending changes are retained. Program stays open.')
    time.sleep(.3)
   raise RuntimeError('Sync did not finish. Network/auth/quota may be unavailable. Pending changes retained; program stays open.')
  except Exception as e:
   with self.lock:self.state={'state':'failed','msg':str(e)}
 def get(self):
  with self.lock:return dict(self.state)
