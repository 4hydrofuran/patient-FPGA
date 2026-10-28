"""Targeted Linux PC tests: owned PID/FD/thread priority and durable reply order."""
import argparse,ast,copy,importlib.util,json,os,socket,sys,tempfile,textwrap,threading,time,types,unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[3]
CANDIDATE=ROOT/'release/a12_permission_scheduler_noboard_20261027_v2/candidate-miss-probe/continuous/bundle/platform/qwen35/a12'
sys.path.insert(0,str(CANDIDATE));sys.path.insert(1,str(ROOT/'platform/qwen35/web'))
from permission_hotpath import SCHEMA,launch,policy,difference
from cpu02_support import DurableJournal
from cpu01b_supervisor import OwnedWorker
from permission_compare import compare


class Scheduling(unittest.TestCase):
    def test_baseline_argv_is_unchanged(self):
        command,profile=launch(['/x/native','model','4'],dict(schema=SCHEMA,worker_nice_adjustment=0))
        self.assertEqual(command,['/x/native','model','4']);self.assertEqual(profile['worker_nice_adjustment'],0)

    def test_policy_does_not_accept_priority_boosts_or_bool(self):
        for value in (-10,1,11,True,None):
            with self.subTest(value=value),self.assertRaises(ValueError):
                launch(['/x/native'],dict(schema=SCHEMA,worker_nice_adjustment=value))

    def test_exact_permission_delta_includes_final_record(self):
        a=dict(calls=10,owner_check_ms=1,health_check_ms=2,durable_permission_record_ms=3)
        b=dict(calls=12,owner_check_ms=2,health_check_ms=4,durable_permission_record_ms=6)
        self.assertEqual(difference(a,b)['durable_permission_record_ms'],3)
        with self.assertRaises(ValueError):difference(b,a)

    def test_runtime_copy_paths_do_not_break_native_argument_comparison(self):
        _,a=launch(['/runtime/baseline/bin/native','model','4'],dict(schema=SCHEMA,worker_nice_adjustment=0))
        _,b=launch(['/runtime/candidate/bin/native','model','4'],dict(schema=SCHEMA,worker_nice_adjustment=10))
        self.assertEqual(a['native_semantic_argv_sha256'],b['native_semantic_argv_sha256'])

    def test_nice_exec_preserves_owned_pid_fd_and_future_thread_priority(self):
        child=textwrap.dedent('''\
            #!/usr/bin/python3
            import json,os,socket,sys,threading
            peer=socket.socket(fileno=int(os.environ['SP_A12_CONTROL_FD']))
            stream=peer.makefile('r');pid=os.getpid()
            def request(phase,sequence,job):
                peer.sendall((json.dumps(dict(phase=phase,sequence=sequence,job=job,pid=pid))+'\\n').encode())
                reply=json.loads(stream.readline());assert reply['allow'] and reply['sequence']==sequence
            request('router_open',1,0);request('device_open',1,0)
            request('weight_load',2,1);request('submit',3,1)
            priorities=[]
            t=threading.Thread(target=lambda:priorities.append(os.getpriority(os.PRIO_PROCESS,0)))
            t.start();t.join()
            print(json.dumps(dict(type='ready',pid=pid,nice=os.getpriority(os.PRIO_PROCESS,0),thread_nice=priorities[0])),flush=True)
            for line in sys.stdin:
                if json.loads(line).get('op')=='shutdown':break
            request('router_close',2,0)
            stream.close();peer.close()
            ''')
        manager_nice=os.getpriority(os.PRIO_PROCESS,0)
        for adjustment in (0,10):
            with self.subTest(adjustment=adjustment),tempfile.TemporaryDirectory() as d:
                root=Path(d);(root/'bin').mkdir();(root/'control').mkdir()
                binary=root/'bin/qwen35-a12';binary.write_text(child);binary.chmod(0o700)
                (root/'control/permission-runtime.json').write_text(json.dumps(dict(schema=SCHEMA,worker_nice_adjustment=adjustment)))
                w=OwnedWorker([str(binary)],directory=root/'worker',env=dict(os.environ),health=lambda:dict(fresh=True),
                    max_runs=1,max_loads=1,expires=time.monotonic()+10,owner_check=lambda:None)
                try:
                    ready=w.get(3)
                    self.assertEqual(ready['pid'],w.process.pid)
                    self.assertEqual(ready['nice'],min(19,manager_nice+adjustment))
                    self.assertEqual(ready['thread_nice'],ready['nice'])
                    self.assertEqual(w.runs,1);self.assertEqual(w.loads,1)
                    self.assertTrue(w.close(3));self.assertEqual(w.process.returncode,0)
                    self.assertEqual(w.permission_metrics['calls'],5)
                    self.assertFalse(w.quarantined)
                finally:
                    if not w.closed:w.close(3)
        self.assertEqual(os.getpriority(os.PRIO_PROCESS,0),manager_nice)


