"""Offline and WSL-only fixtures. No SSH/serial, board or signal operations."""
import copy
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock

import cleanup_board_v3 as board
from cleanup_controller_v3 import Controller, ControlServer, ObservationDeferred, UnknownCommand, STEPS, observe_release
from cleanup_recovery_plan_v3 import choose

PROJECT=Path(__file__).resolve().parents[3]
BUNDLE=PROJECT/'platform/local/a11-mlp-20261023-v1'
sys.path.insert(0,str(BUNDLE))
from accelerator_release_gate_v2 import require_release,require_no_users
import isolated_idle_policy as policy
import recover_cleanup_waiter as old

EVIDENCE=PROJECT/'evidence/mlp_board_A/20261023-recovery-continuation-v1/readback_01'


def frozen():
    return json.loads((EVIDENCE/'state.json').read_bytes())


def history():
    return [json.loads(line) for line in (EVIDENCE/'recovery-continuation-20261023-v1/lifecycle.jsonl').read_text().splitlines()]


class FakeIO:
    def __init__(self, pause=None, failure=None, gate_error=None):
        self.pause=pause;self.failure=failure;self.gate_error=gate_error;self.actions=[];self.logs=[];self.gates=[]
    def emit(self,event,**data):self.logs.append(dict(event=event,**data))
    def gate(self,step):
        self.gates.append(step)
        if step==self.gate_error:raise RuntimeError('UNSAFE_GATE')
        if step==self.pause:
            self.pause=None;raise ObservationDeferred('READONLY_INCOMPLETE')
    def apply(self,step):
        self.actions.append(step)
        if step==self.failure:raise UnknownCommand('MUTATION_NOT_CONFIRMED')


class ObservationTests(unittest.TestCase):
    def drive(self,scans,counts=None,loaded=True):
        values=iter(zip(scans,counts if counts is not None else [0 if loaded else None]*len(scans)))
        log=[];sleeps=[]
        def sample():
            s,n=next(values);return s,n,loaded
        def validate(s,n,is_loaded):
            if is_loaded:require_release(s,n,True,boot_id=board.BOOT)
            else:require_no_users(s,True,boot_id=board.BOOT)
        result=observe_release(sample,lambda *v:log.append(v),validate,board.BOOT,sleeps.append)
        return result,log,sleeps

    def test_reproduce_old_failure_and_fix_exact_trace(self):
        samples=[r['scan'] for r in history() if r['event']=='RELEASE_OBSERVATION' and r['phase']=='cleanup_locks_acquired']
        self.assertEqual([s['scan_complete'] for s in samples],[True,True,True,False])
        it=iter(samples)
        with self.assertRaisesRegex(RuntimeError,'NO_TWO_COMPLETE'):
            old.stable_release(lambda:(next(it),0,True),lambda *a:None,
                lambda s,n,l:require_release(s,n,True,boot_id=board.BOOT),lambda n:None)
        result,logs,wait=self.drive(samples)
        self.assertEqual(result,samples[0]);self.assertEqual(len(logs),1);self.assertEqual(wait,[])

    def test_each_changed_but_complete_snapshot_passes_strict_gate(self):
        samples=[r['scan'] for r in history() if r['event']=='RELEASE_OBSERVATION' and r['phase']=='cleanup_locks_acquired']
        for s in samples[:3]:self.drive([s])

    def test_incomplete_is_retained_not_passed(self):
        s=frozen()['scan'];bad=copy.deepcopy(s)
        bad.update(scan_complete=False,scan_issues=[{'reason':'PROCESS_SET_CHANGED'}])
        _,logs,wait=self.drive([bad,s]);self.assertEqual(len(logs),2);self.assertEqual(wait,[.5])
        self.assertFalse(logs[0][1]['scan_complete'])

    def test_four_incomplete_pauses_without_mutation(self):
        s=frozen()['scan'];s.update(scan_complete=False,scan_issues=[{'reason':'PROCESS_SET_CHANGED'}])
        with self.assertRaises(ObservationDeferred):self.drive([s]*4)

    def test_missing_proc_is_only_temporary_if_exact_match(self):
        s=frozen()['scan'];bad=copy.deepcopy(s)
        bad.update(scan_complete=False,scan_issues=[{'pid':5321,'reason':"FileNotFoundError: [Errno 2] No such file or directory: '/proc/5321/stat'"}])
        self.drive([bad,s])
        bad['scan_issues'][0]['pid']=777
        with self.assertRaisesRegex(RuntimeError,'NON_TRANSIENT'):self.drive([bad])

    def test_security_and_device_failures_never_resampled(self):
        changes=[{'device_holders':[{'pid':3}]},{'device_mappings':[{'pid':3}]},
            {'boot_id':'wrong'},{'schema':'wrong'},{'scan_complete':None},
            {'scan_complete':False,'scan_issues':[]},
            {'scan_complete':False,'scan_issues':[{'reason':'PermissionError: denied'}]},
            {'scan_complete':False,'scan_issues':[{'reason':'ValueError: PROCESS_OR_FD_TABLE_CHANGED'}]},
            {'scan_complete':False,'scan_issues':[{'reason':'PS_DISPLAY_BINDING_CHANGED'}]}]
        for change in changes:
            with self.subTest(change=change),self.assertRaises(RuntimeError):self.drive([{**frozen()['scan'],**change}])
        for ref in (False,True,1,None,'0'):
            with self.subTest(ref=ref),self.assertRaises(RuntimeError):self.drive([frozen()['scan']],[ref])

    def test_complete_but_malformed_rejected_by_original_gate(self):
        s=frozen()['scan'];s['inspected_processes']=[]
        with self.assertRaises(RuntimeError):self.drive([s])

    def test_absent_module_still_requires_full_scan(self):
        s=frozen()['scan'];self.drive([s],loaded=False)
        with self.assertRaises(RuntimeError):self.drive([s],[0],loaded=False)

    def test_kernel_error_not_retried(self):
        def fail():raise RuntimeError('KERNEL_LOG_BLOCKED')
        with self.assertRaisesRegex(RuntimeError,'KERNEL_LOG_BLOCKED'):
            observe_release(fail,lambda *a:None,lambda *a:None,board.BOOT,lambda n:None)


