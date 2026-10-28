"""Prepare immutable PC recovery snapshots and a read-only final collector."""
import ast
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[3]
EV=ROOT/'evidence/mlp_board_A/20261023-recovery-only-v1'


def main():
    out=EV/'reader-v1';out.mkdir(exist_ok=False)
    prior=ROOT/'evidence/mlp_board_A/20261023-integration-v1/execution-host-v1'
    text=(prior/'read_single_result.py').read_text()
    anchor="    lifecycle = root / 'lifecycle.jsonl'"
    assert text.count(anchor)==1
    text=text.replace(anchor,"""    recovery=root/'recovery-only-20261023-v1'
    for name in ('lifecycle.jsonl','result.json'):
        p=recovery/name
        files['recovery-only-20261023-v1/'+name]=pack(p.read_bytes()) if p.is_file() else None
    archive=Path('/var/lock/kv260-a1/history/a11-mlp-20261023-v1-aborted-open/lease.json')
    files['archived-lease.json']=pack(archive.read_bytes()) if archive.is_file() else None
    import sys
    sys.path.insert(0,str(root))
    manifest=json.loads((root/'manifest.json').read_text())
    gate_source=root/'accelerator_release_gate_v2.py'
    assert hashlib.sha256(gate_source.read_bytes()).hexdigest()==manifest['files'][gate_source.name]['sha256']
    from accelerator_release_gate_v2 import collect
    scan=collect(allow_ps_display=True)
"""+anchor)
    anchor="                  files=files, manager_pid=manager_pid, manager_proc=proc, kernel_log=pack(klog.stdout),"
    assert text.count(anchor)==1
    text=text.replace(anchor,"                  scan=scan, worker_exists=Path('/proc/3308').exists(),\n"+anchor)
    ast.parse(text)
    (out/'read_single_result.py').write_text(text)
    shutil.copyfile(prior/'fetch_result.py',out/'fetch_result.py')
    sources=EV/'source_snapshot';sources.mkdir(exist_ok=False)
    for name in ('recover_open_only.py','test_recover_open_only.py','recovery_host.py','prepare_recovery_evidence.py'):
        p=ROOT/'platform/qwen35/a11'/name
        ast.parse(p.read_text());shutil.copyfile(p,sources/name)
    manifest={str(p.relative_to(EV)):hashlib.sha256(p.read_bytes()).hexdigest()
              for folder in (out,sources) for p in folder.iterdir()}
    (EV/'source_manifest.json').write_text(json.dumps(dict(board_contact=False,files=manifest),indent=2))
    print(json.dumps(dict(board_contact=False,files=len(manifest))))


if __name__=='__main__':main()