class Persistence(unittest.TestCase):pass


class Comparison(unittest.TestCase):
    def pair(self):
        row=dict(case_id='PC_FIXTURE',case_sha256='case',question='fixture',repeat=0,prompt_sha256='prompt',
            answer='fixture answer',output_tokens=[1],actual_backend='CPU_REFERENCE',physical_T_calls={'8':1},
            native_pl_calls=0,answer_source='MODEL',answer_cache_used=False,eos=True,
            prefix_binding_sha256='binding',model_identity={'model':'fixture'},prefix={'hit':True,'reused_tokens':34},
            native_request_wall_ms=10,permission_wait_ms=0,permission={'durable_permission_record_ms':0},
            launch={'worker_nice_adjustment':0,'native_semantic_argv_sha256':'same'})
        a={'rows':[row]};b=copy.deepcopy(a);b['rows'][0]['launch']['worker_nice_adjustment']=10
        return a,b
    def test_cpu_comparison_never_claims_board_latency(self):
        result=compare(*self.pair());self.assertEqual(result['BOARD'],'NOT_TESTED');self.assertIsNone(result['board_latency_ms'])
    def test_cache_and_template_are_not_fresh_model_samples(self):
        for key,value in (('answer_cache_used',True),('answer_source','MODEL_CACHE'),('answer_source','TEMPLATE')):
            a,b=self.pair();b['rows'][0][key]=value
            with self.assertRaises(ValueError):compare(a,b)
    def test_changed_model_output_or_call_shape_rejects_pair(self):
        for key,value in (('output_tokens',[2]),('native_pl_calls',1),('model_identity',{'model':'changed'}),('physical_T_calls',{'1':8})):
            a,b=self.pair();b['rows'][0][key]=value
            with self.assertRaises(ValueError):compare(a,b)

# Reuse the original four relevant tests verbatim against the changed bundle.
prior=ast.parse((ROOT/'platform/qwen35/a12/cpu02_pc.py').read_text(encoding='utf-8'))
names={'test_journal_one_fsync_per_append_and_directory_once',
       'test_journal_missing_truncated_replaced_and_symlink_latch',
       'test_journal_partial_write_and_no_progress','test_permission_waits_for_fsync'}
for parent in ast.walk(prior):
    if isinstance(parent,ast.ClassDef) and parent.name=='Additional':
        for node in parent.body:
            if isinstance(node,ast.FunctionDef) and node.name in names:
                module=ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[]))
                namespace={};exec(compile(module,'original_cpu02_persistence_test','exec'),globals(),namespace)
                setattr(Persistence,node.name,namespace[node.name])


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(c) for c in (Scheduling,Persistence,Comparison))
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    report=dict(status='PASS_PC_PERMISSION_SCHEDULING_AND_DURABILITY' if result.wasSuccessful() else 'FAIL_PC',
        tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),BOARD='NOT_TESTED',board_actions=0)
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2)+'\n')
    sys.exit(0 if result.wasSuccessful() else 1)
