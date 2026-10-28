"""Preserve cross-ISA differences separately from same-board chunk correctness."""
import json
from collections import defaultdict
from common import ROOT,save
from step06_prepare import OUT
from step06_audit import compare


if __name__=='__main__':
    board=OUT/'readback-v1/run-v1/diag-teacher_T8'
    pc=ROOT/'evidence/model_pl_A/20261023-preboard-v1/canonical-a05-v8/diag'
    logits={p.name:compare(p.read_bytes(),(pc/p.name).read_bytes(),.002,.0002) for p in sorted(board.glob('logits-*.f32'))}
    bm=json.loads((board/'manifest.json').read_text());pm=json.loads((pc/'manifest.json').read_text())
    proj={}
    for b in bm['projections']:
        p=next(p for p in pm['projections'] if p['id']==b['id'] and p['execution']==b['execution'])
        proj[b['id']+'_'+str(b['execution'])]=dict(input=compare((board/b['input']).read_bytes(),(pc/p['input']).read_bytes(),.002,.0002),
             output=compare((board/b['output']).read_bytes(),(pc/p['output']).read_bytes(),1e-4,1e-5))
    save(OUT/'CROSS_ISA_DIAGNOSTIC.json',dict(domain='PC_X86_VS_BOARD_ARM_CPU_REFERENCE_NOT_PL',logits=logits,projections=proj,
        thresholds_unchanged=True,status='CROSS_ISA_GRAPH_THRESHOLD_FAIL_RETAINED'))
    print(json.dumps(dict(logits={n:dict(max_abs=r['max_abs'],failures=r['failures']) for n,r in logits.items()},
        first_layer=[{n:r} for n,r in proj.items() if n.startswith('l00_')][:3])))
