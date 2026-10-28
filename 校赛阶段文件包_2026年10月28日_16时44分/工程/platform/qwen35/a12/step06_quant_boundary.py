"""Pin the first cross-ISA quantization boundary counterexample without changing math."""
import json
import struct
from common import ROOT,save
from step06_prepare import OUT


def f32(x):return struct.unpack('<f',struct.pack('<f',x))[0]


if __name__=='__main__':
    b=OUT/'readback-v1/run-v1/diag-teacher_T8'
    p=ROOT/'evidence/model_pl_A/20261023-preboard-v1/canonical-a05-v8/diag'
    bm=json.loads((b/'manifest.json').read_text());pm=json.loads((p/'manifest.json').read_text())
    index=3745;rows=[]
    for tag,folder,manifest in (('ARM_BOARD',b,bm),('X86_PC',p,pm)):
        record=next(r for r in manifest['projections'] if r['id']=='l00_gate' and r['execution']==1)
        values=(folder/record['input']).read_bytes();value=struct.unpack_from('<f',values,index*4)[0]
        scale=struct.unpack_from('<f',(OUT/'same-input-v1/l00_gate'/('board' if tag=='ARM_BOARD' else 'pc')/'sx.bin').read_bytes(),3*4)[0]
        q=struct.unpack_from('<b',(OUT/'same-input-v1/l00_gate'/('board' if tag=='ARM_BOARD' else 'pc')/'xq.bin').read_bytes(),index)[0]
        rows.append(dict(platform=tag,index=index,token_row=3,k_index=673,input=value,scale=scale,normalized=f32(value/scale),code=q))
    assert rows[0]['code']!=rows[1]['code']
    save(OUT/'MINIMAL_CROSS_ISA_COUNTEREXAMPLE.json',dict(status='LOCATED_INPUT_ROUNDING_TO_A8_BOUNDARY',values=rows,
        same_input_operator_reference='SAME_INPUT_REFERENCE.json',math_changed=False,thresholds_relaxed=False,
        note='Non-MLP input differs before W4A8 hook. Each captured input independently reproduces its own CPU output exactly; whole-graph PC/ARM parity remains FAIL.'))
    print(json.dumps(rows))
