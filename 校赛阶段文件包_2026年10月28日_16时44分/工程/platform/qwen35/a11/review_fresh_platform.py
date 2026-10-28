"""PC-only audit of this boot's exact diagnostics and captured DT compatibility."""
import base64
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
EV=ROOT/'evidence/mlp_board_A/20261023-integration-v1'
sys.path[:0]=[str(ROOT/'platform/a1'),str(ROOT/'platform/qwen35/a10')]
from audit_overlay_files import get,memory,sha
from kernel_log_gate import diagnostics


def normalized(raw):
    def norm(row):
        row=re.sub(r'^<\d+>\[\s*[0-9.]+\]\s*','',row)
        row=re.sub(r'CPU: \d+','CPU: N',row)
        return re.sub(r'\b[0-9a-f]{16}\b','HEX64',row)
    return {norm(x['text']) for x in diagnostics(raw)}


def main():
    out=EV/'fresh-platform-v2';out.mkdir(exist_ok=False)
    raw=(EV/'candidate_readonly_01/baseline.raw.txt').read_text()
    old=(ROOT/'evidence/board_platform/A10_20261023_isolated_single_v1/candidate_review_01/baseline.raw.txt').read_text()
    delta=normalized(raw)-normalized(old)
    assert not delta,repr(delta)
    assert not re.search(r'\b(Oops:|BUG:|Kernel panic|refcount_t:|hung task)',raw)
    packet=json.loads((EV/'candidate_readonly_01/result.json').read_text())
    assert packet['process_scan']['scan_complete'] and not packet['process_scan']['scan_issues']
    assert not packet['process_scan']['device_holders'] and not packet['process_scan']['device_mappings']
    receipt=json.loads((EV/'irq2_dt_01.json').read_text(encoding='utf-8-sig'))
    assert receipt['closed'] and receipt['records'][0]['exit_code']==0
    payload=[json.loads(l) for l in receipt['records'][0]['raw'].splitlines() if l.startswith('{')]
    assert len(payload)==1
    tree={}
    for key,value in payload[0].items():
        bits=key.split('/');node=tree
        for name in bits[:-1]:node=node.setdefault(name,{})
        if bits[-1]!='name':node[bits[-1]]=base64.b64decode(value,validate=True)
    def emit(node,indent=1):
        rows=[]
        for name,value in sorted(node.items(),key=lambda item:(isinstance(item[1],dict),item[0])):
            if isinstance(value,dict):rows += ['  '*indent+name+' {',*emit(value,indent+1),'  '*indent+'};']
            else:rows.append('  '*indent+name+(' = ['+value.hex(' ')+'];' if value else ';'))
        return rows
    (out/'runtime.dts').write_text('/dts-v1/;\n/ {\n'+'\n'.join(emit(tree))+'\n};\n')
    tools=Path('/home/member-a/a10-kernel-full-20261019-v1/deps/root')
    os.environ['PATH']=str(tools/'usr/bin')+':'+os.environ['PATH']
    os.environ['LD_LIBRARY_PATH']=str(tools/'usr/lib/x86_64-linux-gnu')
    dtc='/home/member-a/a10-kernel-irq2-20261021-v1/build/scripts/dtc/dtc'
    commands=[]
    def run(argv):
        p=subprocess.run(list(map(str,argv)),cwd=out,capture_output=True,text=True)
        commands.append(dict(argv=list(map(str,argv)),exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr))
        (out/'commands.json').write_text(json.dumps(commands,indent=2));assert p.returncode==0
    run([dtc,'-@','-I','dts','-O','dtb','-o','runtime.dtb','runtime.dts'])
    base=out/'runtime.dtb';merged=out/'merged-PC_ONLY.dtb'
    run(['fdtoverlay','-i',base,'-o',merged,EV/'overlay-v1/a11-mlp.dtbo'])
    assert memory(base)==memory(merged)
    cu=get(merged,'/__symbols__','w4a8_linear_v1_1','s')
    intc=get(merged,'/__symbols__','axi_intc_0','s')
    assert get(merged,cu,'reg')=='0 b0000000 0 10000'
    assert get(merged,cu,'interrupts')=='1 4'
    assert get(merged,cu,'xlnx,s-axi-control-addr-width')=='8'
    assert get(merged,intc,'xlnx,num-intr-inputs')=='20' and get(merged,intc,'xlnx,kind-of-intr')=='fffffffd'
    ph=int(get(merged,intc,'phandle'),16)
    irqs=[int(x,16) for x in get(merged,'/axi/zyxclmm_drm','interrupts-extended').split()]
    assert irqs==[x for n in range(32) for x in (ph,n,4)]
    result=dict(status='FRESH_IRQ2_BASELINE_REVIEWED_PC_OVERLAY_COMPATIBLE',
        boot_id=packet['boot_id'],baseline_sha256=packet['baseline_sha256'],
        new_normalized_diagnostics=[],normalization='only timestamps, CPU number and 64-bit register values; full raw logs retained',
        known_limits=['x509 certificate boot warning','unsigned irq2 modules','old PMUFW pinctrl features',
                     'TPM self-test startup message','default overlay removal leak advisory','audit callback suppression'],
        runtime_dt_capture_sha256=sha(EV/'irq2_dt_01.json'),memory_and_bootargs_unchanged=True,
        actual_mlp_configuration_loaded=False,BOARD_compute='NOT_TESTED',
        files={p.name:sha(p) for p in out.iterdir() if p.is_file()})
    (out/'audit.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))


if __name__=='__main__':main()