class StateMachineTests(unittest.TestCase):
    def test_normal_order_once(self):
        io=FakeIO();c=Controller(io)
        self.assertEqual(c.resume('authorized-001',0)['state'],'COMPLETE_NEEDS_INDEPENDENT_READBACK')
        self.assertEqual(io.actions,list(STEPS))
        with self.assertRaises(RuntimeError):c.resume('authorized-002',1)

    def test_pause_each_stage_and_resume_same_controller_no_replay(self):
        for i,step in enumerate(STEPS):
            with self.subTest(step=step):
                io=FakeIO(pause=step);c=Controller(io);identity=id(c)
                result=c.resume('authorized-001',0)
                self.assertEqual(result['state'],'PAUSED_READONLY');self.assertEqual(io.actions,list(STEPS[:i]))
                self.assertEqual(result['next_step'],step)
                with self.assertRaises(RuntimeError):c.resume('authorized-001',1)
                with self.assertRaises(RuntimeError):c.resume('authorized-002',0)
                c.resume('authorized-002',1)
                self.assertEqual(id(c),identity);self.assertEqual(io.actions,list(STEPS))

    def test_unknown_each_action_latches_and_retains_checkpoint(self):
        for i,step in enumerate(STEPS):
            with self.subTest(step=step):
                io=FakeIO(failure=step);c=Controller(io);s=c.resume('authorized-001',0)
                self.assertEqual(s['state'],'HARD_STOP_RECONCILE_ONLY');self.assertEqual(s['inflight'],step)
                self.assertEqual(s['completed_steps'],list(STEPS[:i]))
                with self.assertRaises(RuntimeError):c.resume('authorized-002',1)
                self.assertEqual(io.actions,list(STEPS[:i+1]))

    def test_unsafe_gate_each_phase_blocks_action(self):
        for i,step in enumerate(STEPS):
            io=FakeIO(gate_error=step);c=Controller(io)
            self.assertEqual(c.resume('authorized-001',0)['state'],'HARD_STOP_RECONCILE_ONLY')
            self.assertEqual(io.actions,list(STEPS[:i]))

    def test_deferred_inside_action_not_misclassified_as_retryable(self):
        io=FakeIO()
        def bad(step):raise ObservationDeferred('this is after STEP_BEGIN')
        io.apply=bad;c=Controller(io)
        self.assertEqual(c.resume('authorized-001',0)['state'],'HARD_STOP_RECONCILE_ONLY')

    def test_status_never_runs_gate_or_action(self):
        io=FakeIO(pause='remove_test');c=Controller(io);c.resume('authorized-001',0)
        before=copy.deepcopy((io.actions,io.gates,io.logs))
        for _ in range(10):c.status()
        self.assertEqual(before,(io.actions,io.gates,io.logs))

    def test_write_ahead_step_begin_precedes_action_commit(self):
        io=FakeIO();c=Controller(io);c.resume('authorized-001',0)
        for step in STEPS:
            records=[r['event'] for r in io.logs if r.get('step')==step]
            self.assertEqual(records,['STEP_BEGIN','STEP_COMMITTED'])

    def test_bad_authority_has_no_effect(self):
        for auth,generation in [('',0),('bad;command',0),('authorized-001',True),('authorized-001',1)]:
            io=FakeIO();c=Controller(io)
            with self.assertRaises(RuntimeError):c.resume(auth,generation)
            self.assertEqual(io.actions,[]);self.assertEqual(c.generation,0)


