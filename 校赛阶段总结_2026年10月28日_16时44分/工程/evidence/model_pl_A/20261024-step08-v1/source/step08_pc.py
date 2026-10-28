"""Actual full PC graph/consumer regression and pinned development tokenization."""
import json
import os
from pathlib import Path
import time
from common import ROOT,sha,save
from step08_common import OUT
from test_graph import one
from supervisor import OwnedWorker

def j(p):return json.loads(p.read_text(encoding='utf-8'))

if __name__=='__main__':
    binary=Path(j(ROOT/'evidence/model_pl_A/20261023-step07-single-v1/BUILD.json')['pc'])
    dest=OUT/'pc-graph-v1';dest.mkdir()
    s1=one(binary,dest/'s1',None);s2=one(binary,dest/'all','all')
    assert s1['logits']==s2['logits'] and s1['state']==s2['state']
    assert s2['trace_calls']==216 and s2['trace_layers']==list(range(24))
    bad=one(binary,dest/'discarded-y','all',fault=True)
    save(OUT/'PC_GRAPH.json',dict(status='PASS_PC_ALL_24_LAYERS_216_CONSUMED_OUTPUTS_AND_DISCARD_REJECTION',
       runs=[s1,s2,bad],binary_sha256=sha(binary),BOARD='NOT_TESTED'))
    env=os.environ.copy();env.pop('SP_A12_CONFIG',None);env.pop('SP_A12_TEST_DROP_OUTPUT',None)
    worker=OwnedWorker([str(binary),str(ROOT/'artifacts/qwen35-0.8b/qwen35-text-Q4_K_M.gguf'),'2','1024','all','TILED','2','8'],
       directory=OUT/'tokenize-worker',env=env,health=lambda:None,max_runs=1,max_loads=1,expires=time.monotonic()+120)
    ready=worker.get(60);assert ready['type']=='ready';rows=[]
    try:
        for r in j(OUT/'REQUESTS.json')['generation']:
            worker.send(dict(id=r['id'],op='tokenize',prompt=r['prompt']))
            tokens=worker.get(10);assert tokens['type']=='tokens' and tokens['id']==r['id']
            assert 0<len(tokens['tokens'])<=128
            rows.append(dict(r,tokens=tokens['tokens']))
    finally:assert worker.close(timeout=10)
    save(OUT/'TOKENIZED_REQUESTS.json',dict(status='PINNED_PC_TOKENIZATION_RECHECK_ON_BOARD_BEFORE_GENERATE',
       binary_sha256=sha(binary),generation=rows,token_lengths={r['id']:len(r['tokens']) for r in rows},
       tokenizer_model_sha256=sha(ROOT/'artifacts/qwen35-0.8b/qwen35-text-Q4_K_M.gguf')))
    print('PASS_PC_FULL_GRAPH_REJECTION_AND_17_DEVELOPMENT_PROMPTS_TOKENIZED')
