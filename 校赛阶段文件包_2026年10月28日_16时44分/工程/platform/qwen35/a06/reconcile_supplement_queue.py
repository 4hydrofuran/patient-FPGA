"""Archive only the confirmed finished failed A job marker; never kill jobs."""
import json,os,sys
from pathlib import Path
sys.path.insert(0,'/mnt/c/Patientqwen/platform/ra02')
from build_queue import CENTRAL,exclusive
JOB='01791034581173549294-A-a06-supplement-v1-ca1061c0'
with exclusive(CENTRAL):
 active=CENTRAL/'active.json';request=json.loads(active.read_text());assert request['job']==JOB
 receipt=json.loads((CENTRAL/'results'/(JOB+'.json')).read_text());assert receipt['status']=='FAILED' and receipt['exit_code']==1
 for proc in Path('/proc').iterdir():
  if not proc.name.isdigit() or int(proc.name)==os.getpid():continue
  try:cmd=(proc/'cmdline').read_bytes()
  except (OSError,PermissionError):continue
  if JOB.encode() in cmd:raise RuntimeError('job-related process still alive: '+proc.name)
 target=CENTRAL/'active.failed-a06-supplement-v1.json';assert not target.exists()
 active.rename(target)
 print(json.dumps({'job':JOB,'result':'FAILED_MARKER_ARCHIVED_NOT_DELETED','process_check':'NO_JOB_PROCESS','path':str(target)}))
