"""Bind the prepared, unchanged driver to explicit user approval and fresh baseline."""
import base64,gzip,hashlib,json
from pathlib import Path
from tt10_01_common import OUT,sha,save
def j(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def main():
    window=OUT/'window-20261025-v2';execution=window/'execution-01';prepared=j(window/'PREPARED.json')
    driver=window/'board_driver_plan.py';assert sha(driver)==prepared['driver_sha256']
    assert sha(window/'bundle-v3/manifest.json')==prepared['bundle_manifest_sha256']
    for row in j(window/'bundle-v3/manifest.json')['files']:
        p=window/'bundle-v3'/row['path'];assert p.stat().st_size==row['bytes'] and sha(p)==row['sha256']
    assert j(execution/'preflight-03/receipt.json')['exit_code']==0
    fresh=j(execution/'preflight-03/stdout.txt');assert fresh['probe_status'].startswith('PASS_')
    assert len(fresh['lock_probe'])==3 and all(x['exclusive_acquired'] for x in fresh['lock_probe']) and fresh['lock_probe_released']
    raw=fresh['kernel_raw'].encode('utf-8');assert hashlib.sha256(raw).hexdigest()==fresh['kernel_sha256']
    prior=(OUT/'recovery-authorized-20261025-v1/IRQ2_KERNEL_RAW_UART_03.bin').read_bytes();assert raw==prior
    save(execution/'COMPUTE_BASELINE_REVIEW.json',dict(scope='USER_AUTHORIZED_TT10_01_WINDOW02_COMPUTE',
        boot_id=fresh['boot_id'],kernel=fresh['kernel'],raw_sha256=fresh['kernel_sha256'],raw_bytes=len(raw),
        exact_previous_reviewed_bytes=True,new_diagnostics=[],known_startup_limitations_still_open=True,
        previous_recovery_review='IRQ2_KERNEL_RECOVERY_REVIEW-02.json',current_preflight='preflight-03/stdout.txt',
        authorization='AUTHORIZATION.json',resource_review=fresh['resource_review'],lock_probe=fresh['lock_probe'],
        new_failures_must_latch_closed=True,thresholds_changed=False,reviewer='Primary agent; evidence acceptance not delegated'))
    payload=base64.b64encode(gzip.compress(driver.read_bytes())).decode()
    code='''"""One explicitly authorized invocation of the exact prepared window02 driver."""
import base64,gzip,hashlib,json,sys
from pathlib import Path
data=gzip.decompress(base64.b64decode(DRIVER_B64))
assert hashlib.sha256(data).hexdigest()==DRIVER_SHA
ns={'__name__':'tt10_window02_prepared_import'}
exec(compile(data,'exact_prepared_window02_driver','exec'),ns)
assert len(ns['DATA']['configurations'])==1
assert ns['DATA']['configurations'][0]['remote']=='/var/lib/kv260-a12/tt10-01-20261025-v2'
original=ns['preflight'];observations=0
def bound_preflight(record=None):
    global observations
    result=original(record)
    if observations==0:
        assert result['boot_id']==EXPECTED_BOOT
        assert result['kernel_sha256']==EXPECTED_RAW_SHA,'Fresh kernel differs from explicitly reviewed compute baseline'
        mem={line.split(':')[0]:int(line.split()[1]) for line in result['memory_raw'].splitlines()}
        assert mem['MemAvailable']>=1310720 and mem['CmaFree']>=98304
        assert result['temperatures_mC'] and all(0<t<55000 for t in result['temperatures_mC'])
        assert not Path('/var/lib/kv260-a12/tt10-01-20261025-v2').exists()
        assert not Path('/var/lock/kv260-a1/history/a12-tt10-01-20261025-v2').exists()
        ns['emit']('EXACT_COMPUTE_BASELINE_AND_RESERVE_RECHECK_PASS',boot_id=EXPECTED_BOOT,
                   kernel_sha256=EXPECTED_RAW_SHA,MemAvailable_kib=mem['MemAvailable'],CmaFree_kib=mem['CmaFree'])
    observations+=1
    return result
ns['preflight']=bound_preflight
sys.argv=['reviewed-window02','--execute-reviewed-window','a12-tt10-01-20261025-v2']
raise SystemExit(ns['main']())
'''
    code=code.replace('DRIVER_B64',repr(payload)).replace('DRIVER_SHA',repr(prepared['driver_sha256'])).replace('EXPECTED_BOOT',repr(fresh['boot_id'])).replace('EXPECTED_RAW_SHA',repr(fresh['kernel_sha256']))
    compile(code,'window02_execute_bound','exec')
    with (execution/'execute_bound.py').open('x',encoding='utf-8') as f:f.write(code)
    save(execution/'EXECUTION_BINDING.json',dict(window_id=prepared['window_id'],driver_sha256=prepared['driver_sha256'],
        bundle_manifest_sha256=prepared['bundle_manifest_sha256'],wrapper_sha256=sha(execution/'execute_bound.py'),
        compute_baseline_review_sha256=sha(execution/'COMPUTE_BASELINE_REVIEW.json'),max_runs=5000,
        calculated_worst_case=4752,single_attempt=True,automatic_retry=False,reboot=False,flash=False))
    print('WINDOW02_AUTHORIZATION_AND_EXACT_BASELINE_BOUND_NO_BOARD_CALL')
if __name__=='__main__':main()
