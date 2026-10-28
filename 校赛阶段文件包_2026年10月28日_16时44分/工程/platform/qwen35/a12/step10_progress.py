"""Record task10 progress without changing historical results or enabling defaults."""
import json
from datetime import datetime,timezone,timedelta
from common import ROOT,save
from step10_common import OUT
if __name__=='__main__':
    value=dict(status='IN_PROGRESS_A12_STEP10_FAIR_BOARD_PERFORMANCE',updated_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),
               PC='PASS_NATIVE_CLOCKS_CONTROL_AND_JOURNAL',CROSS_BUILD='PASS_A53_2026.1',BOARD='PENDING_BASELINE',
               speedup=None,default_FPGA_enabled=False,actual_model_settings='unknown',
               first_PC_timing_classification_failure='PRESERVED_FIXED_FFN_OUT',next='BOUNDED_BASELINE_THEN_CONDITIONAL_FIX_AND_RETEST')
    assert json.loads((OUT/'pc_native_02.json').read_text())['exit_code']==0
    save(OUT/'IN_PROGRESS_STATUS.json',value)
    p=ROOT/'docs/PROJECT_STATUS.json';status=json.loads(p.read_text(encoding='utf-8'))
    status['a12_step10_performance_20261024']=value;status['stage']='A12';status['stage_status']=value['status']
    p.write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
