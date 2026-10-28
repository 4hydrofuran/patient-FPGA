"""PC-only tests and immutable source/evidence pins before cleanup continuation."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[3]
EV=ROOT/'evidence/mlp_board_A/20261023-recovery-continuation-v1'


def save(name,obj):
    with (EV/name).open('x',encoding='utf-8') as f:json.dump(obj,f,indent=2,ensure_ascii=False)


def run(name,args):
    started=datetime.now(timezone.utc).isoformat();t=time.monotonic()
    p=subprocess.run(args,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=120)
    save(name,dict(argv=args,started_utc=started,elapsed_s=time.monotonic()-t,exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr,board_contact=False))
    if p.returncode:raise RuntimeError(name+' failed; no board action')


def main():
    EV.mkdir(exist_ok=False)
    save('AUTHORIZATION.json',dict(user_reply='允许继续仅收尾',scope='Recheck and terminate only non-native stopped cleanup waiter5322; ordinary remove/rmmod/default PL/GDM restoration; no A11 retry',
        excluded=['compute','forced unload','reboot/reset','power cycle','SD/QSPI/default boot change','system upgrade'],
        readonly_readiness='at most four samples; require two consecutive complete equal PID/start-tick sets; no reference/device/kernel failure waived'))
    run('contracts_01.json',[sys.executable,'-B','scripts/release/check_contracts.py'])
    run('config_01.json',[sys.executable,'-B','scripts/release/qwen35_config.py'])
    run('tests_01.json',['wsl','-d','KV260-A-2204','--','/usr/bin/python3','-B',
        '/mnt/c/Patientqwen/platform/qwen35/a11/test_recover_cleanup_waiter.py'])
    sealed={}
    for seal in ['evidence/mlp_board_A/20261023-integration-v1/stopped_audit_01/SEAL.json',
                 'evidence/board_platform/A10_20261023_isolated_single_v1/seal_01.json']:
        entries=json.loads((ROOT/seal).read_bytes())['files']
        for rel,v in entries.items():
            raw=(ROOT/rel).read_bytes()
            assert len(raw)==v['bytes'] and hashlib.sha256(raw).hexdigest()==v['sha256'],rel
        sealed[seal]=len(entries)
    snapshot=EV/'source_snapshot';snapshot.mkdir();files={}
    for name in ['recover_cleanup_waiter.py','recovery_continuation_host.py','test_recover_cleanup_waiter.py','prepare_recovery_continuation.py']:
        src=Path(__file__).parent/name;dst=snapshot/name;shutil.copyfile(src,dst)
        files['source_snapshot/'+name]=hashlib.sha256(dst.read_bytes()).hexdigest()
    save('PRECHECK.json',dict(status='PASS_PC_ONLY',prior_seals_verified=sealed,source_sha256=files,board_contact=False,A11='NOT_PASSED'))
    print(json.dumps(dict(status='PC_PREPARED_NOT_EXECUTED',output=str(EV),prior_seals_verified=sealed)))
    return 0


if __name__=='__main__':raise SystemExit(main())
