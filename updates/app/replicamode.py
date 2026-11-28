"""Exact application feature path with an explicit, fixed alternate cloud namespace."""
import os,json
RUN='utest_20261123_kw20'
def load(path):
 if not path:return None
 with open(path,encoding='utf-8')as f:c=json.load(f)
 if c!={'project_id':'car-distribution','run_id':RUN,'enabled':True}:raise ValueError('Replica configuration mismatch')
 return c
def connected(c):
 return {'replica':True,'version':1,'project_id':c['project_id'],'run_id':c['run_id'],'database_id':'(default)','device_id':os.environ.get('DPROGRAM_REPLICA_DEVICE','PC1'),'phase':'replica','execution_approved':True,'share_path':os.path.join(os.path.expanduser('~'),'InvoiceApp_Replica_'+RUN,'local_share')}
