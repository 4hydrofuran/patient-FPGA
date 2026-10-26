"""Additive task07 l00 MLP scope; reuse pinned native code and fixed closeout."""
import ast
import json
from pathlib import Path
import shutil
from common import ROOT,sha,save

OUT=ROOT/'evidence/model_pl_A/20261024-step07-mlp-v1'

def main():
    OUT.mkdir(exist_ok=False)
    for name in ('docs/PROJECT_STATUS.json','docs/DESIGN_GAP.md','docs/DECISIONS.md','docs/TEST_MATRIX.md',
                 'docs/AI_ASSISTANCE.md','docs/status/A.md','docs/A12_STEP_PLAN_20261023.md'):
        dest=OUT/'before'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,dest)
    p=ROOT/'platform/qwen35/a12'
    manager=(p/'step07_manager.py').read_text()
    changes={
      'from window import Window':'from window_closeout_v2 import Window',
      "a12-single-gate-20261023-v1":"a12-mlp-l00-20261024-v1",
      "'l0_gate'":"'l0'",'==1\n    else:assert ready':'==3\n    else:assert ready',
      "host_verified_completions']==3":"host_verified_completions']==9",
      "route['weight_load_count']==1":"route['weight_load_count']==3",
      "row['op']=='gate'":"row['op'] in ('gate','up','down')",
      'CmaFree\']-2112':'CmaFree\']-5920','MemAvailable\']-2112':'MemAvailable\']-5920',
      'max_runs=17,max_loads=1,explicit_bo_budget_bytes=2162688':'max_runs=51,max_loads=3,explicit_bo_budget_bytes=6062080',
      "step07_MLP='NOT_TESTED'":"step07_MLP='EXECUTED_PENDING_INDEPENDENT_AUDIT'",
      'SINGLE_GATE':'L00_MLP',
      'One reviewed l00 gate model window':'One reviewed l00 gate/up/down model window',
      'Admission is for ONLY l00 gate':'Admission is for ONLY l00 gate/up/down',
    }
    for old,new in changes.items():
        assert old in manager,old
        manager=manager.replace(old,new)
    ast.parse(manager);(p/'step07_mlp_manager.py').write_text(manager,encoding='utf-8',newline='\n')
    transport=(p/'step07_transport.py').read_text().replace('SINGLE_PROJECTION_AUTHORIZED','L00_MLP_AUTHORIZED')
    (p/'step07_mlp_transport.py').write_text(transport,encoding='utf-8',newline='\n')
    package=(p/'step07_package.py').read_text()
    begin=package.index("    source=ROOT/")
    end=package.index("    preflight=json.loads")
    replacement='''    source=ROOT/'evidence/model_pl_A/20261023-step07-single-v1/bundle-v1'
    original=json.loads((source/'manifest.json').read_text())
    assert sha(source/'manifest.json')=='c3bdb07de4e97cd74c03e62b718b558bdf5aba79b9dd118b452c2a710969f64d'
    for row in original['files']:
        f=source/row['path'];assert f.stat().st_size==row['bytes'] and sha(f)==row['sha256']
    target=OUT/'bundle-v1';shutil.copytree(source,target)
    (target/'manifest.json').rename(target/'single-parent-manifest.json')
    platform=target/'platform/qwen35/a12';control=target/'control'
    for name in ('window_closeout_v2.py','step07_finalize_policy.py','step07_supervisor.py'):
        shutil.copyfile(ROOT/'platform/qwen35/a12'/name,platform/name)
    tested=json.loads((ROOT/'evidence/model_pl_A/20261024-step07-finalize-v1/WINDOW_V2_PC_FINAL.json').read_text())
    assert tested['tested_source_sha256']==sha(platform/'window_closeout_v2.py')
    shutil.copyfile(ROOT/'platform/qwen35/a12/step07_mlp_manager.py',control/'step07_mlp_manager.py')
    for name in ('preflight.json','asset-pins.json','request.json'):
        (control/name).rename(control/('single-parent-'+name))
'''
    package=package[:begin]+replacement+package[end:]
    package=package.replace('from step07_protocol import OUT','from step07_mlp_prepare import OUT')
    package=package.replace('step07-single-20261023-v1','step07-mlp-20261024-v1').replace('step07-single-readback-20261023-v1','step07-mlp-readback-20261024-v1')
    package=package.replace('SINGLE_GATE','L00_MLP').replace('SINGLE_PROJECTION','L00_MLP').replace("scope='l0_gate',max_loads=1,max_runs=17","scope='l0',max_loads=3,max_runs=51")
    package=package.replace('explicit_BO_budget_bytes=2162688','explicit_BO_budget_bytes=6062080')
    package=package.replace('step07_manager.py','step07_mlp_manager.py').replace('single-gate.tar','l00-mlp.tar')
    package=package.replace("sha(target/'base-manifest.json')","sha(target/'single-parent-manifest.json')")
    # Preserve the readonly independent state inside the result archive too.
    package=package.replace("    (OUT/'readback_reviewed.py').write_text(read)","    read=read.replace(\"        package=ROOT/'readback-v1.tar.gz'\",\"        (ROOT/'run-v1/independent-readback.json').write_text(json.dumps(state))\\n        package=ROOT/'readback-v1.tar.gz'\")\n    (OUT/'readback_reviewed.py').write_text(read)")
    ast.parse(package);(p/'step07_mlp_package.py').write_text(package,encoding='utf-8',newline='\n')
    save(OUT/'SCOPE.json',dict(scope='l0',expected_actual_calls=9,max_runs=51,max_loads=3,
       explicit_BO_bytes=6062080,requests=1,teacher_tokens=[10,11],prompt=list(range(1,10)),
       task08='NOT_STARTED',task06_failures='DEFERRED_BY_USER',model_or_native_math_changed=False,
       model_setting_actual='unknown',reasoning_setting_actual='unknown',subagents=0))
    print(json.dumps(dict(status='MLP_SCOPE_AND_ADDITIVE_SOURCES_READY',output=str(OUT))))

if __name__=='__main__':main()
