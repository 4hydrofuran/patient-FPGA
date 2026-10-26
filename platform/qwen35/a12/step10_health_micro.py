"""Read-only bounded health-component timing, only after the candidate fully closes.

No model, XRT, writes, signals, lock/lease changes or recovery operations.
"""
import hashlib,json,os,subprocess,time
from pathlib import Path
root=Path('/var/lib/kv260-a12/step10-optimized-20261024-v1')
machine='ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec'
boot='86e4938b-0f65-4166-9237-c547b67e1451'
assert os.geteuid()==0 and hashlib.sha256(Path('/etc/machine-id').read_bytes()).hexdigest()==machine
assert json.loads((root/'manager-exit.json').read_text())['exit_code']==0
assert not (root/'run-v1/s2/ISOLATED.json').exists()
for side in ('s1','s2'):assert json.loads((root/'run-v1'/side/'exit.json').read_text())['exit_code']==0
assert not Path('/var/lock/kv260-a1/active').exists() and not Path('/sys/module/zocl').exists()
assert Path('/sys/class/fpga_manager/fpga0/state').read_text().strip()=='operating'
paths=list(Path('/sys/class/hwmon').glob('hwmon*/temp*_input'));assert paths
rows=[]
for index in range(10):
    assert not Path('/var/lock/kv260-a1/active').exists() and not Path('/sys/module/zocl').exists()
    begin=time.monotonic_ns();assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==boot
    after_boot=time.monotonic_ns()
    proc=subprocess.run(['dmesg','--raw'],capture_output=True,timeout=3);assert proc.returncode==0 and not proc.stderr
    after_kernel=time.monotonic_ns();temps=[]
    for path in paths:
        start=time.monotonic_ns();value=int(path.read_text());ended=time.monotonic_ns()
        assert 0<value<55000
        temps.append(dict(path=str(path),value_mC=value,read_ms=(ended-start)/1e6))
    after_temps=time.monotonic_ns()
    mem={s.split(':')[0]:int(s.split()[1]) for s in Path('/proc/meminfo').read_text().splitlines()}
    ended=time.monotonic_ns()
    rows.append(dict(index=index,boot_read_ms=(after_boot-begin)/1e6,kernel_read_ms=(after_kernel-after_boot)/1e6,
        temperatures=temps,temperatures_total_ms=(after_temps-after_kernel)/1e6,
        meminfo_read_ms=(ended-after_temps)/1e6,total_observed_read_ms=(ended-begin)/1e6,
        memory_kib={k:mem[k] for k in ('MemAvailable','CmaFree')},kernel_sha256=hashlib.sha256(proc.stdout).hexdigest()))
result=dict(status='PASS_READ_ONLY_POST_CLOSEOUT_HEALTH_COMPONENT_TIMING',domain='BOARD_CONTROL_READ_ONLY_NOT_MODEL_BENCHMARK',
    rows=rows,accelerator_submissions=0,device_opens=0,mutations=0,signals=0,
    scope='10 bounded idle observations; subprocess/temperature/memory reads only; full permission latency remains the actual in-window measurement')
print(json.dumps(result),flush=True)
