"""Enter one independent web window with the accepted manager lifecycle."""
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
BUNDLE = ROOT/'bundle'
FRONT = Path('/home/ubuntu/patient-web-demo-20261026')


def prepared_main(source):
    tree = ast.parse(source)
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name=='main')
    if not isinstance(function.body[0], ast.Raise) or 'UNBOUND probe' not in ast.unparse(function.body[0]):
        raise RuntimeError('Accepted manager entry differs')
    function.body = function.body[1:]
    function.name = 'run_web_bound'
    return compile(ast.fix_missing_locations(ast.Module(body=[function],type_ignores=[])),
                   '<accepted-manager-new-web-window>', 'exec')


def main():
    assert os.geteuid()==0 and os.uname().release=='6.8.12-a10irq2'
    assert not Path('/var/lock/kv260-a1/active').exists() and not Path('/sys/module/zocl').exists()
    for path in (FRONT/'web_gateway/src', FRONT/'.venv/lib/python3.12/site-packages', ROOT):
        sys.path.insert(0,str(path))
    import patient_web.managed
    import uvicorn
    import board_case
    assert not (BUNDLE/'run-v1').exists()
    # Capture the current baseline once for the original manager's own gates.
    raw = subprocess.check_output(['dmesg','--raw']).decode()
    (BUNDLE/'control/preflight.json').write_text(json.dumps(dict(
        boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),kernel_raw=raw)))
    manifest=json.loads((BUNDLE/'manifest.json').read_text())
    manifest['files']=[dict(path=p.relative_to(BUNDLE).as_posix(),bytes=p.stat().st_size,
                          sha256=hashlib.sha256(p.read_bytes()).hexdigest())
                       for p in sorted(BUNDLE.rglob('*')) if p.is_file() and p!=BUNDLE/'manifest.json']
    (BUNDLE/'manifest.json').write_text(json.dumps(manifest,indent=2))
    source=BUNDLE/'control/resource_probe_manager.py'
    spec=importlib.util.spec_from_file_location('web_original_manager',source)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.run_case=lambda worker,owner,path,real: board_case.run_case(
        worker,owner,path,real=real,api=module,overlay=ROOT)
    exec(prepared_main(source.read_text()),module.__dict__)
    module.run_web_bound()


if __name__=='__main__':
    main()
