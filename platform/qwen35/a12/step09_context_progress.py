"""Record the launched default-context window; retain earlier progress receipt."""
import json
from common import ROOT,save
from step09_common import OUT

if __name__=='__main__':
    assert json.loads((OUT/'context/launch_01/receipt.json').read_text())['exit_code']==0
    p=ROOT/'docs/PROJECT_STATUS.json';status=json.loads(p.read_text(encoding='utf-8'))
    row=status['a12_step09_state_cancel_20261024'];row.update(status='IN_PROGRESS_A12_STEP09_DEFAULT_CONTEXT_BOARD',BOARD_short='PASS_INDEPENDENT_AUDIT_AND_NORMAL_RESTORE',short_real_calls=5400,BOARD_context='RUNNING',context=1024,long_input_tokens=1022,output_limit=2)
    status['stage_status']=row['status'];save(OUT/'CONTEXT_IN_PROGRESS_STATUS.json',status)
    p.write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(row['status'])
