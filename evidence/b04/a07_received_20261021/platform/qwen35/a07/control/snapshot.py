import hashlib,json,shutil,sys
from pathlib import Path
R=Path(__file__).resolve().parents[4];out=Path(sys.argv[1])
shutil.copytree(R/'platform/qwen35/a07/control',out/'platform/qwen35/a07/control',ignore=shutil.ignore_patterns('__pycache__'))
manifest={p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in out.rglob('*') if p.is_file()}
(out/'control-build-inputs.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'snapshot_files':len(manifest),'root':str(out)}))
