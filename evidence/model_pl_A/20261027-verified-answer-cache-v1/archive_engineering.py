"""Archive the scoped engineering increment and the actual PC evidence."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[3]
EV = Path(__file__).resolve().parent
RELEASE = ROOT / 'release/a12_verified_answer_cache_20261027'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


assert read(EV / 'FINAL_REVIEW.json')['status'] == 'PASS_ALL_REQUIRED_NO_BOARD_CACHE_WORK'
assert read(EV / 'finalize-command/COMMAND.json')['exit_code'] == 0
paths = set()
for row in read(EV / 'IMPLEMENTED_SOURCE_PINS.json'):
    path = ROOT / row['path']
    assert path.is_file() and digest(path.read_bytes()) == row['sha256'], path
    paths.add(path)
for relative in (
    'docs/A12_FAST_RESPONSE_EXECUTION_PLAN_20261027.md',
    'docs/A12_VERIFIED_ANSWER_CACHE_10H_PLAN_20261027.md',
    'docs/PROJECT_STATUS.json', 'docs/DESIGN_GAP.md', 'docs/DECISIONS.md',
    'docs/TEST_MATRIX.md', 'docs/AI_ASSISTANCE.md',
    'docs/handoffs/A_A12_VERIFIED_ANSWER_CACHE_NOBOARD_20261027.md',
    'system_qwen35/app/native_pl.py',
):
    path = ROOT / relative
    assert path.is_file(), relative
    paths.add(path)
for name in ('START_HERE.md', 'ARCHIVE.json', 'CHANGES.json'):
    paths.add(RELEASE / name)

# Only generated evidence and command files, without any browser profile tree.
# The three nested data directories contain synthetic-case receipts and model proofs.
allowed_suffixes = {'.json', '.jsonl', '.csv', '.txt', '.log', '.md', '.py', '.png'}
allowed_nested = {'worker', 'consultations', 'proof'}
for path in EV.rglob('*'):
    if not path.is_file() or path.suffix not in allowed_suffixes:
        continue
    rel = path.relative_to(EV)
    if rel.parts[0] == 'archive-engineering-command':
        continue
    if len(rel.parts) > 2 and not (len(rel.parts) == 3 and rel.parts[1] in allowed_nested):
        continue
    paths.add(path)

rows = []
for path in sorted(paths):
    assert not path.is_symlink()
    relative = path.relative_to(ROOT).as_posix()
    data = path.read_bytes()
    rows.append(dict(path=relative, bytes=len(data), sha256=digest(data)))
manifest = dict(
    schema='a12-engineering-increment.v1',
    scope='Existing C:/Patientqwen overlay: owned sources, tests, docs and actual PC evidence',
    parent_product='release/a12_fast_response_20261027_v2/short34-threads2',
    product_archive=read(RELEASE / 'ARCHIVE.json'),
    files=rows,
    model_weights_included=False,
    authorization_included=False,
    BOARD='NOT_TESTED',
)
save(RELEASE / 'ENGINEERING_MANIFEST.json', manifest)
manifest_data = (RELEASE / 'ENGINEERING_MANIFEST.json').read_bytes()
archive = RELEASE / 'a12-verified-answer-cache-engineering.zip'
with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as handle:
    for row in rows:
        handle.write(ROOT / row['path'], row['path'])
    handle.writestr('ENGINEERING_MANIFEST.json', manifest_data)
with zipfile.ZipFile(archive) as handle:
    assert handle.testzip() is None
    assert len(handle.namelist()) == len(rows) + 1
    for row in rows:
        data = handle.read(row['path'])
        assert len(data) == row['bytes'] and digest(data) == row['sha256'], row['path']
    assert handle.read('ENGINEERING_MANIFEST.json') == manifest_data
result = dict(
    status='PASS_ENGINEERING_ZIP_CRC_SHA_READBACK',
    path=archive.relative_to(ROOT).as_posix(), bytes=archive.stat().st_size,
    sha256=digest(archive.read_bytes()), verified_payload_files=len(rows),
    manifest_sha256=digest(manifest_data), model_weights_included=False,
    authorization_included=False, BOARD='NOT_TESTED',
)
save(RELEASE / 'ENGINEERING_ARCHIVE.json', result)
print(json.dumps(result, indent=2))
