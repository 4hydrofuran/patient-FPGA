"""Full logits/state digests and concatenated projection bytes, no numerical tolerance."""
from collections import defaultdict
import hashlib
from pathlib import Path
from tt10_01_common import j,sha


def same_result(a,b):
    fields=['status','output_tokens','text','eos','decode_calls','last_prompt_logits_fnv64','state_position_before_clear','state_position_after_clear','state_cleared_before_response']
    differences={k:dict(reference=a[k],actual=b[k]) for k in fields if a[k]!=b[k]}
    # Optional diagnostics must not silently disappear on one side.
    for k in ('last_prompt_logits_sha256','state_fingerprint'):
        if k in a or k in b:
            if k not in a or k not in b or a[k]!=b[k]:
                differences[k]=dict(reference=a.get(k),actual=b.get(k),reference_present=k in a,actual_present=k in b)
    return dict(equal=not differences,differences=differences)


def concatenated(reference,warm,restored):
    def collect(paths):
        projections={};logits={};count=0
        for folder in paths:
            folder=Path(folder);manifest=j(folder/'diag/manifest.json')
            for row in manifest['projections']:
                for kind in ('input','output'):
                    key=str((row['id'],kind));projections.setdefault(key,hashlib.sha256())
                    p=folder/'diag'/row[kind];assert p.stat().st_size==row['T']*row['K' if kind=='input' else 'N']*4
                    with p.open('rb') as stream:
                        for block in iter(lambda:stream.read(1048576),b''):projections[key].update(block)
                count+=1
            for row in manifest['logits']:
                assert type(row['position']) is int and row['position']>=0
                # JSON object keys are strings; keep that form before serialization.
                key=str(row['position']);assert key not in logits
                logits[key]=sha(folder/'diag'/row['file'])
        return {k:v.hexdigest() for k,v in projections.items()},logits,count
    a,al,ac=collect([reference]);b,bl,bc=collect([warm,restored])
    differences={k:[a.get(k),b.get(k)] for k in a.keys()|b.keys() if a.get(k)!=b.get(k)}
    ld={k:[al.get(k),bl.get(k)] for k in al.keys()|bl.keys() if al.get(k)!=bl.get(k)}
    state_a=sha(Path(reference)/'diag/hybrid-state.bin');state_b=sha(Path(restored)/'diag/hybrid-state.bin')
    state_equal=state_a==state_b
    return dict(equal=not differences and not ld and state_equal,projection_difference=differences,logits_difference=ld,
        prefill_state_equal=state_equal,projection_streams=len(a),full_logit_vectors=len(al),reference_projection_records=ac,actual_projection_records=bc,
        reference_projection_sha256=a,restored_projection_sha256=b,reference_logits_sha256=al,restored_logits_sha256=bl,
        reference_state_sha256=state_a,restored_state_sha256=state_b)
