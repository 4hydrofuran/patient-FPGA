"""Historical strict bridge using the current case's already-read raw ledger.

Historical originals are read once without cache advice. No other window is
ever a target of this candidate's fsync/fadvise operations.
"""
import hashlib
import json
from pathlib import Path
from tt10_01_diag_reader import DiagnosticBlocked, identity
from tt10_01_legacy_compare import fields


def compare_legacy_case(reference, actual, actual_files):
    reference, actual = Path(reference), Path(actual)
    files = {}
    manifest = None
    for p in sorted((reference / 'diag').iterdir()):
        if p.is_symlink() or not p.is_file():
            raise DiagnosticBlocked('historical diagnostic contains non-regular entry')
        before = identity(p.stat())
        h = hashlib.sha256()
        parts = []
        with p.open('rb') as f:
            for block in iter(lambda: f.read(1048576), b''):
                h.update(block)
                if p.name == 'manifest.json':
                    parts.append(block)
        if identity(p.stat()) != before:
            raise DiagnosticBlocked('historical diagnostic changed during comparison')
        files[p.name] = dict(bytes=before[2], sha256=h.hexdigest())
        if parts:
            manifest = json.loads(b''.join(parts))
    request = json.loads((actual / 'request.json').read_text())
    position = len(request['tokens']) - 1
    candidates = [x for x in manifest['logits'] if x['position'] == position and x['file'].startswith('logits-prefill-')]
    if len(candidates) != 1 or Path(candidates[0]['file']).name != candidates[0]['file']:
        raise DiagnosticBlocked('historical final prompt logits missing or ambiguous')
    leaf = candidates[0]['file']
    prompt_sha = files[leaf]['sha256']
    old_raw, new_raw = (reference / 'result.json').read_bytes(), (actual / 'result.json').read_bytes()
    result = fields(json.loads(old_raw), json.loads(new_raw), prompt_sha)
    result.update(all_original_raw_files_equal=files == actual_files, raw_file_count=len(files),
        historical_prompt_sha256_derived_from=leaf, historical_prompt_sha256=prompt_sha,
        raw_differences={k: dict(reference=files.get(k), actual=actual_files.get(k))
                         for k in files.keys() | actual_files.keys() if files.get(k) != actual_files.get(k)},
        reference_result_sha256=hashlib.sha256(old_raw).hexdigest(), actual_result_sha256=hashlib.sha256(new_raw).hexdigest())
    result['historical_comparison_pass'] = result['historical_required_fields_equal'] and result['all_original_raw_files_equal']
    return result
