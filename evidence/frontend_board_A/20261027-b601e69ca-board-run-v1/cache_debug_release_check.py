import json,time
from pathlib import Path
root=Path('/var/lib/kv260-a12/case20-random-20261027-v1')
p=root/'continuous/bundle/run-v1/result.json'
r=dict(status='OLD_OWNER_DRAIN_PENDING',result_exists=p.exists(),active_lease=Path('/var/lock/kv260-a1/active').exists(),zocl_loaded=Path('/sys/module/zocl').exists())
if p.exists():
 r['result']=json.loads(p.read_text())
 if r['result'].get('worker_exit_code')==0 and r['result'].get('lease_archived') is True and not r['active_lease'] and not r['zocl_loaded']:r['status']='OLD_OWNER_NORMAL_RELEASE_VERIFIED'
 r['consultation_archives']=len(list((root/'continuous/bundle/run-v1/s2/consultations').glob('*.json')))
print('__TT10_UART_ROOT_SCENE_BEGIN__',flush=True);print(json.dumps(r),flush=True);print('__TT10_UART_ROOT_SCENE_END__',flush=True)
