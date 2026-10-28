"""Build only the independent PC read-only gate observer with existing g++."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
from mode_evidence import ROOT,OUT,PARENT,WORK,read,save,sha

p=argparse.ArgumentParser();p.add_argument('--revision',type=int,default=1);args=p.parse_args()
work=WORK.with_name(WORK.name[:-1]+str(args.revision))
assert os.name=='posix';os.umask(0o077);work.mkdir(mode=0o700,exist_ok=False)
source=work/'source';source.mkdir()
build=read(PARENT/'BUILD-v5-reviewed.json');parent=Path(build['workspace'])/'source'
for name,path in [('mode_page_reader.cpp',ROOT/'platform/qwen35/a12/mode_page_reader.cpp'),
        ('prefix_cache.hpp',parent/'prefix_cache.hpp')]:shutil.copyfile(path,source/name)
# Keep the exact shared layout/atomic reader helpers. Remove all private writer
# exports from this derived observer; the frozen parent header stays unchanged.
guard=(parent/'microbatch_guard.hpp').read_text();assert guard.count('#define MB_EXPORT')==1
(source/'microbatch_guard_read_layout.hpp').write_text(guard.split('#define MB_EXPORT')[0])
prior=read(ROOT/'evidence/model_pl_A/20261024-step10-v1/BUILD-v1.json')
include=Path(prior['workspace'])/'llama-source/vendor/nlohmann';library=work/'liba12_mode_page_reader.so'
argv=['g++','-std=c++17','-O2','-fPIC','-shared','-fvisibility=hidden','-DSP_A12_PC_TEST=1',
    '-Wall','-Wextra','-I'+str(source),'-I'+str(include),str(source/'mode_page_reader.cpp'),
    '-o',str(library),'-l:libcrypto.so.3']
r=subprocess.run(argv,capture_output=True,text=True)
(OUT/('reader-build-'+str(args.revision)+'.stdout')).write_text(r.stdout);(OUT/('reader-build-'+str(args.revision)+'.stderr')).write_text(r.stderr)
report=dict(status='PASS_PC_READ_ONLY_OBSERVER_BUILD' if r.returncode==0 else 'FAIL',command=argv,exit_code=r.returncode,
    workspace=str(work),library=str(library),source=[dict(name=p.name,sha256=sha(p)) for p in sorted(source.iterdir())],
    BOARD='NOT_TESTED',CPU_math_rebuilt=False,native_rebuilt=False)
if r.returncode==0:report['library_sha256']=sha(library)
save(OUT/('READER_BUILD-v'+str(args.revision)+'.json'),report);raise SystemExit(r.returncode)
