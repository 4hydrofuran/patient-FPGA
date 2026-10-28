"""Preserve independent-work inputs; never modifies B or previous evidence."""
import hashlib, json, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'evidence/A07_independent/preboard-v1'
OUT.mkdir(parents=True, exist_ok=False)
paths = ['AGENTS.md', 'docs/PROJECT_STATUS.json', 'docs/status/A.md',
         'docs/DESIGN_GAP.md', 'docs/TEST_MATRIX.md', 'hw/linear_A/KERNEL_SOURCE.json',
         'modules/linear_A/manifest.json', 'config/qwen35/selection.json',
         'models/model.lock.json', 'models/sidecar_A/qwen35-v1/manifest.json',
         'eval/qwen35/a05/batch-fix-v1/runtime-build-v8.json']
paths += [p.relative_to(ROOT).as_posix() for folder in ('runtime/qwen35_w4a8', 'contracts/qwen35')
          for p in (ROOT/folder).glob('*') if p.is_file()]
records = {}
for name in paths:
    source = ROOT/name
    target = OUT/'before'/name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    records[name] = hashlib.sha256(source.read_bytes()).hexdigest()
with (OUT/'inputs.sha256.json').open('x', encoding='utf-8') as f:
    json.dump(records, f, indent=2)
print(json.dumps({'preserved': len(records), 'output': str(OUT), 'BOARD': 'NOT_TESTED'}))
