"""Local combined-restore recovery. No network. Must run before worker threads.
A prepared journal is never treated as complete. Recovery reinstates BOTH preimages.
"""
import os,json,sqlite3,uuid,shutil

def atomic_json(path,data):
 temp=path+'.tmp'
 with open(temp,'w')as f:json.dump(data,f);f.flush();os.fsync(f.fileno())
 os.replace(temp,path)

def snapshot(connection,path):
 target=sqlite3.connect(path)
 try:connection.backup(target);target.commit()
 finally:target.close()
 with open(path,'rb')as f:os.fsync(f.fileno())

def reinstate(path,connection):
 src=sqlite3.connect(path)
 try:src.backup(connection);connection.commit()
 finally:src.close()

class CombinedRestore:
 def __init__(self,directory,invoice,finance):
  self.directory=os.path.join(directory,'restore_recovery');self.journal=os.path.join(self.directory,'journal.json');self.invoice=invoice;self.finance=finance
 def recover(self):
  if not os.path.exists(self.journal):return False
  with open(self.journal)as f:j=json.load(f)
  if j.get('version')!=1:raise ValueError('Unsupported restore recovery journal. Start blocked to protect data.')
  if j.get('state')=='prepared':
   for name in ('invoice_before.db','finance_before.db'):
    if not os.path.isfile(os.path.join(self.directory,name)):raise ValueError('Missing restore recovery snapshot. Start blocked to protect data.')
   reinstate(os.path.join(self.directory,'invoice_before.db'),self.invoice)
   reinstate(os.path.join(self.directory,'finance_before.db'),self.finance)
  elif j.get('state')!='committed':raise ValueError('Unknown restore recovery state.')
  self._cleanup();return True
 def _cleanup(self):
  # Retain harmless snapshots until the commit/recovery marker has been retired.
  if os.path.exists(self.journal):os.remove(self.journal)
  for n in ('invoice_before.db','finance_before.db'):
   p=os.path.join(self.directory,n)
   if os.path.exists(p):os.remove(p)
 def run(self,apply,fault=None):
  self.recover();os.makedirs(self.directory,exist_ok=True)
  snapshot(self.invoice,os.path.join(self.directory,'invoice_before.db'))
  snapshot(self.finance,os.path.join(self.directory,'finance_before.db'))
  atomic_json(self.journal,{'version':1,'state':'prepared'})
  try:
   result=apply()
   if fault:fault()
   atomic_json(self.journal,{'version':1,'state':'committed'})
  except BaseException:
   self.recover();raise
  self._cleanup();return result
