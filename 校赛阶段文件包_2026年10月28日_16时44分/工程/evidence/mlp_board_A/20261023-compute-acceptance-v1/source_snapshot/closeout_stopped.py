"""PC-only stopped-window audit and evidence seal; never certifies BOARD success."""
import base64
import hashlib
import json
from pathlib import Path
import shutil
import zlib

ROOT=Path(__file__).resolve().parents[3]
EV=ROOT/'evidence/mlp_board_A/20261023-integration-v1'


def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    out=EV/'stopped_audit_01';out.mkdir(exist_ok=False)
    packet=read(EV/'stopped_readback_01/stdout.json')
    for name,meta in packet['files'].items():
        if meta is None:continue
        raw=zlib.decompress(base64.b64decode(meta['zlib_base64'],validate=True))
        assert len(raw)==meta['bytes'] and hashlib.sha256(raw).hexdigest()==meta['sha256']
        assert raw==(EV/'stopped_readback_01'/name).read_bytes()
    rows=[json.loads(l) for l in (EV/'stopped_readback_01/lifecycle.jsonl').read_text().splitlines()]
    worker=[json.loads(l) for l in (EV/'stopped_readback_01/worker.stdout.jsonl').read_text().splitlines()]
    assert rows[-1]['event']=='QUARANTINED_MANAGER_AND_LOCKS_RETAINED'
    permits=[r for r in rows if r['event']=='NEXT_OPERATION_PERMITTED']
    assert len(permits)==1 and permits[0]['phase']=='open'
    assert [r['event'] for r in worker]==['PERMIT_AND_HEALTH','WORKER_PARKED_NO_CLOSE']
    assert worker[-1]['reason']=='RuntimeError: open failed status=8'
    assert packet['files']['worker-result.json'] is None and packet['files']['mlp-receipt.json'] is None
    assert not (EV/'stopped_readback_01/outputs').exists()
    diag=read(EV/'stopped_open_diagnostics_01/state.json')
    assert diag['module_refcount']=='1' and diag['scan']['scan_complete'] and not diag['scan']['scan_issues']
    maps=diag['scan']['device_mappings'];assert len(maps)==1 and maps[0]['pid']==3308
    span=maps[0]['map'].split()[0];lo,hi=[int(x,16) for x in span.split('-')];assert hi-lo==65536
    assert not diag['scan']['device_holders'] and diag['worker']['threads']['3308']['wchan']=='hrtimer_nanosleep'
    assert packet['module_present'] and packet['gdm_state']=='inactive'
    assert packet['overlays']=={'a11-mlp-20261023-v1_image_1':'applied'}
    assert read(EV/'backend-diagnostic-v2/audit.json')['board_retry'] is False
    old=read(ROOT/'evidence/board_platform/A10_20261023_isolated_single_v1/seal_01.json')
    for name,meta in old['files'].items():assert sha(ROOT/name)==meta['sha256'],'changed A10 '+name
    commands={}
    for p in sorted(EV.glob('*.json')):
        d=read(p)
        if 'argv' in d:
            commands[p.name]=dict(argv=d['argv'],exit_code=d.get('exit_code'),evidence_sha256=sha(p))
        elif 'records' in d:
            commands[p.name]=dict(status=d.get('status'),jobs=[dict(name=r['name'],command=r['command'],
                exit_code=r['exit_code']) for r in d['records']],evidence_sha256=sha(p))
        elif 'events' in d:
            commands[p.name]=dict(status=d.get('status'),command=d.get('command'),remote_exit_code=d.get('exit_code'),
                evidence_sha256=sha(p),remote_process_exit_proven=d.get('exit_code')==0)
    for folder in ('stopped_readback_01','stopped_open_diagnostics_01'):
        p=EV/folder/'fetch_receipt.json';d=read(p)
        commands[folder+'/fetch_receipt.json']=dict(argv=d['argv'],exit_code=d['exit_code'],evidence_sha256=sha(p))
    with (out/'COMMANDS.json').open('x') as f:json.dump(commands,f,indent=2)
    report=dict(A11='NOT_PASSED',A12='NOT_ELIGIBLE',boot_id=diag['boot_id'],
        status='OPEN_FAILED_QUARANTINED_AWAITING_RECOVERY_DECISION',real_compute_submissions=0,
        numerical_results=None,service_times=None,speedup=None,explicit_bo_allocations=None,physical_bo_peak_bytes=None,
        manager_pid=3202,worker_pid=3308,worker_sleeping=True,worker_register_vma_bytes=65536,zocl_refcount=1,
        device_fd_holders=[],device_mappings=maps,default_restored=False,locks_and_lease_retained=True,
        last_temperatures_mC=diag['temperatures_mC'],scope='no stress, no retry, no signals, no reboot after failed open',
        core_failure_cause='UNKNOWN: v1 translated native exception or explicit device check to error 8 without phase/detail',
        diagnostic_repair='backend-diagnostic-v2: 30 PC control cases, six phase-detail checks and ARM64 build PASS; NOT_DEPLOYED',
        A10_sealed_files_unchanged=len(old['files']),
        next='New scoped recovery decision; no automatic force termination/unload. Later new test window only after normal restoration and reviewed diagnostic package.',
        P2='NOT_IMPLEMENTED_SAFETY_EXCLUDED_OR_OUT_OF_SCOPE')
    with (out/'AUDIT.json').open('x') as f:json.dump(report,f,indent=2)
    snap=out/'source_snapshot';snap.mkdir()
    for p in (ROOT/'platform/qwen35/a11').iterdir():
        if p.is_file():shutil.copyfile(p,snap/p.name)
    docs=out/'governance_snapshot';docs.mkdir()
    for name in ('PROJECT_STATUS.json','DESIGN_GAP.md','TEST_MATRIX.md','AI_ASSISTANCE.md','DECISIONS.md'):
        shutil.copyfile(ROOT/'docs'/name,docs/name)
    shutil.copyfile(ROOT/'docs/status/A.md',docs/'A.md')
    files={str(p.relative_to(ROOT)):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(EV.rglob('*'))
           if p.is_file() and p.name not in ('closeout_command_01.json','SEAL.json')}
    with (out/'SEAL.json').open('x') as f:json.dump(dict(status='SEALED_STOPPED_NOT_PASSED',files=files),f,indent=2)
    print(json.dumps(dict(A11=report['A11'],real_compute_submissions=0,evidence_files=len(files),A10_unchanged=len(old['files']))))


if __name__=='__main__':main()
