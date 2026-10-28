"""PC only; use frozen readbacks and fakes, never send signals or SSH."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest
import recover_cleanup_waiter as r
from test_recover_open_only import Fake

ROOT=Path(__file__).resolve().parents[3]
EV=ROOT/'evidence/mlp_board_A/20261023-recovery-only-v1'


class Tests(unittest.TestCase):
    def state(self):
        return json.loads((EV/'stop_details_02/state.json').read_text())

    def complete(self):
        return self.state()['scan']

    def drive(self,scans,counts=None,loaded=True):
        log=[];valid=[];wait=[]
        inputs=iter(zip(scans,counts or [0 if loaded else None]*len(scans)))
        def sample():
            s,c=next(inputs);return s,c,loaded
        result=r.stable_release(sample,lambda *a:log.append(a),lambda *a:valid.append(a),wait.append)
        return result,log,valid,wait

    def test_two_complete_required(self):
        s=self.complete();result,log,valid,wait=self.drive([s,s])
        self.assertEqual(result,s);self.assertEqual(len(log),2);self.assertEqual(len(valid),2)
        self.assertEqual(wait,[.5])

    def test_real_incomplete_never_counted_as_pass(self):
        rows=[json.loads(x) for x in (EV/'stop_details_02/recovery-lifecycle.jsonl').read_text().splitlines()]
        bad=[x['scan'] for x in rows if x['event']=='RELEASE_OBSERVATION' and x['phase']=='cleanup_locks_acquired'][0]
        s=self.complete();_,log,valid,_=self.drive([bad,s,s])
        self.assertEqual(len(log),3);self.assertEqual(len(valid),2)
        self.assertFalse(log[0][1]['scan_complete'])

    def test_incomplete_resets_consecutive_identity(self):
        s=self.complete();bad=copy.deepcopy(s);bad.update(scan_complete=False,scan_issues=[{'reason':'PROCESS_SET_CHANGED'}])
        _,log,valid,_=self.drive([s,bad,s,s])
        self.assertEqual(len(log),4);self.assertEqual(len(valid),3)

    def test_bounded_readonly_observations(self):
        s=self.complete();s.update(scan_complete=False,scan_issues=[{'reason':'PROCESS_SET_CHANGED'}])
        with self.assertRaisesRegex(RuntimeError,'NO_TWO_COMPLETE'):self.drive([s]*4)

    def test_changed_process_identity_not_stable(self):
        samples=[]
        for n in range(4):
            s=copy.deepcopy(self.complete());s['inspected_processes'][0]['start_ticks']+=n;samples.append(s)
        with self.assertRaisesRegex(RuntimeError,'NO_TWO_COMPLETE'):self.drive(samples)

    def test_actual_owners_refs_and_errors_stop_without_another_sample(self):
        for change in ({'device_holders':[{'pid':999}]},{'device_mappings':[{'pid':999}]},
                       {'boot_id_after':'wrong'}, {'scan_complete':False,'scan_issues':[]},
                       {'scan_complete':False,'scan_issues':[{'reason':'PermissionError: denied'}]},
                       {'scan_complete':False,'scan_issues':[{'reason':'PS_DISPLAY_BINDING_CHANGED'}]}):
            with self.subTest(change=change),self.assertRaises(RuntimeError):
                self.drive([{**self.complete(),**change}])
        for c in (1,None,False,'0'):
            with self.subTest(ref=c),self.assertRaises(RuntimeError):self.drive([self.complete()],[c])

    def test_module_absent(self):
        s=self.complete();self.drive([s,s],loaded=False)
        with self.assertRaises(RuntimeError):self.drive([s],[0],loaded=False)

    def test_full_validator_failure_not_waived(self):
        def fail(*args):raise RuntimeError('STRICT_GATE_ERROR')
        with self.assertRaisesRegex(RuntimeError,'STRICT_GATE_ERROR'):
            r.stable_release(lambda:(self.complete(),0,True),lambda *a:None,fail,lambda n:None)

    def proc(self):
        p=self.state()['process']
        return dict(pid=r.WAITER,stat=p['stat'],status=p['status'],wchan=p['wchan'],
            cmdline=['/usr/bin/python3','-B','-I','-c',r.PRIOR_HELPER+' reviewed_recover_open_only.py'],
            threads=[str(r.WAITER)],children=[])

    def test_waiter_identity_only(self):r.validate_process(**self.proc())

    def test_waiter_mismatch_rejected(self):
        p=self.proc()
        for change in ({'pid':3308},{'stat':p['stat'].replace(' 303592 ',' 303593 ')},
                       {'children':[1]},{'threads':['5322','99']},{'wchan':'io_schedule'},
                       {'cmdline':['python3','other']},
                       {'status':p['status'].replace('SigCgt:\t0000000000000002','SigCgt:\t0000000000000202')}):
            with self.subTest(change=change),self.assertRaises(RuntimeError):r.validate_process(**{**p,**change})

    def test_order_and_failure_cutoff(self):
        f=Fake();r.cleanup_sequence(f)
        self.assertEqual([x for x in f.events if x[0]=='terminate'],[('terminate',5322)])
        self.assertEqual(f.events[:4],[('preflight',),('terminate',5322),('claim_cleanup_locks',),
            ('release_gate','cleanup_locks_acquired',True)])
        for n in range(1,len(f.events)+1):
            with self.subTest(step=n):
                bad=Fake(n)
                with self.assertRaises(RuntimeError):r.cleanup_sequence(bad)
                self.assertEqual(bad.events,f.events[:n])

    def test_immutable_prior_pins(self):
        self.assertEqual(r.sha((EV/'stop_details_02/kernel.raw.txt').read_bytes()),r.KLOG)
        self.assertEqual(r.sha((EV/'stop_details_02/recovery-lifecycle.jsonl').read_bytes()),r.RECOVERY_LOG)
        r.validate_history({n:(EV/'stopped_readback_01'/n).read_bytes() for n in r.LOG_PINS})

    def test_default_plan_no_board(self):
        p=subprocess.run([sys.executable,'-B',r.__file__],capture_output=True,text=True,timeout=5)
        self.assertEqual(p.returncode,0);self.assertEqual(json.loads(p.stdout)['pids'],[5322])


if __name__=='__main__':unittest.main(verbosity=2)
