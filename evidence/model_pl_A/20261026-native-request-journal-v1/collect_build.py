"""Copy tiny reviewed PC build products, never model weights or old raw dumps."""
import json
from pathlib import Path
import shutil
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'platform/qwen35/a12'))
from native_cpu_build import read,save,sha
OUT=Path(__file__).resolve().parent
build=read(OUT/'BUILD-v2.json');work=Path(build['workspace']);dest=OUT/'pc-build';dest.mkdir(exist_ok=False)
files=[Path(build['library']),work/'source/native_cpu_control.cpp',work/'source/sp_linear_v1.h',work/'source/prefix_cache.hpp']
assert sha(files[-1])==sha(ROOT/'evidence/model_pl_A/20261024-ttft10-01-v1/source-04/prefix_cache.hpp')
assert sha(files[-2])==sha(ROOT/'contracts/qwen35/sp_linear_v1.h')
rows=[]
for source in files:
    target=dest/source.name;shutil.copyfile(source,target);assert sha(target)==sha(source)
    rows.append(dict(name=target.name,bytes=target.stat().st_size,sha256=sha(target)))
save(OUT/'COLLECTED_BUILD.json',dict(status='COPIED_REVIEWED_PC_BUILD_ONLY',files=rows,
    inherited_prefix_header_unchanged=True,public_ABI_header_unchanged=True,weights_copied=False,BOARD='NOT_TESTED'))
print(json.dumps(dict(status='PASS_PC_BUILD_COPY_HASHES',files=len(rows),weights_copied=False,BOARD='NOT_TESTED')))
