"""Snapshot the narrow portable A07 dependency closure, no model/tool/license copies."""
import hashlib, json, shutil, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False)
    folders=['modules/linear_A/xrt','hw/linear_B_received/B04-scope-9a75600-20261003']
    files=[ROOT/p for p in ['contracts/qwen35/sp_linear_v1.h','hw/linear_A/KERNEL_SOURCE.json',
          'platform/qwen35/a07/test_host.cpp','platform/qwen35/a07/b04/build_portable.sh',
          'platform/qwen35/a07/b04/meta_replay.cpp']]
    for folder in folders:files.extend(p for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    received=ROOT/folders[1]
    receipt=json.loads((received/'RECEIPT.json').read_text())
    for name,item in receipt['files'].items():
        if digest(received/name)!=item['sha256']:raise ValueError('B receipt mismatch: '+name)
    for p in files:
        dest=out/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
    vendor=out/'third_party/nlohmann';vendor.mkdir(parents=True)
    shutil.copyfile('/home/member-a/qwen35-a05/source-v3/vendor/nlohmann/json.hpp',vendor/'json.hpp')
    manifest={p.relative_to(out).as_posix():{'bytes':p.stat().st_size,'sha256':digest(p)} for p in out.rglob('*') if p.is_file()}
    (out/'source_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'source_files':len(manifest),'output':str(out),'BOARD':'NOT_TESTED'}))
if __name__=='__main__':main()
