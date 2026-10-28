"""Derive a fresh complete compute candidate from the sealed open-fix package."""
import argparse,hashlib,json,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
OLD=ROOT/'evidence/mlp_board_A/20261023-open-investigation-v1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def change(s,a,b):
    if s.count(a)!=1:raise ValueError('source seam differs: '+a)
    return s.replace(a,b)
def main(out):
    source=OLD/'mlp-fixed-PC-candidate-v2';m=json.loads((source/'manifest.json').read_bytes())
    seals=json.loads((OLD/'SEAL.json').read_bytes())['files']
    for p in source.rglob('*'):
        if p.is_file():
            n=p.relative_to(ROOT).as_posix();assert sha(p)==seals[n]['sha256']
    shutil.copytree(source,out)
    for n in ('mlp_engine.py','mlp_worker.py','manager_support.py','compute_result.py'):
        shutil.copyfile(Path(__file__).with_name(n),out/n)
    # Reuse the independently board-tested complete-scan re-observation fix.
    shutil.copyfile(OLD/'open-package-v5/mlp_base.py',out/'mlp_base.py')
    p=out/'mlp_boundary_v2.py';s=p.read_text()
    start=s.index('def validate_result(');end=s.index('\n\nclass MlpBoundary',start)
    s=s[:start]+'from compute_result import validate_result\n'+s[end:];p.write_text(s)
    p=out/'mlp_manager.py';s=p.read_text()
    s=change(s,"status='PASS_MLP_23_AND_NORMAL_RELEASE_REQUIRES_INDEPENDENT_AUDIT'",
             "status=('PASS_MLP_23_AND_NORMAL_RELEASE_REQUIRES_INDEPENDENT_AUDIT' if result['status']=='NORMAL_CLOSED_A11_MINIMAL' else 'FAILED_COMPUTE_NORMAL_RELEASE_REQUIRES_INDEPENDENT_AUDIT')")
    s=change(s,'compute_runs=23,',"compute_runs=result['real_submissions'],")
    s=change(s,"self.emit('MLP_LIFECYCLE_COMPLETE_DEFAULT_PL_RESTORED', receipt=receipt)",
             "self.emit('MLP_LIFECYCLE_COMPLETE_DEFAULT_PL_RESTORED' if result['status']=='NORMAL_CLOSED_A11_MINIMAL' else 'FAILED_MLP_DEFAULT_PL_RESTORED', receipt=receipt)")
    p.write_text(s)
    p=out/'mlp_policy.py';s=p.read_text();s=change(s,"'mlp_worker.py','mlp_manager.py'","'compute_result.py','mlp_worker.py','mlp_manager.py'");p.write_text(s)
    m['files']={p.relative_to(out).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(out.rglob('*')) if p.is_file() and p!=out/'manifest.json'}
    (out/'manifest.json').write_bytes(json.dumps(m,indent=2).encode())
    for p in out.glob('*.py'):compile(p.read_bytes(),str(p),'exec')
    sys.path.insert(0,str(out))
    from mlp_policy import verify_bundle
    verify_bundle(out,sha(out/'manifest.json'))
    print(json.dumps(dict(status='CANDIDATE_NOT_DEPLOYED',files=len(m['files'])+1,manifest_sha256=sha(out/'manifest.json'))))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);main(p.parse_args().out.resolve())
