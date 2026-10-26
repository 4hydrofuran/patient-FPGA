"""One actual Board ordinary R0/warm/hit window with corrected authority binding."""
import ast,hashlib,json,os,subprocess,time
from pathlib import Path
ROOT=Path('/var/lib/kv260-a12/pl-authfix-20261026-v2');BUNDLE=ROOT/'bundle'
EXPECTED_BASELINE='ce2ca13f0fa0a3b912b4cfab681ef21a12cad41dc3cdc131db14600da965fbc9'
fresh=json.loads((ROOT/'preflight.json').read_text())
assert os.geteuid()==0 and os.uname().release=='6.8.12-a10irq2'
assert fresh['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip()
assert fresh['baseline_sha256']==EXPECTED_BASELINE
assert hashlib.sha256(subprocess.check_output(['dmesg','--raw'])).hexdigest()==EXPECTED_BASELINE
assert not Path('/var/lock/kv260-a1/active').exists()
assert not Path('/sys/module/zocl').exists()
assert not Path('/lib/firmware/xilinx/a12-pl-authfix-20261026-v2').exists()
assert not (BUNDLE/'run-v1/s2/ready.json').exists()
archive=ROOT/'setup-attempt-01';archive.mkdir(mode=0o700)
(BUNDLE/'run-v1').rename(archive/'run-v1')
for name in ('manager.stdout','manager.stderr','ATTEMPT_RESULT.json','run_bound_original.py'):
 (ROOT/name).rename(archive/name)
entry=ROOT/'run_bound_original2.py'
code='''import ast,importlib.util,json,sys
from pathlib import Path
bundle=Path(BUNDLE_LITERAL)
source=bundle/'control/resource_probe_manager.py'
spec=importlib.util.spec_from_file_location('resource_probe_authorized_authfix',source)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
from resource_probe_binding import require_manager_api
require_manager_api(module)
from resource_probe_policy import validate_plan
assert module.SPEC['authorization_included'] is False
assert validate_plan(json.loads((bundle/'control/requests.json').read_text()),module.SPEC)==3024
tree=ast.parse(source.read_text());function=next(q for q in tree.body if isinstance(q,ast.FunctionDef) and q.name=='main')
assert isinstance(function.body[0],ast.Raise) and 'UNBOUND probe' in ast.unparse(function.body[0])
original_tail=ast.dump(ast.Module(body=function.body[1:],type_ignores=[]),include_attributes=False)
function.body=function.body[1:];function.name='run_bound_original'
assert ast.dump(ast.Module(body=function.body,type_ignores=[]),include_attributes=False)==original_tail
exec(compile(ast.fix_missing_locations(ast.Module(body=[function],type_ignores=[])),str(source)+'#fresh-authfix-binding','exec'),module.__dict__)
module.run_bound_original()
'''.replace('BUNDLE_LITERAL',repr(str(BUNDLE)))
with entry.open('x') as f:f.write(code)
env={k:v for k,v in os.environ.items() if not k.startswith(('SP_A12','LD_','GGML_','OMP_'))}
with (ROOT/'manager.stdout').open('xb') as stdout,(ROOT/'manager.stderr').open('xb') as stderr:
 p=subprocess.Popen(['/usr/bin/python3','-B','-I',str(entry)],stdout=stdout,stderr=stderr,env=env,start_new_session=True)
 print(json.dumps(dict(event='PL_MANAGER_STARTED',pid=p.pid)),flush=True)
 previous=None;deadline=time.monotonic()+1900
 while p.poll() is None and time.monotonic()<deadline:
  cases=[name for name in ('app_R0','warm_prefix','app_hit') if (BUNDLE/'run-v1/s2'/name/'actual-work.json').exists()]
  isolated=BUNDLE/'run-v1/s2/ISOLATED.json'
  state=dict(event='PL_PROGRESS',completed=cases,ready=(BUNDLE/'run-v1/s2/ready.json').exists())
  if isolated.exists():state['isolation']=json.loads(isolated.read_text())
  if state!=previous:print(json.dumps(state),flush=True);previous=state
  if isolated.exists():break
  time.sleep(5)
result=dict(status='NORMAL_MANAGER_EXIT' if p.poll()==0 else 'FAILED_OR_OWNER_RETAINED',manager_pid=p.pid,exit_code=p.poll(),
 stdout_tail=(ROOT/'manager.stdout').read_text(errors='replace')[-2000:],stderr_tail=(ROOT/'manager.stderr').read_text(errors='replace')[-3000:])
for name in ('run-v1/result.json','run-v1/s2/resource-probe-summary.json','run-v1/s2/ordinary-pair-comparison.json','run-v1/s2/ISOLATED.json','run-v1/s2/PROBE_FAILURE.json'):
 q=BUNDLE/name
 if q.exists():result[name]=json.loads(q.read_text())
result['cases']={}
for name in ('app_R0','warm_prefix','app_hit'):
 case=BUNDLE/'run-v1/s2'/name;values={}
 for file in ('result.json','actual-work.json','client-timing.json','application-timing.json'):
  q=case/file
  if q.exists():values[file]=json.loads(q.read_text())
 result['cases'][name]=values
(ROOT/'ATTEMPT_RESULT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print('__PL_BEGIN__',flush=True);print(json.dumps(result,ensure_ascii=False),flush=True);print('__PL_END__',flush=True)
