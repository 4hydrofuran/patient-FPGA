"""Linux PC-only protocol, admission, persistence and package rejection tests.

PL/owner/process observations below are explicit control doubles. No BOARD
operations, device nodes, network calls, recovery or native model in this suite.
"""
import argparse
import ast
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import types
import unittest
from unittest import mock
from resource_probe_policy import (ProbeBlocked, admission, validate_plan, validate_request,
                                   ordinary_comparison)
from resource_probe_observer import ResourceObserver
from resource_probe_case import execute_case, SendGate
from resource_probe_prepare import PARENT, derive_manager
from resource_probe_entry import validate_bundle

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT/'evidence/model_pl_A/20261025-resource-probe-v1'


def plan_fixture():
    parent = json.loads((PARENT/'control/requests.json').read_text(encoding='utf-8'))
    requests = [copy.deepcopy(next(r for r in parent if r['id'] == name))
                for name in ('app_R0', 'warm_prefix', 'app_hit')]
    from resource_probe_policy import OFF
    for r in requests:
        for k in OFF:
            r.pop(k, None)
        r.update(logits_mode='final', profile=False, diagnostic_report=False, state_fingerprint=False,
                 dump_state=False, a12_consumer_trace=False)
    spec = dict(prefix_tokens=70, request_limit=3, max_runs=5000, output_token_limit=8,
                prompt_token_limit=128, resource_probe=True, authorization_included=False,
                calculated_worst_case=3024)
    return requests, spec


def inventory():
    cursor = 0x40000000
    io_sizes = [40960, 8192, 155648, 8192]
    io = []
    for n in io_sizes:
        io.append(cursor)
        cursor += n
    weights = []
    for h in range(1, 73):
        weights.append(dict(handle=h, addresses=[cursor, cursor+1835008], charged_sizes=[1835008, 114688]))
        cursor += 1949696
    return dict(owned_bo_charged_bytes=140591104, weight_load_count=72,
                a11_explicit_bo_allocations_host_counter=148, a11_argument_groups=[3]*6,
                a11_io_bo_addresses=io, a11_io_bo_charged_sizes=io_sizes, a11_live_weights=weights,
                host_verified_completions=0, execution_kind='FPGA_REAL', kernel_build_id=0xB3030002)


source = (PARENT/'control/cpu01_manager.py').read_text(encoding='utf-8')
bo_ast = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == 'validate_bo')
bo_scope = {}
exec(compile(ast.Module(body=[bo_ast], type_ignores=[]), 'frozen_validate_bo', 'exec'), bo_scope)
validate_bo = bo_scope['validate_bo']


class PolicyTests(unittest.TestCase):
    def test_exact_three_request_budget(self):
        requests, spec = plan_fixture()
        self.assertEqual(validate_plan(requests, spec), 3024)

    def test_heavy_and_unknown_flags_rejected(self):
        for key, value in [('diagnostic_dir', '/tmp/raw'), ('logits_mode', 'all'),
                           ('profile', True), ('state_fingerprint', True),
                           ('dump_state', True), ('a12_consumer_trace', True), ('teacher_tokens', [10])]:
            with self.subTest(key=key):
                requests, _ = plan_fixture()
                requests[0][key] = value
                with self.assertRaises(ProbeBlocked):
                    validate_request(requests[0])

    def test_order_input_prefix_and_caps_rejected(self):
        for kind in ('order', 'prefix', 'input', 'caps', 'budget', 'authorization'):
            with self.subTest(kind=kind):
                requests, spec = plan_fixture()
                if kind == 'order': requests.reverse()
                if kind == 'prefix': requests[1]['tokens'][0] += 1
                if kind == 'input': requests[2]['tokens'][-1] += 1
                if kind == 'caps': spec['max_runs'] = 6000
                if kind == 'budget': spec['calculated_worst_case'] -= 1
                if kind == 'authorization': spec['authorization_included'] = True
                with self.assertRaises(ProbeBlocked): validate_plan(requests, spec)

    def test_original_memory_boundaries(self):
        m = dict(MemAvailable=1114112, CmaFree=98304, CmaTotal=819200, Cached=0, Dirty=0, Writeback=0)
        admission(m)
        for k in ('MemAvailable', 'CmaFree'):
            with self.subTest(key=k), self.assertRaises(ProbeBlocked):
                admission(dict(m, **{k:m[k]-1}))
        with self.assertRaises(ProbeBlocked): admission(m, prefix=True)
        admission(dict(m, MemAvailable=1114112+192*1024), prefix=True)

    def test_missing_nan_bool_memory_rejected(self):
        for bad in (None, float('nan'), True, -1):
            with self.subTest(value=bad), self.assertRaises(ProbeBlocked):
                admission(dict(MemAvailable=2000000, CmaFree=bad, CmaTotal=819200, Cached=0, Dirty=0, Writeback=0))

    def test_actual_bo_geometry_rejects_overlap_and_high_ddr(self):
        r = inventory()
        self.assertEqual(len(validate_bo(r)), 148)
        for change in ('overlap', 'high', 'size'):
            with self.subTest(change=change):
                bad = copy.deepcopy(r)
                if change == 'overlap': bad['a11_live_weights'][0]['addresses'][0] = bad['a11_io_bo_addresses'][0]
                if change == 'high': bad['a11_live_weights'][0]['addresses'][0] = 2147483648
                if change == 'size': bad['a11_io_bo_charged_sizes'][0] -= 1
                with self.assertRaises(AssertionError): validate_bo(bad)


class CaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='a12-resource-probe-')
        self.root = Path(self.temp.name)
        self.bundle = self.root/'bundle'
        (self.bundle/'control').mkdir(parents=True)
        self.requests, self.spec = plan_fixture()
        (self.bundle/'control/requests.json').write_text(json.dumps(self.requests), encoding='utf-8')
        (self.bundle/'control/chat_template.jinja').write_text('PC_CONTROL_FIXTURE', encoding='utf-8')
        self.output = self.root/'result'
        self.output.mkdir()
        self.sample_count = 0
        self.low_at = None
        self.damage = None
        self.close_ok = True
        self.health_failure = False
        self.m = dict(MemAvailable=2000000, CmaFree=400000, CmaTotal=819200, Cached=1, Dirty=0, Writeback=0)
        self.schedule = types.SimpleNamespace(blocked=False)
        self.owner = types.SimpleNamespace(platform=types.SimpleNamespace(
            health_schedule=self.schedule, emit=lambda *a, **kw: None), owner_check=lambda: None)
        def health():
            if self.health_failure or self.schedule.blocked: raise ProbeBlocked('PC health refusal')
        self.owner.health = health
        test = self
        class Worker:
            real = True  # A protocol double only; the suite is never BOARD evidence.
            runs = 0
            loads = 72
            sequence = 74
            quarantined = False
            delivery_cancelled = False
            closed = False
            task10_launch_ns = time.monotonic_ns()
            process = types.SimpleNamespace(pid=os.getpid(), returncode=None)
            def __init__(self):
                self.sent = []
                self.queue = [dict(type='ready', execution_kind='FPGA_REAL', physical_ubatch=8,
                    prefix_cache=dict(enabled=True, binding_sha256='b'*64), bridge={'a12_route':inventory()})]
            def send(self, req):
                self.sent.append(req['id'])
                warm = req['id'] == 'warm_prefix'
                new = 70 if warm else 37 if req['id'] == 'app_hit' else 107
                decode = 0 if warm else 1
                self.runs += 72*((new+7)//8+decode)
                self.sequence += 72*((new+7)//8+decode)
                route = inventory();route['host_verified_completions'] = self.runs
                r = dict(type='cache_created' if warm else 'result', id=req['id'], status='OK',
                    state_cleared_before_response=True, state_position_after_clear=-1, state_position_before_clear=108,
                    prefix_cache=dict(binding_sha256='b'*64, entries=[dict(tokens=70)] if self.runs>1080 else []),
                    prefix_cache_request=dict(hit=req['id']=='app_hit', reused_tokens=70 if req['id']=='app_hit' else 0, new_tokens=new),
                    decode_calls=decode, output_tokens=[10,11], text='PC_CONTROL_FIXTURE', eos=True,
                    last_prompt_logits_fnv64=123, last_prompt_logits_sha256='a'*64, bridge={'a12_route':route})
                if self.damage == 'count':r['bridge']['a12_route']['host_verified_completions'] += 1
                if req['id'] == 'app_hit' and test.damage == 'logits':r['last_prompt_logits_sha256']='c'*64
                if test.damage == 'state':r['state_cleared_before_response']=False
                if test.damage == 'backend':r['bridge']['a12_route']['execution_kind']='CPU_REFERENCE'
                self.queue.append(r)
            def close(self, timeout):
                self.closed = test.close_ok
                self.process.returncode = 0 if test.close_ok else None
                return test.close_ok
        # Mutable fixture data lives on the test, not on real worker classes.
        Worker.damage = property(lambda w: test.damage)
        self.worker = Worker()
        def save(p, obj):
            p.parent.mkdir(parents=True, exist_ok=True)
            with p.open('x', encoding='utf-8') as f:json.dump(obj, f, allow_nan=False)
        def sample(pids):
            self.sample_count += 1
            mem = dict(self.m)
            if self.sample_count == self.low_at:mem['CmaFree']=98303
            return dict(memory_kib=mem, processes={'PC_CONTROL_FIXTURE':{}})
        def receive(*args):return self.worker.queue.pop(0)
        def measure(gate, get, template, frozen):
            begin=time.monotonic_ns()
            gate.send({k:v for k,v in frozen.items() if k not in ('tokens','application')})
            result=get();end=time.monotonic_ns()
            return result, [], begin, end, dict(answer_source='MODEL', eos=True,
                candidate_check={'status':'pass'}, final_check={'status':'pass'},
                TTFT_app_ms=1, complete_app_ms=2, stamps={'request_received_ns':begin,'worker_send_ns':begin,'checked_ns':end})
        self.api=dict(save=save, BUNDLE=self.bundle, SPEC=self.spec, receive=receive,
            validate_bo=validate_bo, measure_application=measure,
            resource_observer=lambda o,w,p:ResourceObserver(o,w,p,sample=sample))

    def tearDown(self):self.temp.cleanup()

    def run_case(self):return execute_case(self.worker,self.owner,self.output,real=True,api=self.api)

    def test_ordinary_pair_completes_without_diagnostics(self):
        self.run_case()
        self.assertEqual(self.worker.sent,['app_R0','warm_prefix','app_hit'])
        self.assertTrue(self.worker.closed)
        self.assertFalse(self.schedule.blocked)
        summary=json.loads((self.output/'resource-probe-summary.json').read_text())
        self.assertEqual(summary['actual_calls'],2160)
        self.assertLessEqual(summary['observation_bytes'],24*8192)
        self.assertEqual(summary['observation_rows'],8)
        self.assertEqual(summary['full_numeric_acceptance'],'NOT_PERFORMED')
        clock=json.loads((self.output/'app_hit/application-timing.json').read_text())
        self.assertTrue(clock['cache']['hit'])
        self.assertEqual(clock['cache']['new_tokens'],37)
        self.assertFalse(any(p.name=='diag' or p.suffix in ('.f32','.bin') for p in self.output.rglob('*')))

    def test_low_cma_rejected_before_hit_send_and_failure_preserved(self):
        self.low_at=6
        with self.assertRaises(ProbeBlocked):self.run_case()
        self.assertEqual(self.worker.sent,['app_R0','warm_prefix'])
        self.assertFalse(self.worker.closed)
        self.assertTrue(self.schedule.blocked)
        rows=[json.loads(x) for x in (self.output/'probe-resources.jsonl').read_text().splitlines()]
        self.assertEqual(rows[-1]['sample']['memory_kib']['CmaFree'],98303)
        self.assertTrue((self.output/'app_R0/result.json').exists())
        self.assertTrue((self.output/'PROBE_FAILURE.json').exists())

    def test_failure_not_retried_even_when_later_memory_recovers(self):
        self.low_at=2
        with self.assertRaises(ProbeBlocked):self.run_case()
        self.low_at=None
        self.assertEqual(self.worker.sent,[])
        self.assertTrue(self.schedule.blocked)
        with self.assertRaises(ProbeBlocked):self.owner.health()

    def test_wrong_counts_state_backend_and_logits_latch(self):
        # Run separate fixtures to retain every rejected result within its own run.
        for damage in ('count','state','backend','logits'):
            with self.subTest(damage=damage):
                case=CaseTests(methodName='test_ordinary_pair_completes_without_diagnostics')
                case.setUp()
                try:
                    case.damage=damage
                    with self.assertRaises(ProbeBlocked):case.run_case()
                    self.assertTrue(case.schedule.blocked)
                    self.assertFalse(case.worker.closed)
                    self.assertTrue((case.output/'PROBE_FAILURE.json').exists())
                    self.assertTrue(any(case.output.glob('*/result.json')))
                finally:case.tearDown()

    def test_health_refusal_and_journal_io_failure_prevent_send(self):
        self.health_failure=True
        with self.assertRaises(ProbeBlocked):self.run_case()
        self.assertEqual(self.worker.sent,[])
        self.assertTrue(self.schedule.blocked)

    def test_fsync_failure_is_not_reported_as_success(self):
        with mock.patch('resource_probe_observer.os.fsync',side_effect=OSError('PC disk failure')):
            with self.assertRaises(OSError):self.run_case()
        self.assertEqual(self.worker.sent,[])
        self.assertTrue(self.schedule.blocked)
        self.assertFalse(self.worker.closed)

    def test_close_timeout_retains_failure(self):
        self.close_ok=False
        with self.assertRaises(ProbeBlocked):self.run_case()
        self.assertFalse(self.worker.closed)
        self.assertTrue(self.schedule.blocked)
        self.assertFalse((self.output/'exit.json').exists())

    def test_unsafe_replay_and_request_mutation_prevented(self):
        observer=ResourceObserver(self.owner,self.worker,self.output,sample=lambda p:dict(memory_kib=self.m,processes={}))
        try:
            gate=SendGate(self.worker,observer);req=copy.deepcopy(self.requests[0]);gate.arm(req)
            native={k:v for k,v in req.items() if k not in ('tokens','application')}
            with self.assertRaises(ProbeBlocked):gate.send(dict(native,max_tokens=7))
            gate.send(native)
            with self.assertRaises(ProbeBlocked):gate.send(native)
            self.assertEqual(self.worker.sent,['app_R0'])
        finally:observer.close()

    def test_journal_replacement_latches_without_losing_original(self):
        observer=ResourceObserver(self.owner,self.worker,self.output,sample=lambda p:dict(memory_kib=self.m,processes={}))
        try:
            observer.checkpoint('READY')
            old=self.output/'preserved-original.jsonl'
            observer.path.rename(old)
            observer.path.write_text('',encoding='utf-8')
            with self.assertRaises(ProbeBlocked):observer.checkpoint('CHANGED')
            self.assertTrue(self.schedule.blocked)
            self.assertTrue(old.read_text())
            self.assertEqual(self.worker.sent,[])
        finally:observer.close()

    def test_observation_budget_stops_growth(self):
        observer=ResourceObserver(self.owner,self.worker,self.output,sample=lambda p:dict(memory_kib=self.m,processes={}))
        try:
            for _ in range(observer.MAX_ROWS):observer.checkpoint('PC_BUDGET_FIXTURE')
            before=observer.path.stat().st_size
            with self.assertRaises(ProbeBlocked):observer.checkpoint('OVER_BUDGET')
            self.assertEqual(observer.path.stat().st_size,before)
            self.assertLessEqual(before,observer.MAX_ROWS*observer.MAX_ROW_BYTES)
            self.assertTrue(self.schedule.blocked)
        finally:observer.close()


class ManagerTests(unittest.TestCase):
    def test_derived_main_is_unbound_and_safety_helpers_unchanged(self):
        before=(PARENT/'control/cpu01_manager.py').read_text(encoding='utf-8')
        after=derive_manager(before)
        tree=ast.parse(after)
        main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
        scope={};exec(compile(ast.Module(body=[main],type_ignores=[]),'unbound_main','exec'),scope)
        with self.assertRaises(PermissionError):scope['main']()
        self.assertNotIn("run_case(cpu",after)
        self.assertNotIn("review_archive_cache(rows)",after)
        self.assertNotIn("owner.finish(cpu)",after)
        self.assertIn('require_release(scan, refs, allowed, boot_id=boot)',after)
        self.assertIn('owner.retain_until_finished(reason)',after)

    def test_missing_anchor_stops_derivation(self):
        before=(PARENT/'control/cpu01_manager.py').read_text(encoding='utf-8')
        with self.assertRaises((ProbeBlocked,ValueError)):
            derive_manager(before.replace("        s1 = run / 's1'",'        changed = True'))


class PackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.bundle=TEST_BUNDLE

    def test_package_plan_only_and_no_execute_command(self):
        self.assertEqual(validate_bundle(self.bundle)['status'],'PLAN_ONLY_UNBOUND_PACKAGE_VERIFIED')
        entry=self.bundle/'platform/qwen35/a12/resource_probe_entry.py'
        p=subprocess.run([sys.executable,'-B',str(entry),'--bundle',str(self.bundle)],capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr)
        p=subprocess.run([sys.executable,'-B',str(entry),'--execute'],capture_output=True,text=True)
        self.assertEqual(p.returncode,2)
        self.assertFalse((self.bundle/'run-v1').exists())

    def test_isolated_manager_import_has_no_board_or_process_side_effect(self):
        script=r'''
import importlib.util,sys
def deny(event,args):
    if event in ('subprocess.Popen','os.system','socket.connect'):
        raise AssertionError('forbidden process/network operation during import')
    if event=='open' and isinstance(args[0],str) and args[0].startswith(('/dev/','/sys/','/proc/','/etc/','/var/lock/')):
        raise AssertionError('forbidden board observation during import: '+args[0])
sys.addaudithook(deny)
spec=importlib.util.spec_from_file_location('unbound_resource_probe_manager',sys.argv[1])
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
assert module.SPEC['request_limit']==3
try:module.main()
except PermissionError:pass
else:raise AssertionError('unbound manager executed')
print('ISOLATED_IMPORT_NO_BOARD_ACTIONS_PASS')
'''
        p=subprocess.run([sys.executable,'-B','-c',script,str(self.bundle/'control/resource_probe_manager.py')],
                         capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertIn('ISOLATED_IMPORT_NO_BOARD_ACTIONS_PASS',p.stdout)

    def test_manifest_unsafe_path_rejected(self):
        # Patch only the parsed manifest or inventory; frozen package bytes stay read-only.
        import resource_probe_entry as entry
        original=entry.json.loads
        manifest=original((self.bundle/'manifest.json').read_text())
        bad=copy.deepcopy(manifest);bad['files'][0]['path']='../outside'
        with mock.patch.object(entry.json,'loads',side_effect=lambda t:bad if t.startswith('{\n  "schema_version"') else original(t)):
            with self.assertRaises(ProbeBlocked):entry.validate_bundle(self.bundle)


def main():
    global TEST_BUNDLE
    parser=argparse.ArgumentParser();parser.add_argument('--evidence',type=Path,required=True)
    parser.add_argument('--bundle',type=Path,default=BASE/'bundle-v2')
    args=parser.parse_args();args.evidence.mkdir(parents=True,exist_ok=False)
    TEST_BUNDLE=args.bundle
    stream=io.StringIO();suite=unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    text=stream.getvalue();(args.evidence/'unittest.txt').write_text(text,encoding='utf-8')
    report=dict(domain='PC_CONTROL_DOUBLES_LINUX',tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),
                status='PASS' if result.wasSuccessful() else 'FAIL',BOARD='NOT_TESTED',new_PL_calls=0)
    (args.evidence/'RESULT.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(text);print(json.dumps(report));return 0 if result.wasSuccessful() else 1


if __name__=='__main__':raise SystemExit(main())
