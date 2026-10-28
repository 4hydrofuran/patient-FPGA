"""Locate cross-ISA input quantization changes using preserved independent A04 scalar."""
import json
from pathlib import Path
from common import ROOT,command,save
from step06_prepare import OUT
from step06_audit import compare


if __name__=='__main__':
    out=OUT/'same-input-v1';out.mkdir(exist_ok=False)
    board=OUT/'readback-v1/run-v1/diag-teacher_T8'
    pc=ROOT/'evidence/model_pl_A/20261023-preboard-v1/canonical-a05-v8/diag'
    bm=json.loads((board/'manifest.json').read_text());pm=json.loads((pc/'manifest.json').read_text())
    entries={e['id']:e for e in json.loads((ROOT/'models/sidecar_A/qwen35-v1/manifest.json').read_text())['entries']}
    rows=[]
    for identifier in ('l00_gate','l00_up','l00_down','l23_down'):
        e=entries[identifier];b=next(p for p in bm['projections'] if p['id']==identifier and p['execution']==1)
        p=next(p for p in pm['projections'] if p['id']==identifier and p['execution']==1)
        case=out/identifier;case.mkdir()
        for tag,folder,record in (('board',board,b),('pc',pc,p)):
            target=case/tag
            argv=['/home/member-a/qwen35-a04/build-v1/w4ref','run',str(e['N']),str(e['K']),str(record['T']),
                str(ROOT/'models/sidecar_A/qwen35-v1'/e['files']['w.bin']['file']),
                str(ROOT/'models/sidecar_A/qwen35-v1'/e['files']['sw.bin']['file']),
                str(folder/record['input']),str(target)]
            command(argv,case/(tag+'-command.json'))
            original=(folder/record['output']).read_bytes();golden=(target/'y.bin').read_bytes()
            result=compare(original,golden,1e-4,1e-5)
            assert result['failures']==0,(identifier,tag,result)
            rows.append(dict(id=identifier,input_origin=tag,scalar_same_input=result))
        q1=(case/'board/xq.bin').read_bytes();q2=(case/'pc/xq.bin').read_bytes()
        mismatches=[i for i,(u,v) in enumerate(zip(q1,q2)) if u!=v]
        save(case/'QUANTIZATION_DIFFERENCE.json',dict(id=identifier,quantized_input_mismatches=len(mismatches),
            first_mismatches=mismatches[:16],board_input_max_error=compare((board/b['input']).read_bytes(),(pc/p['input']).read_bytes(),.002,.0002)['max_abs']))
    save(OUT/'SAME_INPUT_REFERENCE.json',dict(status='PASS_CAPTURED_ARM_AND_PC_SAME_INPUT_VS_A04_SCALAR',comparisons=rows,
        cross_ISA_graph='FAIL_RETAINED_DIFFERENT_INPUTS_ENTER_QUANTIZER',tolerances_unchanged=True,
        not_PL_validation=True))
    print(json.dumps(dict(status='PASS_CAPTURED_ARM_AND_PC_SAME_INPUT_VS_A04_SCALAR',comparisons=len(rows))))
