"""Executed in the unique shared-queue work directory; never build in B intake."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path('/mnt/c/Patientqwen')
B=ROOT/'hw/linear_B_received/B03-fdd1d656290b-20261003'
E=ROOT/'evidence/A06_acceptance/local-tests-v1'
sys.path.insert(0,str(ROOT/'platform/a1'))
from record import run

def main():
    E.mkdir(parents=True,exist_ok=False)
    work=Path.cwd()
    outcomes=[]
    for variant in ('baseline','reuse','double'):
        source=B/('baseline/b02/src/w4a8_linear_v1.cpp' if variant=='baseline' else 'src/w4a8_prefill_v1.cpp')
        flags=['-DB02_CACHE_X','-DB02_AXI_X128','-DB03_TEST']
        if variant!='baseline':flags+=['-DB03_REUSE']
        if variant=='double':flags+=['-DB03_DOUBLE_BUFFER']
        include=['-I'+str(source.parent),'-I'+str(B/'host'),'-I'+str(ROOT/'quant/reference')]
        common=flags+include+['-fno-fast-math','-ffp-contract=off']
        exe=work/('acceptance-'+variant)
        argv=['g++','-std=c++17','-O3','-Wno-unknown-pragmas']+common+[
            str(source),str(ROOT/'quant/reference/w4a8.cpp'),str(ROOT/'platform/qwen35/a06/acceptance.cpp'),'-o',str(exe)]
        code=run(argv,E/(variant+'-compile.json'),cwd=work)
        if code:outcomes.append({'variant':variant,'compile':code});continue
        code=run([str(exe),str(B/'fixtures'),str(ROOT/'models/sidecar_A/qwen35-v1')],E/(variant+'-pc.json'),cwd=work)
        cflags=' '.join(common+['-std=c++17'])
        cfg=work/(variant+'.cfg')
        cfg.write_text(f'''part=xck26-sfvc784-2LV-c
[hls]
flow_target=vitis
syn.file={source}
syn.top=w4a8_linear_v1
syn.cflags={cflags}
tb.file={ROOT}/quant/reference/w4a8.cpp
tb.file={ROOT}/platform/qwen35/a06/acceptance.cpp
tb.cflags={cflags}
clock=6.667
syn.compile.unsafe_math_optimizations=0
syn.compile.pipeline_loops=0
csim.argv={B}/fixtures {ROOT}/models/sidecar_A/qwen35-v1
package.output.format=xo
''')
        (E/(variant+'.cfg')).write_bytes(cfg.read_bytes())
        csim=run(['/home/member-a/AMDDesignTools/2026.1/Vitis/bin/vitis-run','--mode','hls','--csim','--config',str(cfg),'--work_dir',str(work/(variant+'-csim'))],E/(variant+'-csim.json'),cwd=work)
        outcomes.append({'variant':variant,'PC':code,'Csim':csim,'executable':str(exe),'sha256':hashlib.sha256(exe.read_bytes()).hexdigest()})
    (E/'outcomes.json').write_text(json.dumps(outcomes,indent=2))
    return int(any(o.get('PC',1) or o.get('Csim',1) for o in outcomes))

if __name__=='__main__':raise SystemExit(main())
