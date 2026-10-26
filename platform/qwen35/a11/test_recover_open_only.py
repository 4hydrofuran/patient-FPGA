"""PC tests only: no signals, network or device operations."""
import copy
import json
from pathlib import Path
import unittest
import recover_open_only as r

PROJECT = Path(__file__).resolve().parents[3]
OLD = PROJECT/'evidence/mlp_board_A/20261023-integration-v1'


class Fake:
    def __init__(self,fail=None):self.events=[];self.fail=fail
    def __getattr__(self,name):
        def action(*args):
            event=(name,*args);self.events.append(event)
            if len(self.events)==self.fail:raise RuntimeError('CONTROL_ONLY_FAILURE')
        return action


class Tests(unittest.TestCase):
    def test_order_and_no_test_load(self):
        f=Fake();r.cleanup_sequence(f)
        self.assertEqual(f.events,[('preflight',),('terminate',r.WORKER),
            ('release_gate','worker_exited_manager_still_owns_locks',True),('terminate',r.MANAGER),
            ('claim_cleanup_locks',),('release_gate','cleanup_locks_acquired',True),('remove_test',),
            ('release_gate','test_removed',True),('unload_module',),('release_gate','module_removed',False),
            ('load_default',),('release_gate','default_loaded',False),('start_graphics',),('finish',)])

    def test_each_failure_stops_no_following_mutation(self):
        base=Fake();r.cleanup_sequence(base)
        for index in range(1,len(base.events)+1):
            with self.subTest(index=index):
                f=Fake(index)
                with self.assertRaises(RuntimeError):r.cleanup_sequence(f)
                self.assertEqual(f.events,base.events[:index])

    def test_actual_stopped_history(self):
        files={n:(OLD/'stopped_readback_01'/n).read_bytes() for n in r.LOG_PINS}
        r.validate_history(files)
        for name in files:
            with self.subTest(name=name),self.assertRaises(RuntimeError):
                r.validate_history({**files,name:files[name]+b'\n'})

    def process(self,pid):
        if pid==r.WORKER:
            info=json.loads((OLD/'stopped_open_diagnostics_01/state.json').read_text())['worker']
            children=[]
        else:
            info=json.loads((OLD/'stopped_readback_01/state.json').read_text())['manager_proc']
            children=[r.WORKER]
        return dict(pid=pid,stat=info['stat'],status=info['status'],cmdline=info['cmdline'].strip().split(),
                    wchan='hrtimer_nanosleep',threads=[str(pid)],children=children)

    def test_exact_pinned_processes(self):
        for pid in (r.WORKER,r.MANAGER):r.validate_process(**self.process(pid))

    def test_process_mismatch_rejected(self):
        p=self.process(r.WORKER)
        variants=[dict(wchan='io_schedule'),dict(threads=[str(r.WORKER),'999']),dict(children=[999]),
                  dict(cmdline=['python3','wrong']),dict(stat=p['stat'].replace(' 91251 ',' 91252 ')),
                  dict(status=p['status'].replace('SigCgt:\t0000000000000002','SigCgt:\t0000000000000202')),
                  dict(status=p['status'].replace('SigPnd:\t0000000000000000','SigPnd:\t0000000000000200'))]
        for change in variants:
            with self.subTest(change=change),self.assertRaises(RuntimeError):r.validate_process(**{**p,**change})

    def test_defaults_plan_only(self):
        import subprocess,sys
        p=subprocess.run([sys.executable,'-B',r.__file__],capture_output=True,text=True,timeout=5)
        self.assertEqual(p.returncode,0)
        self.assertEqual(json.loads(p.stdout)['mode'],'PLAN_ONLY')


if __name__=='__main__':unittest.main(verbosity=2)
