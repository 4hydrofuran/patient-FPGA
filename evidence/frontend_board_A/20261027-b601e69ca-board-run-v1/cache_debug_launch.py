import hashlib,json,os,subprocess
from pathlib import Path
assert hashlib.sha256(Path('/etc/machine-id').read_bytes()).hexdigest()=='ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec'
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()=='98886b24-96d3-409e-a783-ce9c54873da9'
source=Path('/home/ubuntu/kv260-staging/a12-case20-debug-20261027-v1/case20-debug-t4')
r=subprocess.run(['/usr/bin/python3','-B',str(source/'start_board.py'),'--execute-board','--window-id','a12-case20-debug-20261027-v1'],capture_output=True,text=True,timeout=50)
out=dict(status='CACHE_DEBUG_START_REQUESTED' if r.returncode==0 else 'FAILED_PRESERVE_PARTIAL_STATE',exit_code=r.returncode,stdout=r.stdout,stderr=r.stderr)
print('__TT10_UART_ROOT_SCENE_BEGIN__',flush=True);print(json.dumps(out),flush=True);print('__TT10_UART_ROOT_SCENE_END__',flush=True)
