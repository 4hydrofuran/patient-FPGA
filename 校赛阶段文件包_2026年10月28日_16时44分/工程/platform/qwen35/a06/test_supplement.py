"""A independent PC/Csim retry and reviewed provider replay in unique queue work."""
import hashlib,json,os,sys
from pathlib import Path
R=Path('/mnt/c/Patientqwen');B=R/'hw/linear_B_received/B03-supplement-e227297-20261003/payload'
E=R/'evidence/A06_acceptance/supplement-v1'
sys.path.insert(0,str(R/'platform/a1'))
from record import run
def main():
    work=Path.cwd();out=E/'tests';out.mkdir(exist_ok=False)
    flags=['-DB02_CACHE_X','-DB02_AXI_X128','-DB03_TEST','-DB03_REUSE','-DB03_DOUBLE_BUFFER',
           '-I'+str(B/'src'),'-I'+str(B/'host'),'-I'+str(R/'quant/reference'),'-fno-fast-math','-ffp-contract=off','-std=c++17']
    sources=[str(B/'src/w4a8_prefill_v1.cpp'),str(R/'quant/reference/w4a8.cpp'),str(R/'platform/qwen35/a06/acceptance.cpp')]
    exe=work/'A-independent'
    assert run(['g++','-O3','-Wno-unknown-pragmas']+flags+sources+['-o',str(exe)],out/'compile.json')==0
    assert run([str(exe),str(B/'fixtures'),str(R/'models/sidecar_A/qwen35-v1')],out/'pc.json')==0
    cfg=work/'acceptance.cfg';cf=' '.join(flags)
    cfg.write_text(f'part=xck26-sfvc784-2LV-c\n[hls]\nflow_target=vitis\nsyn.top=w4a8_linear_v1\nsyn.file={sources[0]}\nsyn.cflags={cf}\ntb.file={sources[1]}\ntb.file={sources[2]}\ntb.cflags={cf}\nclock=6.667\nsyn.compile.unsafe_math_optimizations=0\nsyn.compile.pipeline_loops=0\ncsim.argv={B}/fixtures {R}/models/sidecar_A/qwen35-v1\n')
    (out/'acceptance.cfg').write_bytes(cfg.read_bytes())
    csim=run(['/home/member-a/AMDDesignTools/2026.1/Vitis/bin/vitis-run','--mode','hls','--csim','--config',str(cfg),'--work_dir',str(work/'csim')],out/'csim.json')
    provider=run(['python3',str(B/'tools/check_prefill_supplement.py'),str(B.parent/'B03_A06_supplement_20261003.zip'),
                  str(work/'provider'), '--cxx','/usr/bin/g++','--receipt',str(out/'provider-replay.json')],out/'provider-command.json')
    (out/'outcome.json').write_text(json.dumps({'PC':0,'Csim':csim,'provider_replay':provider,'work':str(work),'BOARD':'NOT_TESTED'},indent=2))
    # Csim environment failure is preserved independently, not mislabeled PASS.
    return provider
if __name__=='__main__':raise SystemExit(main())