class BoardAdapterTests(unittest.TestCase):
    def setUp(self):
        self.type=board.make_recovery_type()

    def waiter(self):
        p=frozen()['recovery_process']
        return dict(pid=6174,stat=p['stat'],status=p['status'],wchan=p['wchan'],threads=['6174'],children=[],
            cmdline=['/usr/bin/python3','-B','-I','-c',board.PRIOR_HELPER+' reviewed_recover_cleanup_waiter.py'])

    def test_pinned_current_waiter_and_history(self):
        board.validate_process(**self.waiter())
        self.assertEqual(hashlib.sha256((EVIDENCE/'recovery-continuation-20261023-v1/lifecycle.jsonl').read_bytes()).hexdigest(),board.CONTINUATION_LOG)
        self.assertEqual(hashlib.sha256((EVIDENCE/'kernel.raw.txt').read_bytes()).hexdigest(),board.KLOG)

    def test_wrong_waiter_never_signalled(self):
        p=self.waiter()
        for change in ({'pid':5322},{'stat':p['stat'].replace(' 383249 ',' 383250 ')},{'children':[999]},
                       {'wchan':'io_schedule'},{'cmdline':['python','other']},
                       {'status':p['status'].replace('SigBlk:\t0000000000004007','SigBlk:\t0000000000004207')}):
            with self.subTest(change=change),self.assertRaises(RuntimeError):board.validate_process(**{**p,**change})

    def adapter(self):
        obj=self.type.__new__(self.type);obj.pending=[];obj.records=[]
        obj.emit=lambda e,**k:obj.records.append(dict(event=e,**k))
        obj.snapshot=lambda p:{};obj.kernel_checkpoint=lambda *a:None
        return obj

    def test_actual_command_timeout_retains_child_without_kill(self):
        obj=self.adapter();p=mock.Mock(pid=12345)
        p.communicate.side_effect=subprocess.TimeoutExpired('rmmod',8)
        with mock.patch.object(policy,'lock_owned',return_value=True):
            # Class captures the original function; inject a new class while patched.
            obj.__class__=board.make_recovery_type()
        with mock.patch.object(board.subprocess,'Popen',return_value=p):
            with self.assertRaises(UnknownCommand):obj.command(['rmmod','zocl'],True)
        self.assertEqual(obj.pending,[p]);p.kill.assert_not_called();p.terminate.assert_not_called()

    def test_actual_allowlist_and_nonzero_exit(self):
        obj=self.adapter()
        with mock.patch.object(policy,'lock_owned',return_value=True):obj.__class__=board.make_recovery_type()
        for argv in (['reboot'],['rmmod','-f','zocl'],['dfx-mgr-client','-load','test'],['sh','-c','true']):
            with self.subTest(argv=argv),mock.patch.object(board.subprocess,'Popen') as spawn:
                with self.assertRaises(RuntimeError):obj.command(argv,True)
                spawn.assert_not_called()
        p=mock.Mock(returncode=1);p.communicate.return_value=('','failure')
        with mock.patch.object(board.subprocess,'Popen',return_value=p):
            with self.assertRaisesRegex(RuntimeError,'management command failed'):obj.command(['rmmod','zocl'],True)
        p.kill.assert_not_called();p.terminate.assert_not_called()

    def test_real_linux_lock_retained_across_pause(self):
        import fcntl
        with tempfile.TemporaryDirectory(prefix='a11-cleanup-lock-') as name:
            path=Path(name)/'lock';first=os.open(path,os.O_CREAT|os.O_RDWR,0o600)
            other=os.open(path,os.O_RDWR)
            try:
                fcntl.flock(first,fcntl.LOCK_EX|fcntl.LOCK_NB)
                io=FakeIO(pause='remove_test');c=Controller(io);c.resume('authorized-001',0)
                with self.assertRaises(BlockingIOError):fcntl.flock(other,fcntl.LOCK_EX|fcntl.LOCK_NB)
                self.assertEqual(c.status()['state'],'PAUSED_READONLY')
            finally:os.close(other);os.close(first)

    def test_actual_adapter_composition_resume_does_not_repeat_management_commands(self):
        # Real gate/apply/remove/unload/load/default checks, simulated OS only.
        io=self.adapter();io.initial_vart=None;io.held=[]
        state=dict(overlays={board.ROOT.name+'_image_1':'applied'},module_refcount=0,
            zocl_bound=['zocl'],render_nodes=['/dev/dri/renderD128'],accelerator_card_nodes=[],
            device_holders=[],fpga_state='operating',vart_sha256=None)
        commands=[];paused=[False];gdm=[False]
        io.snapshot=lambda phase:copy.deepcopy(state)
        io.stopped_history=lambda:None;io.pins=lambda:None
        io.preflight=lambda:None;io.terminate=lambda pid:commands.append(('signal-simulated',pid))
        io.claim_cleanup_locks=lambda:io.held.append('simulated-lock')
        def gate(phase,loaded):
            sample=frozen()['scan']
            if phase=='before_load_default' and not paused[0]:
                paused[0]=True;sample.update(scan_complete=False,scan_issues=[{'reason':'PROCESS_SET_CHANGED'}])
            observe_release(lambda:(sample,state['module_refcount'],loaded),lambda *a:None,
                lambda s,n,l:require_release(s,n,True,boot_id=board.BOOT) if l else require_no_users(s,True,boot_id=board.BOOT),
                board.BOOT,lambda n:None)
        io.release_gate=gate
        io.finish=lambda:commands.append(('finalize-simulated',))
        def spawn(argv,**kwargs):
            commands.append(tuple(argv));output=''
            if argv==['dfx-mgr-client','-listPackage']:output=board.ROOT.name+' 0->1\n'
            elif argv==['dfx-mgr-client','-remove','1']:
                state.update(overlays={},zocl_bound=[],render_nodes=[])
            elif argv==['rmmod','zocl']:state['module_refcount']=None
            elif argv==['dfx-mgr-client','-load','k26-starter-kits']:state['overlays']={'k26-starter-kits_image_1':'applied'}
            elif argv==['systemctl','start','gdm.service']:gdm[0]=True
            else:raise AssertionError(argv)
            p=mock.Mock(returncode=0);p.communicate.return_value=(output,'');return p
        def run(argv,**kwargs):
            self.assertEqual(argv,['systemctl','is-active','gdm.service'])
            return subprocess.CompletedProcess(argv,0 if gdm[0] else 3,b'active\n' if gdm[0] else b'inactive\n',b'')
        with mock.patch.object(policy,'lock_owned',return_value=True):io.__class__=board.make_recovery_type()
        with mock.patch.object(board.subprocess,'Popen',side_effect=spawn),mock.patch.object(board.subprocess,'run',side_effect=run):
            c=Controller(io)
            self.assertEqual(c.resume('authorized-001',0)['next_step'],'load_default')
            self.assertEqual(c.state,'PAUSED_READONLY');self.assertEqual(state['module_refcount'],None)
            self.assertEqual(c.resume('authorized-002',1)['state'],'COMPLETE_NEEDS_INDEPENDENT_READBACK')
        for command in [('signal-simulated',6174),('dfx-mgr-client','-remove','1'),('rmmod','zocl'),
                        ('dfx-mgr-client','-load','k26-starter-kits'),('systemctl','start','gdm.service')]:
            self.assertEqual(commands.count(command),1)

    def test_cli_defaults_and_missing_authority_do_not_touch_board(self):
        for name in ('cleanup_board_v3.py','cleanup_control_v3.py'):
            p=subprocess.run([sys.executable,'-B',str(Path(__file__).parent/name)],capture_output=True,text=True,timeout=5)
            self.assertEqual(p.returncode,0);self.assertEqual(json.loads(p.stdout)['mode'],'PLAN_ONLY')
        p=subprocess.run([sys.executable,'-B',str(Path(board.__file__)),'--execute-authorized-takeover'],capture_output=True,text=True,timeout=5)
        self.assertNotEqual(p.returncode,0);self.assertIn('explicit authorization',p.stderr)


