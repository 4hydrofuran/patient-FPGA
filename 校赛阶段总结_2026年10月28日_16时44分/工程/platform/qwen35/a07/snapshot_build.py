"""Inputs receipt for each isolated A07 compile job (no model-weight copies)."""
import hashlib, json, shutil, sys
from pathlib import Path
root=Path(__file__).resolve().parents[3]
out=Path(sys.argv[1])/'inputs'
out.mkdir(exist_ok=False)
files={}
for folder in ('modules/linear_A/xrt','platform/qwen35/a07','runtime/qwen35_w4a8','contracts/qwen35','quant/reference'):
    for p in (root/folder).rglob('*'):
        if not p.is_file() or '__pycache__' in p.parts:continue
        key=p.relative_to(root).as_posix()
        dest=out/key;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
        files[key]=hashlib.sha256(p.read_bytes()).hexdigest()
with (out/'sha256.json').open('x') as f:json.dump(files,f,indent=2)
print(json.dumps({'build_inputs':len(files),'path':str(out)}))
