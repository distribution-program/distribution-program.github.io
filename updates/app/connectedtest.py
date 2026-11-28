"""Connected-test isolation guards. Importing this module has no effects.
A prepared source mode is NOT approval to run it with a real account.
"""
import os,re,json,ntpath
ALLOWED=frozenset({'invoices','lists','users','meta','finance_v1_ops','finance_v1_meta','driver_accounts','driver_state'})
class ScopedClient:
 def __init__(self,client,run):self.client=client;self.prefix=validate_run(run)+'_'
 def collection(self,name):
  if name not in ALLOWED:raise ValueError('Connected test blocked an unexpected collection')
  return self.client.collection(self.prefix+name)
 def transaction(self,*a,**k):return self.client.transaction(*a,**k)
 def close(self):return self.client.close()
def validate_run(run):
 if not isinstance(run,str)or not re.fullmatch(r'utest_[0-9]{8}_[a-z0-9]{4,12}',run):raise ValueError('Invalid test run ID')
 return run
def load(path):
 if not path:return None
 with open(path,encoding='utf-8')as f:c=json.load(f)
 fields={'version','run_id','project_id','database_id','share_path','device_id','phase','execution_approved'}
 if set(c)!=fields or c['version']!=1 or c['execution_approved']is not True:raise ValueError('Connected-test configuration incomplete or not approved')
 run=validate_run(c['run_id'])
 if c['database_id']!='(default)':raise ValueError('Only the inspected default database is supported in this candidate')
 if not isinstance(c['project_id'],str)or not re.fullmatch(r'[a-z][a-z0-9-]{4,61}[a-z0-9]',c['project_id']):raise ValueError('Invalid project ID')
 if c['device_id']not in ('PC1','PC2','PC3')or c['phase']not in ('firebase','lan','combined'):raise ValueError('Choose explicit device and transport phase')
 share=c['share_path'];normalized=ntpath.normpath(share)
 if not isinstance(share,str)or ntpath.basename(normalized)!=run or ntpath.dirname(normalized).casefold()!='z:\\':raise ValueError('Test share must be the new run-ID child directly under Z:\\')
 c['share_path']=normalized
 return c
def validate_share(c):
 # Marker must be explicitly prepared in the NEW empty folder during approved preflight.
 p=c['share_path'];marker=os.path.join(p,'DPROGRAM_TEST_SCOPE.json')
 if not os.path.isdir(p):raise ValueError('Connected test share missing. No production-folder fallback.')
 with open(marker,encoding='utf-8')as f:m=json.load(f)
 if m!={'v':1,'run_id':c['run_id'],'purpose':'DPROGRAM connected test only'}:raise ValueError('Test share marker mismatch')
 return p
def profile(home,c):return os.path.join(home,'InvoiceApp_Sync_Test_'+c['run_id'])
