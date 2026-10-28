"""This exact reviewed boot/baseline only. No retry, reset or forced cleanup."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path('/var/lib/kv260-a11/a11-mlp-20261023-v3')
BOOT='8422f92f-d01f-4849-ad19-6e66b640a9ad'
MANIFEST_SHA='64f9cc327b006f2ca12d213c159d33d404e7668679144c15e95c6290fcf0bcde'
BASELINE_SHA='6e147df356b0197fde6575f1795489355652b69bd9502e3663b2187ca46c4247'
PRIOR_AUDIT_SHA='b5cb0d3037e047da5ae2ae42fb700ad5ac5f9c3518412a63bf868bdf001db9ce'


def verify_fresh_log(proc):
    if proc.returncode!=0 or proc.stderr or hashlib.sha256(proc.stdout).hexdigest()!=BASELINE_SHA:
        raise RuntimeError('BASELINE_CHANGED_REVIEW_REQUIRED_NO_TRIAL')
    return proc.stdout


def main():
    if len(sys.argv)!=2 or sys.argv[1]!=BOOT or os.geteuid()!=0:
        raise RuntimeError('EXACT_AUTHORIZED_BOOT_AND_ROOT_REQUIRED')
    if ROOT.is_symlink() or ROOT.stat().st_uid!=0 or ROOT.stat().st_mode&0o022 or hashlib.sha256((ROOT/'manifest.json').read_bytes()).hexdigest()!=MANIFEST_SHA:
        raise RuntimeError('ROOT_BUNDLE_PIN_DIFFERS')
    sys.path.insert(0,str(ROOT))
    from mlp_policy import KERNEL,MACHINE,SCOPE,digest,need,trusted_file,validate_review,verify_bundle
    from accelerator_release_gate_v2 import collect,require_no_users
    need(os.uname().machine=='aarch64' and os.uname().release==KERNEL,'exact kernel required')
    need(Path('/proc/sys/kernel/random/boot_id').read_text().strip()==BOOT and digest('/etc/machine-id')==MACHINE,'identity changed')
    manifest=verify_bundle(ROOT,MANIFEST_SHA)
    for name in manifest['files']:trusted_file(ROOT/name)
    need(not os.path.lexists('/var/lock/kv260-a1/active') and not Path('/sys/module/zocl').exists(),'active device/lease')
    need(digest(ROOT/'prior-a10-audit.json')==PRIOR_AUDIT_SHA,'prior acceptance changed')
    for name in ('baseline.raw.txt','review.json','attempt.json','native-attempt.json'):
        need(not os.path.lexists(ROOT/name),'authorization already reserved')
    scans=[]
    for attempt in range(4):
        scan=collect(allow_ps_display=True);scans.append(scan)
        if scan.get('scan_complete') is True:break
        need(scan.get('boot_id')==scan.get('boot_id_after')==BOOT and
             not scan.get('device_holders') and not scan.get('device_mappings'),'unsafe preflight')
        issues=scan.get('scan_issues');need(type(issues) is list and issues,'unknown scan failure')
        for issue in issues:
            need(issue.get('reason') in ('PROCESS_SET_CHANGED','ValueError: PROCESS_OR_FD_TABLE_CHANGED'),
                 'nontransient scan failure')
        if attempt<3:time.sleep(.15)
    with (ROOT/'preflight-scans.json').open('x') as f:json.dump(scans,f)
    raw=verify_fresh_log(subprocess.run(['dmesg','--raw'],capture_output=True,timeout=3))
    stamp=time.monotonic_ns();require_no_users(scan,True,boot_id=BOOT)
    review=validate_review(dict(schema='A11_MLP_REVIEW_V1',scope=SCOPE,authorized=True,compute_authorized=True,
        allow_gdm_stop_restore=True,max_submissions=23,explicit_bo_budget_bytes=4194304,
        boot_id=BOOT,kernel=KERNEL,machine_sha256=MACHINE,window_id=ROOT.name,
        baseline_sha256=BASELINE_SHA,bundle_sha256=MANIFEST_SHA,prior_a10_audit_sha256=PRIOR_AUDIT_SHA,
        baseline_read_uptime_ns=stamp,authorization='USER_REQUESTED_A11_COMPLETE_NUMERIC_PERFORMANCE_AND_REPAIR_20261023'))
    os.umask(0o077)
    with (ROOT/'baseline.raw.txt').open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    with (ROOT/'review.json').open('x',encoding='utf-8') as f:json.dump(review,f,sort_keys=True);f.flush();os.fsync(f.fileno())
    pin=digest(ROOT/'review.json')
    print(json.dumps(dict(event='A11_REVIEW_RESERVED',boot_id=BOOT,review_sha256=pin,baseline_sha256=BASELINE_SHA)),flush=True)
    os.execv('/usr/bin/python3',['/usr/bin/python3','-B','-I',str(ROOT/'mlp_manager_entry.py'),
        '--execute-authorized-mlp-once','--source',str(ROOT),'--review-sha256',pin])


if __name__=='__main__':main()