class ControlSocketTests(unittest.TestCase):
    def test_actual_unix_status_resume_no_second_controller(self):
        io=FakeIO(pause='remove_test');controller=Controller(io);controller.resume('authorized-001',0)
        with tempfile.TemporaryDirectory(prefix='a11-control-') as name:
            os.chmod(name,0o700);server=ControlServer(controller,name,uid=os.geteuid())
            def call(payload):
                thread=threading.Thread(target=server.serve_one);thread.start()
                with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as s:
                    s.settimeout(3);s.connect(str(server.path));s.sendall(json.dumps(payload).encode()+b'\n')
                    data=b''
                    while not data.endswith(b'\n'):data+=s.recv(8192)
                thread.join(3);self.assertFalse(thread.is_alive());return json.loads(data)
            try:
                self.assertEqual(call({'action':'status'})['state'],'PAUSED_READONLY')
                self.assertEqual(io.actions,['takeover'])
                self.assertIn('error',call({'action':'execute','cmd':'reboot'}))
                self.assertIn('error',call({'action':'resume','authorization_id':'authorized-001','generation':1}))
                self.assertEqual(call({'action':'resume','authorization_id':'authorized-002','generation':1})['state'],'COMPLETE_NEEDS_INDEPENDENT_READBACK')
                self.assertEqual(io.actions,list(STEPS))
                with self.assertRaises(RuntimeError):server.dispatch({'action':'status'},os.geteuid()+1)
            finally:server.close()
            self.assertFalse(server.path.exists())

    def test_endpoint_never_overwritten(self):
        with tempfile.TemporaryDirectory(prefix='a11-control-') as name:
            os.chmod(name,0o700);p=Path(name)/'control.sock';p.write_text('existing evidence')
            with self.assertRaises(RuntimeError):ControlServer(Controller(FakeIO()),name,uid=os.geteuid())
            self.assertEqual(p.read_text(),'existing evidence')


