"""Read-only Cloud Monitoring totals. No IAM/API/billing enablement or Firestore writes."""
import datetime as dt,json,threading,time,urllib.request,urllib.parse

class ProjectUsage:
 def __init__(self,core,clock=time.time):
  self.c=core;self.clock=clock;self.lock=threading.RLock();self.data={};self.error='Not checked yet';self.thread=None;self.manual=json.loads(core.meta('project_usage_baseline_v37','{}'))
 def interval(self,day):
  start=dt.datetime.combine(day,dt.time(),self.c.CLOUD_USAGE.zone);end=dt.datetime.combine(day+dt.timedelta(days=1),dt.time(),self.c.CLOUD_USAGE.zone)
  return start.timestamp(),min(end.timestamp(),self.clock())
 def fetch_metric(self,kind,start,end,token):
  iso=lambda t:dt.datetime.fromtimestamp(t,dt.timezone.utc).isoformat()
  params={'filter':f'metric.type="firestore.googleapis.com/document/{kind}_ops_count"','interval.startTime':iso(start),'interval.endTime':iso(end),'view':'FULL','pageSize':'1000','aggregation.alignmentPeriod':'60s','aggregation.perSeriesAligner':'ALIGN_SUM','aggregation.crossSeriesReducer':'REDUCE_SUM'}
  total=0;latest=0
  for page in range(20):
   url='https://monitoring.googleapis.com/v3/projects/car-distribution/timeSeries?'+urllib.parse.urlencode(params)
   req=urllib.request.Request(url,headers={'Authorization':'Bearer '+token})
   with urllib.request.urlopen(req,timeout=20)as response:body=json.load(response)
   for series in body.get('timeSeries',[]):
    for p in series.get('points',[]):
     v=p['value'];total+=int(v.get('int64Value',v.get('doubleValue',0)))
     latest=max(latest,dt.datetime.fromisoformat(p['interval']['endTime'].replace('Z','+00:00')).timestamp())
   if not body.get('nextPageToken'):return total,latest
   params['pageToken']=body['nextPageToken']
  raise ValueError('Monitoring result incomplete; not showing partial totals')
 def refresh(self):
  try:
   import firebase_admin
   token=firebase_admin.get_app().credential.get_access_token().access_token
   today=dt.datetime.fromtimestamp(self.clock(),self.c.CLOUD_USAGE.zone).date();result={}
   for label,day in [('today',today),('yesterday',today-dt.timedelta(days=1))]:
    start,end=self.interval(day);values={};latest=0
    for key,kind in [('reads','read'),('writes','write'),('deletes','delete')]:
     value,stamp=self.fetch_metric(kind,start,end,token);values[key]=value;latest=max(latest,stamp)
    result[label]=dict(values,day=day.isoformat(),as_of=latest,empty=not latest)
   with self.lock:self.data=dict(result,checked_at=self.clock());self.error=''
  except Exception as e:
   # HTTP status/type only, never copy credentials or server request headers into UI.
   code=getattr(e,'code',None)
   with self.lock:self.error=('Monitoring permission denied (HTTP '+str(code)+'). Use manual baseline or ask owner for read access.' if code in (401,403) else 'Monitoring read unavailable: '+type(e).__name__+((' HTTP '+str(code))if code else''))
 def start(self):
  if self.thread:return
  def run():
   while True:self.refresh();time.sleep(300)
  self.thread=threading.Thread(target=run,daemon=True,name='project-usage-readonly');self.thread.start()
 def set_manual(self,body):
  stamp=dt.datetime.fromisoformat(str(body.get('as_of','')))
  if stamp.tzinfo is None:raise ValueError('As-of needs timezone offset, for example +02:00')
  if stamp.timestamp()>self.clock()+60:raise ValueError('As-of cannot be in future')
  day=stamp.astimezone(self.c.CLOUD_USAGE.zone).date().isoformat()
  if day!=self.c.CLOUD_USAGE.day():raise ValueError('Starting usage must be from current Pacific quota day; yesterday is separate')
  values={}
  for key in ('reads','writes','deletes'):
   text=str(body.get(key,''))
   if not text.isdigit():raise ValueError('Use nonnegative whole-number counts, not percentages or k abbreviations')
   values[key]=int(text)
  self.manual=dict(values,as_of=stamp.timestamp(),day=day,device_at_entry={k:self.c.CLOUD_USAGE.status()[k]for k in values})
  self.c.setmeta('project_usage_baseline_v37',json.dumps(self.manual));return self.status()
 def status(self):
  with self.lock:
   manual=dict(self.manual);device=self.c.CLOUD_USAGE.status()
   if manual and manual['day']==device['day']:
    manual['estimate']={k:manual[k]+max(0,device[k]-manual['device_at_entry'][k])for k in ('reads','writes','deletes')}
   else:manual={}
   valid=self.data.get('today',{}).get('day')==device['day']
   return dict(data=self.data if valid else {},error=self.error,manual=manual,limits=device['limits'],source='Cloud Monitoring; whole project, main + replica + other clients; delayed estimate, not exact billing')
