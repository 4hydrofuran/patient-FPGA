"""Exact same-ISA diagnostic comparison, including every dumped MLP projection."""
import hashlib
import json
from pathlib import Path


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def compare_cases(reference, actual):
    reference, actual = Path(reference), Path(actual)
    a = json.loads((reference/'result.json').read_text(encoding='utf-8'))
    b = json.loads((actual/'result.json').read_text(encoding='utf-8'))
    for key in ('output_tokens','text','eos','decode_calls','last_prompt_logits_fnv64','state_fingerprint',
                'prefill_requested_logits','state_position_before_clear','state_position_after_clear','state_cleared_before_response'):
        assert a[key] == b[key], ('same-ISA result mismatch', key)
    assert a['state_fingerprint'] is not None
    am = json.loads((reference/'diag/manifest.json').read_text(encoding='utf-8'))
    bm = json.loads((actual/'diag/manifest.json').read_text(encoding='utf-8'))
    assert am == bm, 'diagnostic manifests differ'
    ap = {p.name:sha(p) for p in (reference/'diag').iterdir() if p.is_file() and p.name != 'manifest.json'}
    bp = {p.name:sha(p) for p in (actual/'diag').iterdir() if p.is_file() and p.name != 'manifest.json'}
    assert ap == bp, 'projection/logits/hybrid state bytes differ'
    assert 'hybrid-state.bin' in ap and len(am['projections']) >= 144
    assert len(am['logits']) == 10
    return dict(status='BIT_EXACT', files=len(ap), projections=len(am['projections']),
                logits=len(am['logits']), prefill_hybrid_state_sha256=ap['hybrid-state.bin'],
                final_hybrid_state_fingerprint=a['state_fingerprint'])
