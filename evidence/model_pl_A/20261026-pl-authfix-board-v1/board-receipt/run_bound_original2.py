import ast,importlib.util,json,sys
from pathlib import Path
bundle=Path('/var/lib/kv260-a12/pl-authfix-20261026-v1/bundle')
source=bundle/'control/resource_probe_manager.py'
spec=importlib.util.spec_from_file_location('resource_probe_authorized_authfix',source)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
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
