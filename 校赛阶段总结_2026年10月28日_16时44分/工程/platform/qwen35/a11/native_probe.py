"""ARM64 loader and activation quantization only; NEVER call sp_linear_open."""
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT=Path('/var/lib/kv260-a11/a11-mlp-20261023-v1')
PIN='3b3c46700f92565839abda962e07e557018b8fd1be9e7846613ff46ecf89f11c'


def main():
    assert len(sys.argv)==2 and os.geteuid()==0
    assert not ROOT.is_symlink() and ROOT.stat().st_uid==0 and not ROOT.stat().st_mode&0o022
    assert hashlib.sha256((ROOT/'manifest.json').read_bytes()).hexdigest()==PIN
    sys.path.insert(0,str(ROOT))
    from mlp_policy import verify_bundle,digest,trusted_file,LIBRARIES,KERNEL,MACHINE,need
    need(os.uname().release==KERNEL and os.uname().machine=='aarch64' and digest('/etc/machine-id')==MACHINE,'wrong platform')
    need(Path('/proc/sys/kernel/random/boot_id').read_text().strip()==sys.argv[1],'boot changed')
    need(not Path('/sys/module/zocl').exists() and not os.path.lexists('/var/lock/kv260-a1/active'),'active device/lease')
    manifest=verify_bundle(ROOT,PIN)
    for name in manifest['files']:trusted_file(ROOT/name)
    for name,pin in LIBRARIES.items():need(digest(name)==pin,'runtime library differs')
    from mlp_engine import NativeAPI
    start=time.monotonic_ns();api=NativeAPI(ROOT);loaded=time.monotonic_ns()
    plan=json.loads((ROOT/'vectors/manifest.json').read_text());results=[]
    for name in ('hand_T1','l00_gate_T8'):
        case=plan['cases'][name];folder=ROOT/'vectors/inputs'/name
        raw=(folder/'x.f32').read_bytes();x=C.create_string_buffer(raw,len(raw))
        qbytes=case['T']*((case['K']+127)//128*128);sbytes=case['T']*4
        q=C.create_string_buffer(qbytes);s=C.create_string_buffer(sbytes)
        rc=api.quantize(case['N'],case['K'],case['T'],x,len(raw),q,qbytes,s,sbytes)
        need(rc==0 and q.raw==(folder/'xq.bin').read_bytes() and s.raw==(folder/'sx.bin').read_bytes(),'quantization mismatch')
        results.append(dict(case=name,exit_code=rc,byte_exact=True))
    maps=[l for l in Path('/proc/self/maps').read_text().splitlines() if 'libxrt_' in l or 'libsp_linear' in l or 'liba11_quant' in l]
    need(not Path('/sys/module/zocl').exists(),'unexpected module')
    print(json.dumps(dict(status='ARM64_LOADER_QUANT_ONLY_PASSED',boot_id=sys.argv[1],
        loader_ms=(loaded-start)/1e6,total_ms=(time.monotonic_ns()-start)/1e6,results=results,
        native_mappings=maps,fpga_open_calls=0,bo_allocations=0,compute_runs=0)))


if __name__=='__main__':main()
