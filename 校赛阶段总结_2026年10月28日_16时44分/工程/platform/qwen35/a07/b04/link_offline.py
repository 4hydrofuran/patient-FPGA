"""Fail-closed A07 hardware link; run under the shared queue in a NEW directory.

No emulation, board access, deployment, or A06 acceptance override.
"""
import argparse, hashlib, json, os, subprocess, sys, zipfile
from pathlib import Path

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):
    with Path(p).open('x') as f:json.dump(v,f,indent=2)
def run(argv, name):
    p=subprocess.run([str(x) for x in argv],capture_output=True,text=True)
    save(name,{'argv':list(map(str,argv)),'cwd':str(Path.cwd()),'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
    if p.returncode:raise RuntimeError(f'{name} exit {p.returncode}')
    return p.stdout
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root',type=Path,required=True)
    ap.add_argument('--platform',type=Path,required=True)
    ap.add_argument('--xo',type=Path,required=True)
    a=ap.parse_args();a.root=a.root.resolve()
    source=json.loads((a.root/'hw/linear_A/KERNEL_SOURCE.json').read_text())
    gate={k:source.get(k) for k in ['accepted','frozen','production_or_A07_link_allowed']}
    save('link-gate.json',{'gates':gate,'source_sha256':sha(a.root/'hw/linear_A/KERNEL_SOURCE.json'),'BOARD':'NOT_TESTED'})
    if not all(value is True for value in gate.values()):
        print('BLOCKED_A06_ACCEPTANCE: no v++ invoked',file=sys.stderr);return 3
    if os.environ.get('XCL_EMULATION_MODE') is not None:raise ValueError('no emulation')
    if sha(a.xo)!=source['xo_sha256']:raise ValueError('XO identity mismatch')
    with zipfile.ZipFile(a.xo) as z:
        actual=hashlib.sha256(z.read(source['embedded_metadata_member'])).hexdigest()
        if actual!=source['embedded_metadata_sha256']:raise ValueError('embedded XML mismatch')
    expected={'kv260_base.xpfm':'563308140b285caf10ee9fd5294fc401b14390fd99267855cabd11e1c6b0f6aa',
              'hw/hw.xsa':'97daf86957a2839965cac39a0a6dc36a4619c96c127ad8fb98b9ca5e960c0630'}
    for name,digest in expected.items():
        if sha(a.platform.parent/name)!=digest:raise ValueError('official platform mismatch: '+name)
    version=run(['v++','--version'],'vpp-version.json')
    if '2026.1' not in version or '6511674' not in version:raise ValueError('tool version mismatch')
    info=run(['platforminfo','--platform',a.platform],'platforminfo.json')
    if 'xck26-sfvc784-2LV-c' not in info:raise ValueError('wrong device')
    cfg=Path(__file__).with_name('link.cfg')
    run(['v++','--link','--target','hw','--save-temps','--platform',a.platform,'--config',cfg,
         '--vivado.synth.jobs','2','--vivado.impl.jobs','2','--output','w4a8.xclbin',a.xo],'link.json')
    if not Path('w4a8.xclbin').is_file():raise ValueError('no xclbin')
    run(['xclbinutil','--input','w4a8.xclbin','--info'],'xclbin-info.json')
    save('artifact.json',{'xclbin_sha256':sha('w4a8.xclbin'),'xo_sha256':sha(a.xo),
         'link_config_sha256':sha(cfg),'implementation_acceptance':'PENDING_REPORT_REVIEW',
         'BOARD':'NOT_TESTED','linux_budget_bytes':None,'pl_budget_bytes':None})
    return 0
if __name__=='__main__':raise SystemExit(main())
