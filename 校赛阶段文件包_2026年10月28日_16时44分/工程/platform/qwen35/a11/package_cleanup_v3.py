"""Create a small unaccepted PC candidate, never transfer or execute on board."""
import ast
import hashlib
import json
from pathlib import Path
import shutil
import tarfile

ROOT=Path(__file__).resolve().parents[3]
EV=ROOT/'evidence/mlp_board_A/20261023-cleanup-pc-fix-v3'


def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    assert json.loads((EV/'tests_03.json').read_bytes())['exit_code']==0
    prior={}
    for rel in ['evidence/board_platform/A10_20261023_isolated_single_v1/seal_01.json',
                'evidence/mlp_board_A/20261023-integration-v1/stopped_audit_01/SEAL.json',
                'evidence/mlp_board_A/20261023-recovery-continuation-v1/SEAL.json']:
        entries=json.loads((ROOT/rel).read_bytes())['files']
        for name,v in entries.items():
            p=ROOT/name;assert p.stat().st_size==v['bytes'] and digest(p)==v['sha256'],name
        prior[rel]=len(entries)
    target=EV/'candidate/cleanup-v3-20261023';target.mkdir(parents=True,exist_ok=False)
    sources=['cleanup_board_v3.py','cleanup_controller_v3.py','cleanup_control_v3.py']
    for name in sources:
        src=Path(__file__).parent/name;ast.parse(src.read_text());shutil.copyfile(src,target/name)
    baseline=ROOT/'evidence/mlp_board_A/20261023-recovery-continuation-v1/readback_01/kernel.raw.txt'
    shutil.copyfile(baseline,target/'reviewed-kernel.raw.txt')
    manifest=dict(schema='A11_CLEANUP_V3_CANDIDATE',PC='TESTED',BOARD='NOT_TESTED',accepted=False,
        compute_authorized=False,authorization_required=True,
        expected_boot='8422f92f-d01f-4849-ad19-6e66b640a9ad',expected_waiter=dict(pid=6174,start_ticks=383249),
        files={p.name:dict(bytes=p.stat().st_size,sha256=digest(p)) for p in sorted(target.iterdir())})
    with (target/'candidate.json').open('x') as f:json.dump(manifest,f,indent=2)
    archive=EV/'a11-cleanup-v3-PC-CANDIDATE-NOT-BOARD-TESTED.tar.gz'
    with archive.open('xb') as raw,tarfile.open(fileobj=raw,mode='w:gz') as tar:
        for p in sorted(target.iterdir()):
            assert p.is_file() and not p.is_symlink()
            info=tar.gettarinfo(str(p),arcname='cleanup-v3-20261023/'+p.name)
            info.uid=info.gid=0;info.uname=info.gname='';info.mode=0o600
            with p.open('rb') as data:tar.addfile(info,data)
    with tarfile.open(archive,'r:gz') as tar:
        entries=tar.getmembers()
        assert len(entries)==5 and all(e.isfile() and not Path(e.name).is_absolute() and '..' not in Path(e.name).parts for e in entries)
    out=dict(status='PC_CANDIDATE_NOT_DEPLOYED',BOARD='NOT_TESTED',board_connections=0,board_mutations=0,
        tests=30,prior_seals_verified=prior,candidate_manifest_sha256=digest(target/'candidate.json'),
        archive=dict(path=str(archive.relative_to(ROOT)),bytes=archive.stat().st_size,sha256=digest(archive)),
        contents='3 reviewed Python sources + reviewed kernel log + manifest; no credentials/models/images/system disks/WSL')
    with (EV/'PACKAGE.json').open('x') as f:json.dump(out,f,indent=2)
    print(json.dumps(out))


if __name__=='__main__':main()
