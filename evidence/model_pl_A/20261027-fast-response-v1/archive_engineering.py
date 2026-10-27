"""Package the explicit source increment and bounded final evidence, never the workspace."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[3];EV=Path(__file__).resolve().parent
RELEASE=ROOT/'release/a12_fast_response_20261027_v2'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
paths={ROOT/r['path'] for r in read(EV/'IMPLEMENTED_SOURCE_PINS.json')}
paths.update(ROOT/p for p in ['docs/PROJECT_STATUS.json','docs/DESIGN_GAP.md','docs/TEST_MATRIX.md','docs/AI_ASSISTANCE.md',
    'docs/handoffs/A_A12_FAST_RESPONSE_NOBOARD_20261027.md','docs/A12_FAST_RESPONSE_EXECUTION_PLAN_20261027.md'])
paths.update(p for p in EV.iterdir() if p.is_file() and p.suffix in ('.md','.json','.py') and p.name!='WORKTREE_BEFORE.txt')
paths.update(p for p in (EV/'release-model').glob('*.json'))
review=read(EV/'FINAL_REVIEW.json')
for name in review['commands']:
    paths.update((EV/name/p) for p in ('COMMAND.json','stdout.txt','stderr.txt'))
paths.update((EV/'attempt01/BASE_CHECKS.json',EV/'attempt01/check_contracts.log',EV/'attempt01/qwen35_config.log'))
paths.update((EV/'attempt06-browser/RESULT.json',RELEASE/'START_HERE.md',RELEASE/'PC_ENVIRONMENT.json',RELEASE/'ARCHIVES.json'))
pins=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(paths)]
save_path=RELEASE/'engineering-increment.zip'
with zipfile.ZipFile(save_path,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for row in pins:z.write(ROOT/row['path'],row['path'])
with zipfile.ZipFile(save_path) as z:
    for row in pins:
        data=z.read(row['path'])
        assert len(data)==row['bytes'] and hashlib.sha256(data).hexdigest()==row['sha256']
record=dict(path=save_path.relative_to(ROOT).as_posix(),bytes=save_path.stat().st_size,sha256=sha(save_path),
    status='CRC_AND_SHA_READBACK_PASS',files=pins,model_weights_included=False,board_contacted=False)
(RELEASE/'ENGINEERING_ARCHIVE.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in record.items() if k!='files'},indent=2))
