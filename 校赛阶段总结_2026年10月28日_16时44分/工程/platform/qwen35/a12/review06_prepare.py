"""Snapshot governance and derive strictly allocation-only control components."""
import ast
import shutil
from common import ROOT,save
from review06_common import OUT

def main():
    for name in ('docs/PROJECT_STATUS.json','docs/DESIGN_GAP.md','docs/DECISIONS.md','docs/TEST_MATRIX.md',
                 'docs/AI_ASSISTANCE.md','docs/status/A.md','docs/A12_STEP_PLAN_20261023.md'):
        d=OUT/'before'/name;d.parent.mkdir(parents=True,exist_ok=True)
        if d.exists():assert d.read_bytes()==(ROOT/name).read_bytes()
        else:shutil.copyfile(ROOT/name,d)
    p=ROOT/'platform/qwen35/a12'
    supervisor=(p/'step07_supervisor.py').read_text(encoding='utf-8')
    supervisor=supervisor.replace('class PermissionOrder:', 'class PermissionOrder:')
    anchor="        phase=r['phase']\n        if phase not in"
    assert supervisor.count(anchor)==1
    supervisor=supervisor.replace(anchor,"        phase=r['phase']\n        if phase=='submit':raise ValueError('LOAD_ONLY_WINDOW_REJECTS_ALL_COMPUTE_SUBMISSIONS')\n        if phase not in")
    ast.parse(supervisor);(p/'review06_loadonly_supervisor.py').write_text(supervisor,encoding='utf-8',newline='\n')
    w=(p/'window_closeout_v2.py').read_text(encoding='utf-8')
    assert w.count('from step07_supervisor import OwnedWorker')==1
    w=w.replace('from step07_supervisor import OwnedWorker','from review06_loadonly_supervisor import OwnedWorker')
    ast.parse(w);(p/'window_capacity_only.py').write_text(w,encoding='utf-8',newline='\n')
    t=(p/'step07_transport.py').read_text(encoding='utf-8').replace('A12_STEP07_SINGLE_PROJECTION_AUTHORIZED','A12_STEP06_FAILURE_REVIEW_NO_COMPUTE')
    (p/'review06_transport.py').write_text(t,encoding='utf-8',newline='\n')
    save(OUT/'SCOPE.json',dict(operation='REASSESS_TWO_STEP06_FAILURES',
       capacity_operation='ONE_NEW_LOAD_ONLY_WINDOW_72_WEIGHTS_ZERO_RUNS',
       actual_full_BO_bytes=140591104,max_loads=72,max_kernel_submissions=0,
       graph_or_math_change=False,step08='NOT_STARTED',subagents=0,model_settings='unknown',
       old_evidence='IMMUTABLE',dangerous_timeout_or_reset_injection=False))
    print('REVIEW_SNAPSHOT_AND_ZERO_SUBMISSION_COMPONENTS_READY')

if __name__=='__main__':main()
