"""Register actual in-progress task09 without changing historical pass entries."""
import json
from common import ROOT,save
from step09_common import OUT

if __name__=='__main__':
    p=ROOT/'docs/PROJECT_STATUS.json';status=json.loads(p.read_text(encoding='utf-8'))
    assert 'a12_step09_state_cancel_20261024' not in status
    row=dict(status='IN_PROGRESS_A12_STEP09_SHORT_BOARD_CONTEXT_PENDING',PC_native='PASS',PC_controls='31_CASES_764_CHECKS_PASS',app_state_PC='17_TESTS_PASS_AFTER_UTF8_FIX',BOARD_short='RUNNING',BOARD_context='NOT_STARTED',evidence='evidence/model_pl_A/20261024-step09-v1',default_FPGA_enabled=False,hardware_global_count=None,board_speedup=None)
    status={'a12_step09_state_cancel_20261024':row,**status};status['stage']='A12';status['stage_status']=row['status']
    save(OUT/'IN_PROGRESS_STATUS.json',status)
    p.write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(row['status'])
