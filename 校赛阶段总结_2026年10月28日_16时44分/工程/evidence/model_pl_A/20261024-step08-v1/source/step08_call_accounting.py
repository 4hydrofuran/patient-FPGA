"""Check actual per-case completions for the pinned final-logits graph."""
import json
import math
from common import sha,save
from step08_common import OUT
def j(p):return json.loads(p.read_text(encoding='utf-8'))

if __name__=='__main__':
    audit=j(OUT/'GENERATION_AUDIT.json');assert audit['status']=='PASS_BOARD_ALL_FROZEN_DEV_PAIRED_GENERATION'
    root=OUT/'generation/readback-v1/run-v1';requests=j(OUT/'TOKENIZED_REQUESTS.json')['generation']
    rows=[];previous=0
    for req in requests:
        a=j(root/'s1'/req['id']/'result.json');b=j(root/'s2'/req['id']/'result.json')
        assert a['decode_calls']==b['decode_calls'] and a['prefill_requested_logits']==b['prefill_requested_logits']==1
        assert a['physical_ubatch']==b['physical_ubatch']==8 and a['prompt_tokens']==b['prompt_tokens']==len(req['tokens'])
        assert a['logits_mode']==b['logits_mode']=='final' and a['prefill_chunk']==b['prefill_chunk']==256
        microbatches=math.ceil(len(req['tokens'])/8)
        # This pinned runtime leaves embeddings_nextn_masked disabled. Output
        # row selection is after final norm: all24MLPs remain in each prefill
        # microbatch, while only one final LM-head logits row is requested.
        prefill=24*3*microbatches
        expected=prefill+72*b['decode_calls']
        cumulative=b['bridge']['a12_route']['host_verified_completions'];actual=cumulative-previous
        assert actual==expected,(req['id'],actual,expected)
        rows.append(dict(id=req['id'],prompt_tokens=len(req['tokens']),physical_prefill_microbatches=microbatches,
            prefill_calls=prefill,decode_calls=b['decode_calls'],decode_projection_calls=72*b['decode_calls'],
            actual_projection_calls=actual,cumulative_completions=cumulative,output_tokens=len(b['output_tokens']),EOS=b['eos']))
        previous=cumulative
    assert previous==audit['actual_calls']
    save(OUT/'GENERATION_CALL_ACCOUNTING.json',dict(status='PASS_ACTUAL_COUNTS_MATCH_PINNED_FINAL_LOGITS_GRAPH',
        rows=rows,actual_calls=previous,source_sha256=sha(__file__),
        scope='Normal aggregate scheduling check; final output selection after MLP/norm, no omitted last-layer MLP calls claimed. Diagnostic216 separately proves per-layer/Y/consumer coverage.',
        hardware_global_counter=None))
    print(json.dumps(dict(status='PASS_NORMAL_FINAL_LOGITS_CALL_ACCOUNTING',actual_calls=previous,requests=len(rows))))
