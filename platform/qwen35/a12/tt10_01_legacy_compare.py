"""Schema-bound old R0 comparison; never invent an absent terminal-state SHA.

New/new cache comparisons continue to use unchanged strict same_result().
This bridge requires every historical field and every original diagnostic byte.
"""
import hashlib,json,re
from pathlib import Path
FIELDS=('status','output_tokens','text','eos','decode_calls','last_prompt_logits_fnv64',
        'state_position_before_clear','state_position_after_clear','state_cleared_before_response')
def j(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for block in iter(lambda:f.read(1048576),b''):h.update(block)
    return h.hexdigest()
def fields(reference,actual,prompt_sha):
    diffs={k:dict(reference=reference.get(k),actual=actual.get(k)) for k in FIELDS if k not in reference or k not in actual or reference[k]!=actual[k]}
    a=reference.get('state_fingerprint');b=actual.get('state_fingerprint')
    if not isinstance(a,dict) or not isinstance(b,dict) or not {'bytes','fnv64'}<=a.keys() or not {'bytes','fnv64','sha256'}<=b.keys():
        diffs['state_fingerprint']='Required original size/FNV or new SHA missing'
    else:
        for k,v in a.items():
            if k not in b or b[k]!=v:diffs['state_fingerprint.'+k]=dict(reference=v,actual=b.get(k))
        if b.keys()-a.keys()-{'sha256'}:diffs['state_fingerprint.schema']='Unexpected additional field'
        if not isinstance(b['sha256'],str) or not re.fullmatch('[0-9a-f]{64}',b['sha256']):diffs['actual_terminal_sha']='Malformed'
    if actual.get('last_prompt_logits_sha256')!=prompt_sha:diffs['last_prompt_logits_sha256']='Does not match historical raw final-prompt logits'
    if 'last_prompt_logits_sha256' in reference and reference['last_prompt_logits_sha256']!=prompt_sha:
        diffs['reference_last_prompt_logits_sha256']='Historical metadata differs from its raw bytes'
    return dict(historical_required_fields_equal=not diffs,differences=diffs,
        historical_final_state_sha256='PRESENT_AND_COMPARED' if isinstance(a,dict) and 'sha256' in a else 'NOT_AVAILABLE_NO_HISTORICAL_TERMINAL_BYTES',
        new_terminal_state_sha256=b.get('sha256') if isinstance(b,dict) else None,
        terminal_sha_equality_claimed=isinstance(a,dict) and 'sha256' in a,
        old_terminal_size_and_FNV_preserved=True,new_new_cache_comparison_unchanged=True)
def compare_legacy_case(reference,actual):
    reference=Path(reference);actual=Path(actual)
    # Exact filename set and streaming bytes; no tolerance or missing-file exemption.
    a={p.name:dict(bytes=p.stat().st_size,sha256=sha(p)) for p in (reference/'diag').iterdir() if p.is_file()}
    b={p.name:dict(bytes=p.stat().st_size,sha256=sha(p)) for p in (actual/'diag').iterdir() if p.is_file()}
    manifest=j(reference/'diag/manifest.json');request=j(actual/'request.json')
    position=len(request['tokens'])-1
    candidates=[x for x in manifest['logits'] if x['position']==position and x['file'].startswith('logits-prefill-')]
    assert len(candidates)==1,'Historical last-prompt logits ambiguous or absent'
    leaf=candidates[0]['file'];assert Path(leaf).name==leaf
    prompt_sha=sha(reference/'diag'/leaf)
    result=fields(j(reference/'result.json'),j(actual/'result.json'),prompt_sha)
    result.update(all_original_raw_files_equal=a==b,raw_file_count=len(a),historical_prompt_sha256_derived_from=leaf,
        historical_prompt_sha256=prompt_sha,raw_differences={k:dict(reference=a.get(k),actual=b.get(k)) for k in a.keys()|b.keys() if a.get(k)!=b.get(k)},
        reference_result_sha256=sha(reference/'result.json'),actual_result_sha256=sha(actual/'result.json'))
    result['historical_comparison_pass']=result['historical_required_fields_equal'] and result['all_original_raw_files_equal']
    return result
