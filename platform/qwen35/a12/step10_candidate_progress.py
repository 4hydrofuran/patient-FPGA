"""Record audited baseline and pending candidate measurements without promoting them."""
import json
from datetime import datetime,timezone,timedelta
from common import ROOT,save
from step10_common import OUT
if __name__=='__main__':
    p=ROOT/'docs/PROJECT_STATUS.json';status=json.loads(p.read_text(encoding='utf-8'))
    value=dict(status['a12_step10_performance_20261024'])
    value.update(updated_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),
        BOARD='BASELINE_PASS_OPTIMIZED_WINDOW_RUNNING',baseline_report='evidence/model_pl_A/20261024-step10-v1/BASELINE_AUDIT.json',
        baseline_bottleneck='PER_PERMISSION_HEALTH_AND_DURABLE_JOURNAL',candidate_result='PENDING_COMPLETE_AND_INDEPENDENT_AUDIT',
        baseline_restored=True,default_FPGA_enabled=False,speedup=None)
    save(OUT/'CANDIDATE_IN_PROGRESS_STATUS.json',value)
    status['a12_step10_performance_20261024']=value
    p.write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
