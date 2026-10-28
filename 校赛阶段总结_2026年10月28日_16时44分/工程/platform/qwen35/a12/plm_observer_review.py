"""Hide weak STL exports in a NEW observer artifact, leaving old binaries untouched."""
from pathlib import Path
import subprocess
from plm_evidence import OUT,read,save,sha
from plm_build import run
def main():
    b=read(OUT/'BUILD-v4.json');w=Path(b['workspace']);mapping=w/'observer-exports-v2.map'
    mapping.write_text('{ global: a12_plm_observe_fd_v1; local: *; };\n')
    library=w/'libplm_observer_ro_v2.so';src=w/'source'
    run(['g++','-std=c++17','-O2','-Wall','-Wextra','-Werror','-shared','-fPIC','-fvisibility=hidden','-I'+str(src),src/'plm_observer.cpp',
        '-Wl,--version-script='+str(mapping),'-Wl,-z,defs','-o',library],'OBSERVER_EXPORT_FIX-v2',w)
    cmd=['nm','-D','--defined-only',str(library)];r=subprocess.run(cmd,capture_output=True,text=True);assert r.returncode==0
    assert {line.split()[-1] for line in r.stdout.splitlines()}=={'a12_plm_observe_fd_v1'}
    save(OUT/'OBSERVER_REVIEWED-v2.json',dict(status='PASS_EXACT_RO_OBSERVER_EXPORT',library=str(library),sha256=sha(library),
        original_library=b['observer_library'],original_sha256=sha(b['observer_library']),command=cmd,exit_code=r.returncode,stdout=r.stdout,stderr=r.stderr,
        source_sha256=sha(src/'plm_observer.cpp'),export_map_sha256=sha(mapping),no_writer_exports=True,BOARD='NOT_TESTED'))
    print('PASS_EXACT_RO_OBSERVER_EXPORT')
if __name__=='__main__':main()
