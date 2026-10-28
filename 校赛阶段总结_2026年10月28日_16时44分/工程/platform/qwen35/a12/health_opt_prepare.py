"""Reserve an independent health optimization batch; never change sealed inputs."""
import json
from pathlib import Path
import shutil
from common import ROOT, sha, save

OUT = ROOT/'evidence/model_pl_A/20261024-health-opt-v1'
if __name__ == '__main__':
    assert not (OUT/'START.json').exists(),'batch already reserved; do not overwrite before snapshots'
    for name in ('PROJECT_STATUS.json', 'DESIGN_GAP.md', 'DECISIONS.md', 'TEST_MATRIX.md',
                 'AI_ASSISTANCE.md', 'status/A.md', 'A12_STEP_PLAN_20261023.md'):
        src=ROOT/'docs'/name; dst=OUT/'before/docs'/name
        dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
    seal=ROOT/'evidence/model_pl_A/20261024-step10-v1/SEAL.json'
    old=json.loads(seal.read_text(encoding='utf-8'))
    save(OUT/'START.json',dict(task='A12_HEALTH_OPT',scope='HEALTH_ONLY_NO_KERNEL_OR_ABI_CHANGE',
        prior_seal_sha256=sha(seal),historical_manifest=old['files'],
        authority='USER_HEALTH_OPTIMIZATION_WITH_PRIOR_BOARD_AUTHORIZATION',
        reboot_power_flash=False,actual_model_settings='unknown',subagents=0))
    module=(ROOT/'platform/qwen35/a12/health_opt.py').read_text(encoding='utf-8')
    probe='''import json,os,subprocess,time,hashlib
from pathlib import Path
assert os.geteuid()==0 and os.uname().release=='6.8.12-a10irq2'
assert hashlib.sha256(Path('/etc/machine-id').read_bytes()).hexdigest()=='ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec'
assert not Path('/sys/module/zocl').exists() and not Path('/var/lock/kv260-a1/active').exists()
MODULE
reader=PersistentKmsg();rows=[]
try:
    a=reader.drain()
    full=subprocess.check_output(['dmesg','--raw']).decode('utf-8')
    reader.assert_full_snapshot(full)
    sensors=StableTemperatures()
    for i in range(30):
        begin=time.monotonic_ns();reader.drain();kernel_end=time.monotonic_ns()
        values=sensors.read();temp_end=time.monotonic_ns()
        mem=Path('/proc/meminfo').read_text();end=time.monotonic_ns()
        rows.append(dict(kernel_ms=(kernel_end-begin)/1e6,temperature_ms=(temp_end-kernel_end)/1e6,memory_ms=(end-temp_end)/1e6,new_records=reader.last_new_records))
    final=subprocess.check_output(['dmesg','--raw']).decode('utf-8');reader.assert_full_snapshot(final)
    print(json.dumps(dict(status='PASS_READONLY_KMSG_EXACT_RAW_AND_TIMING',records=reader.records,drains=reader.drains,sha256=hashlib.sha256(final.encode()).hexdigest(),rows=rows,model_runs=0,PL_loads=0,mutations=0)),flush=True)
finally:reader.close()
'''.replace('MODULE',module)
    (OUT/'probe_reviewed.py').write_text(probe,encoding='utf-8',newline='\n')
    save(OUT/'PLAN.json',dict(items=['PC fail-closed reader/schedule/path tests',
        'READONLY exact dmesg/kmsg equality and timings',
        'New isolated Python-only candidate, existing ARM/xclbin bytes unchanged',
        'CPU then PL short_profile/natural_plain/natural_profile bounded comparison',
        'Normal release, independent/delayed scans, numerical and history audit'],
        max_runs=5000,max_loads=72,request_limit=3,prompt_limit=107,output_limit=24,
        health_limits_unchanged=True,per_permission_fsync_unchanged=True,
        max_session_seconds=1800,major_unresolved_problem_stop_seconds=600))
    print('HEALTH_OPT_RESERVED')
