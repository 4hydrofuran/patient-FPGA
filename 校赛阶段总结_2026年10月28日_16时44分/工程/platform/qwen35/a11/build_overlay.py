"""PC-only MLP deployment derivative; never touches a board or boot media."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'platform/a1'))
from audit_overlay_files import get,memory,sha


def build(out):
    out.mkdir(parents=True,exist_ok=False)
    tools=Path('/home/member-a/a10-kernel-full-20261019-v1/deps/root')
    os.environ['PATH']=str(tools/'usr/bin')+':'+os.environ['PATH']
    os.environ['LD_LIBRARY_PATH']=str(tools/'usr/lib/x86_64-linux-gnu')
    dtc='/home/member-a/a10-kernel-irq2-20261021-v1/build/scripts/dtc/dtc'
    commands=[]
    def run(argv):
        p=subprocess.run(list(map(str,argv)),capture_output=True,text=True,cwd=out)
        commands.append(dict(argv=list(map(str,argv)),exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr))
        (out/'commands.json').write_text(json.dumps(commands,indent=2),encoding='utf-8')
        if p.returncode:raise RuntimeError('PC overlay command failed; see commands.json')
        return p.stdout
    old=ROOT/'platform/local/a10-isolated-single-20261023-v1/a1-vadd.dtbo'
    assert sha(old)=='14a014624b084f8c9f39fd13e15e156360f9eae367b7da7994328fee432e4646'
    meta_path=ROOT/'evidence/mlp_board_A/20261023-preparation-v1/metadata.json'
    meta=json.loads(meta_path.read_text())
    assert meta['cu_address']==0xb0000000 and meta['cu_interrupt']==1
    assert meta['kernel_params']['C_S_AXI_CONTROL_ADDR_WIDTH']=='8'
    assert meta['intc_params']['C_KIND_OF_INTR']=='0xfffffffd'
    assert meta['intc_params']['C_S_AXI_ACLK_FREQ_MHZ']=='149.9985'
    text=run([dtc,'-I','dtb','-O','dts',old])
    # Shared platform nodes retain their reviewed A10 bytes/semantics. Kernel
    # properties come from the separately pinned MLP HWH and xclbin metadata.
    text=text.replace('a1-vadd.bit.bin','a11-mlp.bit.bin')
    text=text.replace('krnl_vadd_1','w4a8_linear_v1_1').replace('krnl_vadd','w4a8_linear_v1')
    text=text.replace('xlnx,krnl-vadd-1.0','xlnx,w4a8-linear-v1-1.0')
    for old_value,new_value in [
        ('xlnx,s-axi-control-addr-width = <0x06>','xlnx,s-axi-control-addr-width = <0x08>'),
        ('xlnx,ii = <0x00>','xlnx,ii = "2 ~ ?"'),
        ('xlnx,latency = "undef"','xlnx,latency = <0x01>')]:
        assert text.count(old_value)==1
        text=text.replace(old_value,new_value)
    # Existing ZOCL consumer already uses flag 4. The CU declaration must
    # describe the same active-high level source, not the old generator's 2.
    assert text.count('interrupts = <0x01 0x02>')==1
    text=text.replace('interrupts = <0x01 0x02>','interrupts = <0x01 0x04>')
    (out/'a11-mlp.dts').write_text(text,encoding='utf-8')
    run([dtc,'-@','-I','dts','-O','dtb','-o','a11-mlp.dtbo','a11-mlp.dts'])
    base=Path('/home/member-a/a10-driver-audit-20261018/board-reconstructed.dtb')
    merged=out/'merged-PC_ONLY.dtb'
    run(['fdtoverlay','-i',base,'-o',merged,out/'a11-mlp.dtbo'])
    assert memory(base)==memory(merged)
    amba=get(merged,'/__symbols__','amba','s')
    cu=get(merged,'/__symbols__','w4a8_linear_v1_1','s')
    intc=get(merged,'/__symbols__','axi_intc_0','s')
    assert get(merged,cu,'reg')=='0 b0000000 0 10000'
    assert get(merged,cu,'interrupts')=='1 4'
    assert get(merged,cu,'xlnx,s-axi-control-addr-width')=='8'
    assert get(merged,intc,'interrupts')=='0 59 4'
    assert get(merged,intc,'xlnx,kind-of-intr')=='fffffffd'
    assert get(merged,intc,'xlnx,num-intr-inputs')=='20'
    ph=int(get(merged,intc,'phandle'),16)
    irq=[int(v,16) for v in get(merged,amba+'/zyxclmm_drm','interrupts-extended').split()]
    assert irq==[v for n in range(32) for v in (ph,n,4)]
    for name in ('#address-cells','#size-cells'):assert get(merged,amba,name)=='2'
    bit=ROOT/'release/a07_b04_v3/artifacts/MPSoC_ext_platform.bit'
    assert sha(bit)=='432d2191d72e6372285f7021ec86efc4fb7ea80005db61ab41fcf0fea2d7a517'
    shutil.copyfile(bit,out/'MLP.bit')
    (out/'bitstream_only.bif').write_text('all: { MLP.bit }\n',encoding='ascii')
    run(['/home/member-a/AMDDesignTools/2026.1/Vitis/bin/bootgen','-arch','zynqmp',
         '-process_bitstream','bin','-image','bitstream_only.bif'])
    generated=out/'MLP.bit.bin'
    assert generated.is_file() and generated.stat().st_size>7000000
    shutil.copyfile(generated,out/'a11-mlp.bit.bin')
    report=dict(status='PASS_PC_STATIC_ONLY',BOARD='NOT_TESTED',metadata_sha256=sha(meta_path),
        template_sha256=sha(old),base_sha256=sha(base),memory_and_bootargs_unchanged=True,
        firmware_name=get(merged,get(merged,'/__symbols__','fpga_full','s'),'firmware-name','s'),
        CU_address=meta['cu_address'],CU_interrupt=[1,4],groups=meta['argument_groups'],
        irq_count=32,clock_MHz=149.9985,clock_optimization=False,
        files={n:dict(bytes=(out/n).stat().st_size,sha256=sha(out/n)) for n in
               ('a11-mlp.dts','a11-mlp.dtbo','a11-mlp.bit.bin','merged-PC_ONLY.dtb')},
        limits=['cached-base compatibility only; fresh runtime DT must match before load',
                'symbol/property overlay removal advisories remain recorded limitations',
                'no board BO allocation capacity proven by metadata'])
    (out/'audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report))


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path,required=True)
    build(ap.parse_args().out.resolve())
