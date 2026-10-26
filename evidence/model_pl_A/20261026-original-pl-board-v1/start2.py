"""Fresh authorized binding of original gates and one ordinary PL group."""
import ast,hashlib,importlib.util,json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path('/var/lib/kv260-a12/original-pl-20261026-v1');BUNDLE=ROOT/'bundle'
EXPECTED_BASELINE='b515d9b084933bd7f6816e3516c2b4e175cbba4d5ed8e830e26e31250cf3e854'
fresh=json.loads((ROOT/'preflight.json').read_text())
assert os.geteuid()==0 and os.uname().release=='6.8.12-a10irq2'
assert fresh['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip()
assert fresh['baseline_sha256']==EXPECTED_BASELINE
raw=subprocess.check_output(['dmesg','--raw'])
assert hashlib.sha256(raw).hexdigest()==EXPECTED_BASELINE,'Kernel changed after exact baseline review'
entry=ROOT/'run_bound_original2.py'
code='''import ast,importlib.util,json,sys
from pathlib import Path
bundle=Path(BUNDLE_LITERAL)
source=bundle/'control/resource_probe_manager.py'
spec=importlib.util.spec_from_file_location('original_resource_probe_authorized_binding',source)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
tree=ast.parse(source.read_text());function=next(q for q in tree.body if isinstance(q,ast.FunctionDef) and q.name=='main')
assert isinstance(function.body[0],ast.Raise) and 'UNBOUND probe' in ast.unparse(function.body[0])
original_tail=ast.dump(ast.Module(body=function.body[1:],type_ignores=[]),include_attributes=False)
function.body=function.body[1:];function.name='run_bound_original'
assert ast.dump(ast.Module(body=function.body,type_ignores=[]),include_attributes=False)==original_tail
exec(compile(ast.fix_missing_locations(ast.Module(body=[function],type_ignores=[])),str(source)+'#fresh-reviewed-binding','exec'),module.__dict__)
module.run_bound_original()
'''.replace('BUNDLE_LITERAL',repr(str(BUNDLE)))
with entry.open('x') as f:f.write(code)
(ROOT/'COMPUTE_BASELINE_REVIEW-v2.json').write_text(json.dumps(dict(boot_id=fresh['boot_id'],kernel=os.uname().release,
     exact_sha256=EXPECTED_BASELINE,review='Primary agent reviewed current startup diagnostics; preserve baseline and reject new diagnostics',
     original_gate_and_main_tail_unchanged=True,new_lease_required=True,single_group=['app_R0','warm_prefix','app_hit'])))
env={k:v for k,v in os.environ.items() if not k.startswith(('SP_A12','LD_','GGML_','OMP_'))}
with (ROOT/'manager2.stdout').open('xb') as stdout,(ROOT/'manager2.stderr').open('xb') as stderr:
    p=subprocess.Popen(['/usr/bin/python3','-B','-I',str(entry)],stdout=stdout,stderr=stderr,env=env,start_new_session=True)
    print(json.dumps(dict(event='PL_MANAGER_STARTED',pid=p.pid)),flush=True)
    previous=None;deadline=time.monotonic()+240
    while p.poll() is None and time.monotonic()<deadline:
        cases=[name for name in ('app_R0','warm_prefix','app_hit') if (BUNDLE/'run-v1/s2'/name/'actual-work.json').exists()]
        isolated=BUNDLE/'run-v1/s2/ISOLATED.json'
        state=dict(event='PL_PROGRESS',completed=cases)
        if isolated.exists():state['isolation']=json.loads(isolated.read_text())
        if state!=previous:print(json.dumps(state),flush=True);previous=state
        if isolated.exists():break
        time.sleep(5)
result=dict(status='NORMAL_MANAGER_EXIT' if p.poll()==0 else 'FAILED_OR_OWNER_RETAINED',manager_pid=p.pid,exit_code=p.poll(),
            stdout_tail=(ROOT/'manager2.stdout').read_text(errors='replace')[-2000:],stderr_tail=(ROOT/'manager2.stderr').read_text(errors='replace')[-3000:])
for name in ('run-v1/result.json','run-v1/s2/resource-probe-summary.json','run-v1/s2/ISOLATED.json','run-v1/PROBE_FAILURE.json'):
    q=BUNDLE/name
    if q.exists():result[name]=json.loads(q.read_text())
results={}
for name in ('app_R0','warm_prefix','app_hit'):
    case=BUNDLE/'run-v1/s2'/name
    if (case/'result.json').exists():
        q=json.loads((case/'result.json').read_text());results[name]=dict(status=q.get('status'),text=q.get('text'),eos=q.get('eos'),
            state_cleared=q.get('state_cleared_before_response'),route_count=q.get('bridge',{}).get('a12_route',{}).get('host_verified_completions'))
        if (case/'application-timing.json').exists():results[name]['application_timing']=json.loads((case/'application-timing.json').read_text())
result['cases']=results
(ROOT/'ATTEMPT_RESULT-v2.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print('__PL_BEGIN__',flush=True);print(json.dumps(result,ensure_ascii=False),flush=True);print('__PL_END__',flush=True)