class RouteTests(unittest.TestCase):
    def test_last_readback_is_only_candidate_not_permission(self):
        result=choose(frozen())
        self.assertEqual(result['route'],'SAME_BOOT_TAKEOVER_CANDIDATE')
        self.assertTrue(result['fresh_readback_required']);self.assertFalse(result['execution_authorized'])

    def test_new_boot_never_uses_old_pid(self):
        s=frozen();s['boot_id']='different-boot'
        self.assertEqual(choose(s)['route'],'NEW_BOOT_READONLY_REBUILD')

    def test_already_default_no_replay(self):
        s=frozen();s.update(overlays={'k26-starter-kits_image_1':'applied'},module_present=False)
        self.assertEqual(choose(s)['route'],'DEFAULT_READBACK_ONLY')

    def test_unsafe_or_changed_waiter_needs_reconciliation(self):
        for key,value in [('boot_id',None),('module_refcount','1'),('cleanup_locks_owned',[False,True])]:
            s=frozen();s[key]=value;self.assertEqual(choose(s)['route'],'READONLY_RECONCILE')
        s=frozen();s['scan']['device_mappings']=[{'pid':999}]
        self.assertEqual(choose(s)['route'],'READONLY_RECONCILE')
        s=frozen();s['recovery_process']['pid']=999
        self.assertEqual(choose(s)['route'],'READONLY_RECONCILE')


if __name__=='__main__':unittest.main(verbosity=2)
