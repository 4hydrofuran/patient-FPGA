"""PC/WSL tests, no board connection or real signal to any process."""
import base64
import copy
import gzip
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import final_closeout_v2 as c

ROOT=Path(__file__).resolve().parents[3]
EV=ROOT/'evidence/mlp_board_A/20261023-cleanup-board-v3/final_readback_01'


class Checks(unittest.TestCase):
    def setUp(self):
        self.state=json.loads((EV/'state.json').read_bytes())
        self.good=self.state['scan']
        rows=[json.loads(x) for x in (EV/'v3/lifecycle.jsonl').read_bytes().splitlines()]
        self.bad=[r['scan'] for r in rows if r['event']=='RELEASE_OBSERVATION'][-1]

    def validate(self,scan,*a,**kw):
        import sys
        sys.path.insert(0,str(ROOT/'platform/local/a11-mlp-20261023-v1'))
        from accelerator_release_gate_v2 import require_no_users
        require_no_users(scan,*a,**kw)

    def test_actual_fd_churn_requires_new_complete_scan(self):
        it=iter([self.bad,self.good]);logged=[]
        got=c.bounded_scan(lambda:next(it),self.validate,lambda e,**k:logged.append(k),lambda _:None)
        self.assertIs(got,self.good);self.assertEqual(len(logged),2)

    def test_four_incomplete_never_pass(self):
        count=[]
        with self.assertRaisesRegex(RuntimeError,'four incomplete'):
            c.bounded_scan(lambda:self.bad,self.validate,lambda *a,**k:count.append(1),lambda _:None)
        self.assertEqual(len(count),4)

    def test_unsafe_scan_not_retried(self):
        for change in ({'device_holders':[{'pid':1}]},{'device_mappings':[{}]},
            {'boot_id':'different'},{'scan_issues':[{'reason':'PermissionError: denied'}]},
            {'scan_complete':None}):
            s=copy.deepcopy(self.bad);s.update(change);count=[]
            with self.assertRaises(RuntimeError):c.bounded_scan(lambda:s,self.validate,lambda *a,**k:count.append(1),lambda _:None)
            self.assertEqual(len(count),1)

    def test_complete_malformed_still_rejected(self):
        s=copy.deepcopy(self.good);s['inspected_processes']=[]
        with self.assertRaises(RuntimeError):c.bounded_scan(lambda:s,self.validate,lambda *a,**k:None)

    def process(self):
        p=self.state['processes']['8851']
        return dict(stat_text=p['stat'],status=p['status'],cmdline=p['cmdline'].strip().split(' '),
            maps=p['maps'],children=p['children'],threads=['8851'],fds=p['fds'])

    def test_exact_historical_process(self):c.validate_process(**self.process())

    def test_identity_resources_children_signal_rejected(self):
        for change in ({'stat_text':self.process()['stat_text'].replace('644102','644103')},
            {'children':'123'},{'threads':['8851','9']},{'maps':'/dev/dri/card1'},
            {'cmdline':['different']},{'fds':{}},
            {'status':self.process()['status'].replace('SigBlk:\t0000000000004007','SigBlk:\t0000000000004207')}):
            p=self.process();p.update(change)
            with self.assertRaises(RuntimeError):c.validate_process(**p)

    def test_no_hardware_command_allowed(self):
        actor=object.__new__(c.Closeout)
        with patch.object(c.subprocess,'run') as run:
            for argv in (['rmmod','zocl'],['dfx-mgr-client','-load','k26-starter-kits'],['reboot'],['systemctl','start','gdm.service']):
                with self.assertRaises(RuntimeError):actor.readcmd(argv)
            run.assert_not_called()

    def test_signal_consumed_once_and_uses_pidfd(self):
        actor=object.__new__(c.Closeout);actor.signalled=False;actor.phase='PREFLIGHT_PASSED';actor.pidfd=999
        with patch.object(c.signal,'pidfd_send_signal') as send:
            actor.signal_once()
            with self.assertRaises(RuntimeError):actor.signal_once()
            send.assert_called_once_with(999,c.signal.SIGUSR1,None,0)

    def test_unknown_exit_does_not_claim_locks(self):
        actor=object.__new__(c.Closeout);actor.pidfd=999
        with patch.object(c.select,'select',return_value=([],[],[])):
            with self.assertRaisesRegex(RuntimeError,'exit unknown'):actor.confirm_exit()

    def test_orchestration_order_and_failure_no_replay(self):
        names=['preflight','signal_once','confirm_exit','claim_locks','verify_after_exit',
               'prepare_record','archive_lease','commit_record','release_locks']
        class Fake:
            def __init__(self,fail=None):self.calls=[];self.fail=fail
            def emit(self,*a,**k):pass
            def __getattr__(self,name):
                def action():
                    self.calls.append(name)
                    if name==self.fail:raise RuntimeError('injected')
                return action
        f=Fake();c.execute(f);self.assertEqual(f.calls,names)
        for n in names:
            f=Fake(n)
            with self.assertRaises(RuntimeError):c.execute(f)
            self.assertEqual(f.calls,names[:names.index(n)+1])

    def test_atomic_archive_and_no_overwrite_receipts(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);central=base/'locks';central.mkdir();active=central/'active';active.mkdir()
            history=central/'history';history.mkdir();archive=history/'old';dest=base/'receipt';dest.mkdir()
            raw=b'lease';(active/'lease.json').write_bytes(raw)
            actor=object.__new__(c.Closeout);actor.result={};actor.history=lambda:None;actor.emit=lambda *a,**k:None
            with patch.object(c,'CENTRAL',central),patch.object(c,'ARCHIVE',archive),patch.object(c,'LEASE',c.sha(raw)):
                actor.archive_lease()
                self.assertFalse(active.exists());self.assertEqual((archive/'lease.json').read_bytes(),raw)
                with self.assertRaises(FileNotFoundError):actor.archive_lease()
            c.write_new(dest/'result.json',{'state':'prepared'})
            with self.assertRaises(FileExistsError):c.write_new(dest/'result.json',{'state':'overwrite'})

    def test_default_cli_has_no_board_access(self):
        with patch.object(c.sys,'argv',['final_closeout']),patch.object(c,'Closeout') as actor,patch('sys.stdout',new_callable=io.StringIO) as out:
            self.assertEqual(c.main(),0);actor.assert_not_called();self.assertIn('PLAN_ONLY',out.getvalue())

    def test_default_hardware_history_pins_match(self):
        self.assertEqual(c.sha((EV/'v3/lifecycle.jsonl').read_bytes()),c.JOURNAL)
        rows=[json.loads(x) for x in (EV/'v3/lifecycle.jsonl').read_bytes().splitlines()]
        baseline=[r['raw_log'] for r in rows if r['event']=='KERNEL_GATE'][-1]
        self.assertEqual(c.sha(baseline.encode()),c.KLOG)
        import sys
        sys.path.insert(0,str(ROOT/'platform/local/a11-mlp-20261023-v1'))
        from kernel_log_gate import KernelLogGate
        gate=KernelLogGate()
        self.assertTrue(gate.observe(c.BOOT,baseline,c.KLOG)['allowed'])
        self.assertTrue(gate.observe(c.BOOT,(EV/'kernel.raw.txt').read_bytes().decode(),c.KLOG)['allowed'])
        self.assertEqual(c.sha((EV/'active-lease.json').read_bytes()),c.LEASE)

    def test_transport_is_fixed_and_payload_matches_source(self):
        import re
        import final_closeout_host_v2 as host
        argv,pin=host.plan('launch')
        self.assertIn('StrictHostKeyChecking=yes',argv)
        self.assertLess(len(' '.join(argv)),30000)
        blob=re.search(r"b64decode\('([^']+)'\)",argv[-1]).group(1)
        raw=gzip.decompress(base64.b64decode(blob,validate=True))
        self.assertEqual(c.sha(raw),pin)
        self.assertEqual(raw,(Path(__file__).parent/'final_closeout_v2.py').read_bytes())
        compile(raw,'reviewed_final_closeout_v1.py','exec')
        for action in ('stage','resume','status'):
            with self.assertRaises(ValueError):host.plan(action)

    def test_error_returns_and_closes_instead_of_parking(self):
        class Fake:
            phase='PREPARED';signalled=True
            def emit(self,*a,**k):pass
            def close(self):self.closed=True
        actor=Fake()
        with patch.object(c.sys,'argv',['final_closeout','--execute-authorized-final-only']),\
             patch.object(c,'Closeout',return_value=actor),patch.object(c,'execute',side_effect=RuntimeError('injected')) ,\
             patch.object(c,'write_new') as record,patch.object(c.signal,'pthread_sigmask'):
            self.assertEqual(c.main(),2);self.assertTrue(actor.closed);record.assert_called_once()

    def test_actual_policy_loading_with_frozen_bundle_and_journal(self):
        import shutil
        candidate=ROOT/'evidence/mlp_board_A/20261023-cleanup-pc-fix-v3/candidate/cleanup-v3-20261023'
        with tempfile.TemporaryDirectory() as d:
            v3=Path(d)
            for p in candidate.iterdir():shutil.copyfile(p,v3/p.name)
            (v3/'state').mkdir();shutil.copyfile(EV/'v3/lifecycle.jsonl',v3/'state/lifecycle.jsonl')
            actor=object.__new__(c.Closeout)
            with patch.object(c,'V3',v3),patch.object(c,'ROOT',ROOT/'platform/local/a11-mlp-20261023-v1'),patch.object(c,'trusted'):
                actor.load_policy()
            self.assertTrue(actor.kernel.observe(c.BOOT,(EV/'kernel.raw.txt').read_bytes().decode(),c.KLOG)['allowed'])


if __name__=='__main__':unittest.main(verbosity=2)
