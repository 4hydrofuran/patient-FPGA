"""PC ELF/ABI/build-guard checks; no native model, hardware or cross build."""
import json
from pathlib import Path
import subprocess
from native_cpu_build import ROOT,OUT,read,save,sha


def main():
    build=read(OUT/'BUILD-v2.json');work=Path(build['workspace']);library=Path(build['library'])
    assert sha(library)==build['library_sha256']
    rows=[]
    def command(argv,**kwargs):
        r=subprocess.run(argv,capture_output=True,text=True,**kwargs)
        rows.append(dict(argv=argv,exit_code=r.returncode));return r
    symbols=command(['nm','-D','--defined-only',str(library)])
    assert symbols.returncode==0
    public=sorted(line.split()[-1] for line in symbols.stdout.splitlines() if line.split()[-1].startswith('sp_linear_'))
    assert public==sorted('sp_linear_'+name+'_v1' for name in ('open','load','run','report','unload','close'))
    header=command(['readelf','-h',str(library)]);dynamic=command(['readelf','-d',str(library)])
    assert header.returncode==dynamic.returncode==0 and 'X86-64' in header.stdout
    assert all(name not in dynamic.stdout.lower() for name in ('xrt','zocl','xilinx'))
    includes=[arg for arg in build['command'] if arg.startswith('-I')]
    guard=subprocess.run(['g++','-E','-DSP_A12_PC_TEST=1','-U__x86_64__','-D__aarch64__',*includes,
        str(work/'source/native_cpu_control.cpp')],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True)
    assert guard.returncode!=0 and 'x86_64 PC-test-only adapter' in guard.stderr
    save(OUT/'ARTIFACT_AUDIT.json',dict(status='PASS_PC_ELF_PUBLIC_SYMBOLS_AND_NEGATIVE_PREPROCESS_GUARD',
        domain='PC_STATIC_NOT_ARM_BUILD',commands=rows,public_symbols=public,header=header.stdout,
        dynamic=dynamic.stdout,negative_preprocess_exit=guard.returncode,negative_preprocess_stderr=guard.stderr,
        adapter_sha256=sha(library),CPU_math_rebuilt=False,ARM_cross_build='NOT_PERFORMED',BOARD='NOT_TESTED'))
    print(json.dumps(dict(status='PASS_PC_ARTIFACT_REVIEW',public_ABI_symbols=len(public),device_dependencies=0,
        ARM_cross_build='NOT_PERFORMED',BOARD='NOT_TESTED')))


if __name__=='__main__':main()
