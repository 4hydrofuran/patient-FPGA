"""Reproduce cross-ISA failure and independently recompute saved real PL calls."""
import hashlib
import json
import struct
from common import ROOT,command,sha,save
from review06_common import OUT
from step06_audit import compare

def j(p):return json.loads(p.read_text(encoding='utf-8'))

def main():
    base=ROOT/'evidence/model_pl_A';old=base/'20261023-step06-v1'
    board=old/'readback-v1/run-v1/diag-teacher_T8'
    pc=base/'20261023-preboard-v1/canonical-a05-v8/diag'
    cross={p.name:compare(p.read_bytes(),(pc/p.name).read_bytes(),.002,.0002) for p in sorted(board.glob('logits-*.f32'))}
    assert len(cross)==10 and any(c['failures'] for c in cross.values())
    save(OUT/'CROSS_ISA_REPRODUCED.json',dict(status='FAIL_REPRODUCED_SAVED_INPUTS_UNCHANGED',
       domain='PC_X86_VS_BOARD_ARM_CPU_GRAPH',logits=cross,graph_atol=.002,graph_rtol=.0002,
       step08_reference_policy='MATCHED_SAME_BOARD_S1_VS_S2_REQUIRED',changed_math=False))
    manifest=j(ROOT/'models/sidecar_A/qwen35-v1/manifest.json')
    entries={e['id']:e for e in manifest['entries']};out=OUT/'independent-scalar-v1';out.mkdir()
    mlp=base/'20261024-step07-mlp-v1/readback-v1/run-v1/s2'
    real=j(mlp/'result.json')['bridge']['a12_route']['a12_trace'];cases=[]
    for origin,folder in (('ARM_CPU',board),('X86_CPU',pc)):
        m=j(folder/'manifest.json')
        for name in ('l00_gate','l00_up','l00_down','l23_down'):
            r=next(r for r in m['projections'] if r['id']==name and r['execution']==1)
            cases.append((origin,folder,r,None))
    for t in real:
        r=next(r for r in j(mlp/'diag/manifest.json')['projections'] if r['id']=='l00_'+t['op'] and r['execution']==t['execution'])
        cases.append(('BOARD_REAL_PL',mlp/'diag',r,t))
    rows=[];ref='/home/member-a/qwen35-a04/build-v1/w4ref'
    for origin,folder,r,t in cases:
        e=entries[r['id']];name=origin+'-'+r['id']+'-'+str(r['execution']);dest=out/name
        argv=[ref,'run',str(e['N']),str(e['K']),str(r['T']),
           str(ROOT/'models/sidecar_A/qwen35-v1'/e['files']['w.bin']['file']),
           str(ROOT/'models/sidecar_A/qwen35-v1'/e['files']['sw.bin']['file']),str(folder/r['input']),str(dest)]
        command(argv,out/(name+'-command.json'))
        c=compare((folder/r['output']).read_bytes(),(dest/'y.bin').read_bytes(),1e-4,1e-5)
        assert c['bit_exact'] and c['failures']==0,(name,c)
        if t:assert sha(folder/r['output'])==t['output_sha256'] and t['consumer_verified']
        rows.append(dict(origin=origin,id=r['id'],execution=r['execution'],T=r['T'],N=e['N'],K=e['K'],
            input_sha256=sha(folder/r['input']),actual_sha256=sha(folder/r['output']),
            independent_sha256=sha(dest/'y.bin'),comparison=c,job_id=t['job_id'] if t else None))
    boundary=[];index=3745
    for tag,folder in (('ARM_CPU',board),('X86_CPU',pc)):
        m=j(folder/'manifest.json');r=next(r for r in m['projections'] if r['id']=='l00_gate' and r['execution']==1)
        x=struct.unpack_from('<f',(folder/r['input']).read_bytes(),index*4)[0]
        d=out/(tag+'-l00_gate-1');sx=struct.unpack_from('<f',(d/'sx.bin').read_bytes(),12)[0]
        q=struct.unpack_from('<b',(d/'xq.bin').read_bytes(),index)[0]
        normalized=struct.unpack('<f',struct.pack('<f',x/sx))[0]
        boundary.append(dict(platform=tag,index=index,row=3,k=673,value=x,scale=sx,normalized=normalized,code=q))
    assert [r['code'] for r in boundary]==[1,2]
    save(OUT/'NUMERIC_REVIEW.json',dict(status='PASS_SAME_INPUT_INDEPENDENT_REFERENCE_CROSS_ISA_LIMITATION_RETAINED',
       comparisons=rows,boundary=boundary,reference_executable=ref,reference_sha256=sha(ref),
       original_cross_ISA='FAIL_REPRODUCED_NOT_WAIVED',same_board_S1_S2='PASS_PREVIOUS_SEALED_TASK07',
       step08_numerical_blocker=False,required_step08_reference='SAME_BOARD_ARM_BINARY_MODEL_INPUT_THREADS_SCHEDULE',
       cross_ISA_equivalence='NOT_ACCEPTED',scope_limit='First divergence localized to quantization boundary; specific upstream non-MLP instruction is not identified',
       model_math_changed=False,tolerances_changed=False,new_BOARD_kernel_runs=0))
    print(json.dumps(dict(status='PASS_17_SAME_INPUT_INDEPENDENT_SCALAR_RECOMPUTATIONS',cases=len(rows),real_PL_cases=9,boundary=boundary)))

if __name__=='__main__':main()
