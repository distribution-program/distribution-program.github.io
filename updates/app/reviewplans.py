"""Driver-plan review. Caller owns authenticated actor and existing invoice operations."""
import hashlib,json,time,re

def install(s):
 def plans():
  groups={}
  for uid,d in s.docs.items():
   if d.get('Invoice Status') not in ('Proposal','inprocess'):continue
   parts=[str(d.get(k,'')).strip()for k in ('Driver name','Distributed Date','Car No','Line')]
   key=hashlib.sha256(json.dumps(parts).encode()).hexdigest()[:24]
   g=groups.setdefault(key,{'key':key,'driver':parts[0]or'Unassigned','date':parts[1],'car':parts[2],'line':parts[3],'uids':[],'stages':set(),'inprocess_count':0,'proposal_count':0});g['uids'].append(uid);g['stages'].add(d['Invoice Status']);g[d['Invoice Status']+'_count' if d['Invoice Status']=='inprocess'else'proposal_count']+=1
  # Saved plans remain reopenable even after all invoices change status.
  for uid,raw in s.q("SELECT uid,data FROM inv WHERE uid LIKE 'review_%'"):
   d=json.loads(raw)
   if d.get('_kind')=='review_plan':
    key=d['key'];g=groups.setdefault(key,dict(d,uids=[],stages=set(),inprocess_count=0,proposal_count=0))
    g['uids']=list(dict.fromkeys(g['uids']+d.get('uids',[])))
  return [dict(g,stages=sorted(g['stages']),count=len(g['uids']))for g in groups.values()]
 def open_plan(key):
  plan=next((g for g in plans()if g['key']==key),None)
  if not plan:return {'ok':False,'msg':'Plan not found'}
  prior=s.q('SELECT data FROM inv WHERE uid=?',('review_'+key,));saved=json.loads(prior[0][0])if prior else {};marks=saved.get('marks',{})
  rows=[]
  for uid in plan['uids']:
   if uid not in s.docs:continue
   d=s.docs[uid];rows.append({'uid':uid,'invoice':d.get('Invoice Number',''),'customer':d.get('Customer Name',''),'status':d.get('Invoice Status',''),'updated':d.get('updated',0),'out':marks.get(uid,{}).get('out',False),'received':marks.get(uid,{}).get('received',False),'exception_out':marks.get(uid,{}).get('exception_out',False),'exception_received':marks.get(uid,{}).get('exception_received',False)})
  return {'ok':True,'plan':plan,'rows':rows,'revision':saved.get('updated',0)}
 def save(b,user):
  with s.core.LOCK,s.STATE_LOCK:
   current=open_plan(b.get('key'));changes=b.get('changes',{})
   if not current['ok']:return current
   if current['revision']!=b.get('revision',0):return {'ok':False,'msg':'Plan changed on another device. Reload before saving.'}
   rows={r['uid']:r for r in current['rows']};bad=[]
   for uid,c in changes.items():
    if uid not in rows or rows[uid]['updated']!=c.get('updated'):bad.append(uid);continue
    status=c.get('status',rows[uid]['status'])
    if c.get('received') and rows[uid]['status'] in ('inprocess','Proposal') and not c.get('exception_received') and not c.get('exception_out'):status='Delivered'
    c['status']=status
    if status not in s.STATUSES:return {'ok':False,'msg':'Choose an existing status.'}
    if status=='Cancelled'and rows[uid]['status']!='Cancelled'and not c.get('reason','').strip():return {'ok':False,'msg':'Cancelled requires a reason.'}
   if bad:return {'ok':False,'msg':'Invoice changed since opening. Reload the plan; nothing was applied.'}
   old=s.q('SELECT data FROM inv WHERE uid=?',('review_'+b['key'],));old=json.loads(old[0][0])if old else {};marks=old.get('marks',{})
   now=time.time()
   updates=[]
   for uid,c in changes.items():
    marks[uid]={'out':bool(c.get('out')),'received':bool(c.get('received')),'exception_out':bool(c.get('exception_out')),'exception_received':bool(c.get('exception_received')),'by':user,'at':now}
    if c.get('status',rows[uid]['status'])!=rows[uid]['status']:
     record=dict(s.docs[uid]);record['Invoice Status']=c['status'];record['updated']=now
     if c['status']=='Cancelled'and rows[uid]['status']!='Cancelled':s.with_reason(record,c['reason'])
     updates.append((uid,record))
   rec=dict(current['plan']);rec.pop('stages',None);rec.update(_kind='review_plan',marks=marks,updated=now)
   updates.append(('review_'+b['key'],rec))
   s.db_put(updates,1,1);s.reload_data();s.bump();s.sync_now.set();s.request_cloud()
   return {'ok':True,'msg':'Saved locally. Sync requested; remote arrival not confirmed.'}
 return plans,open_plan,save
