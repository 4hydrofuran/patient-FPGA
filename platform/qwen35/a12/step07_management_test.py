"""PC release ordering checks of the exact packaged controller; no board API calls."""
import importlib.util
import json
import types
from common import save
from step07_protocol import OUT


if __name__=='__main__':
    path=OUT/'bundle-v1/control/step07_manager.py'
    spec=importlib.util.spec_from_file_location('single_gate_controller_under_test',path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    checks=[]
    for released,closed,code in ((False,True,0),(True,False,0),(True,True,1)):
        p=m.Platform.__new__(m.Platform);p.package=m.WINDOW;p.release_checked=released
        p.worker=types.SimpleNamespace(closed=closed,process=types.SimpleNamespace(returncode=code))
        p.command=lambda *a:(_ for _ in ()).throw(RuntimeError('command must remain unreachable'))
        try:p.remove(m.WINDOW)
        except AssertionError:checks.append(dict(release_checked=released,closed=closed,exit_code=code,rejected=True))
        else:raise AssertionError('unsafe removal accepted')
    p=m.Platform.__new__(m.Platform);p.package=m.WINDOW;p.release_checked=True
    p.worker=types.SimpleNamespace(closed=True,process=types.SimpleNamespace(returncode=0));commands=[]
    def fake(argv,state_changing=False):
        commands.append(dict(argv=argv,state_changing=state_changing));return m.WINDOW+' 0->7\n'
    p.command=fake;p.remove(m.WINDOW)
    assert commands==[dict(argv=['dfx-mgr-client','-listPackage'],state_changing=False),
                      dict(argv=['dfx-mgr-client','-remove','7'],state_changing=True)]
    assert p.release_checked is False
    try:p.remove(m.WINDOW)
    except AssertionError:pass
    else:raise AssertionError('release proof reused')
    checks.append(dict(single_use_release_and_actual_handle=True))
    assert 'ready[\'gpu_layers\']' not in path.read_text()
    save(OUT/'MANAGEMENT_PC.json',dict(status='PASS_PC_PACKAGED_RELEASE_GATES',checks=checks,BOARD='NOT_TESTED'))
    print('PASS_PC_PACKAGED_RELEASE_GATES')
