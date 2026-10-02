"""Read ARM wheel ELF headers/metadata only; never execute target binaries."""
import hashlib
import json
from pathlib import Path
import re
import struct
import zipfile

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'evidence/c04/arm'


def main():
    wheels=json.loads((OUT/'wheels.lock.json').read_text('utf-8'))
    inspected=[]
    for row in wheels:
        p=OUT/row['filename']; assert hashlib.sha256(p.read_bytes()).hexdigest()==row['sha256']
        libraries=[]
        with zipfile.ZipFile(p) as archive:
            licenses=[name for name in archive.namelist() if '.dist-info/licenses/' in name or name.endswith(('LICENSE','LICENSE.txt'))]
            for name in archive.namelist():
                if '.so' not in Path(name).name:continue
                data=archive.read(name)
                if data[:4]!=b'\x7fELF':continue
                machine=struct.unpack_from('<H',data,18)[0]
                assert data[4]==2 and data[5]==1 and machine==183, 'Require 64-bit little-endian AArch64 ELF'
                versions=sorted(set(x.decode() for x in re.findall(rb'GLIBC_[0-9]+\.[0-9]+',data)))
                libraries.append(dict(path=name,sha256=hashlib.sha256(data).hexdigest(),elf_class=64,
                    elf_machine=machine,architecture='AARCH64',glibc_symbol_strings=versions,
                    isa_execution_compatibility='NOT_TESTED'))
        inspected.append(dict(wheel=row['filename'],libraries=libraries,embedded_license_paths=licenses))
    report=dict(status='PASS_STATIC_ARM_WHEEL_INSPECTION',target='KV260 Cortex-A53',
        target_isa='ARMv8-A with Advanced SIMD/NEON; do not assume SVE, dot-product, ARMv8.1 LSE',
        python='CPython 3.12',os='GNU/Linux aarch64',wheel_tag_glibc_floor='2.27 (NumPy); 2.17 (sherpa)',
        rootfs_version=None,actual_board_glibc=None,actual_cpu_features=None,
        cross_build='NOT_PERFORMED_PREBUILT_WHEELS_ONLY',native_import='NOT_TESTED',board='NOT_TESTED',
        a53_binary_isa_compatibility='NOT_VERIFIED_BY_HEADER_INSPECTION',wheels=inspected,
        sources=['https://pypi.org/project/numpy/2.5.3/',
                 'https://pypi.org/project/sherpa-onnx/1.13.8/',
                 'https://pypi.org/project/sherpa-onnx-core/1.13.8/',
                 'https://k2-fsa.github.io/sherpa/onnx/install/aarch64-embedded-linux.html'])
    (OUT/'inspection.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print('ARM wheels hash and 64-bit AARCH64 ELF headers verified; native execution and A53 ISA compatibility untested.')


if __name__=='__main__':main()
