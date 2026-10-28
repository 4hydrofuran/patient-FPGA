"""After official license recovery only: rerun Csim, not the passed PC suite.

Run through the shared queue in a NEW unique workdir. This does not waive
missing XO/B evidence and does not change KERNEL_SOURCE acceptance.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT=Path('/mnt/c/Patientqwen')
E=ROOT/'evidence/A06_acceptance'
sys.path.insert(0,str(ROOT/'platform/a1'))
from record import run

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--label',required=True);args=ap.parse_args()
    if not re.fullmatch(r'[a-z0-9-]{1,50}',args.label):raise ValueError('unsafe label')
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    snapshot=json.loads((E/'test-inputs.sha256.json').read_text())
    for name in ['platform/qwen35/a06/acceptance.cpp','quant/reference/w4a8.cpp','quant/reference/w4a8.hpp']:
        if sha(ROOT/name)!=snapshot[name]:raise RuntimeError('test input changed: '+name)
    received=json.loads((E/'intake-v1/download-manifest.json').read_text())
    for f in received['files']:
        p=ROOT/'hw/linear_B_received/B03-fdd1d656290b-20261003'/f['path']
        if sha(p)!=f['sha256']:raise RuntimeError('received B file changed: '+f['path'])
    out=E/('csim-retry-'+args.label);out.mkdir(exist_ok=False)
    results=[]
    for variant in ['baseline','reuse','double']:
        cfg=Path.cwd()/(variant+'.cfg');cfg.write_bytes((E/f'local-tests-v1/{variant}.cfg').read_bytes())
        code=run(['/home/member-a/AMDDesignTools/2026.1/Vitis/bin/vitis-run','--mode','hls','--csim',
                  '--config',str(cfg),'--work_dir',str(Path.cwd()/(variant+'-csim'))],out/(variant+'.json'))
        results.append({'variant':variant,'exit_code':code})
        if code:break  # avoid repeating a common environment failure
    (out/'summary.json').write_text(json.dumps(results,indent=2))
    return int(len(results)!=3 or any(v['exit_code'] for v in results))
if __name__=='__main__':raise SystemExit(main())
