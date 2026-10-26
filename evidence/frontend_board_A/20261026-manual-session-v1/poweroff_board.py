import json,os,subprocess
from pathlib import Path
assert os.geteuid()==0 and os.uname().machine=='aarch64'
assert not Path('/var/lock/kv260-a1/active').exists()
assert not Path('/sys/module/zocl').exists()
os.sync()
print('__PL_BEGIN__',flush=True)
print(json.dumps(dict(status='USER_REQUESTED_NORMAL_POWEROFF',active_lease=False,zocl=False)),flush=True)
subprocess.run(['systemctl','poweroff'],check=True)
