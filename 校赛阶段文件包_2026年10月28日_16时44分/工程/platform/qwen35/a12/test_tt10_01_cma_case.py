"""Synthetic control-path tests, no model, PL, or application performance claims."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import threading
import time
import types
import unittest
from unittest import mock
import tt10_01_cma_case as adapter
from tt10_01_app import measure as actual_measure
from system_qwen35.app.checking import prompt_messages
from system_qwen35.app.domain import Transcript,load_case
from system_qwen35.app.planning import plan
from jinja2.sandbox import ImmutableSandboxedEnvironment
from tt10_01_cma_observer import PhaseObserver
from tt10_01_diag_reader import DiagnosticReader, DiagnosticBlocked
from test_tt10_01_cma_reader import fixture


class AdapterControlTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix=self._testMethodName + '-', dir=os.environ.get('SP_CMA_TEST_ARTIFACTS')))
        self.data = self.root / 'fixture-data'; self.data.mkdir(mode=0o700); fixture(self.data)
        self.side = self.root / 'new-window-s1'; self.side.mkdir(mode=0o700)
        self.bundle = self.root / 'new-bundle'; (self.bundle / 'control').mkdir(parents=True)
        base = dict(op='generate', tokens=[1, 2], max_tokens=2, profile=False,
            cache_policy='R0', prefill_chunk=256, logits_mode='all', tt10_diagnostic=True)
        requests = [dict(base, id='diag_exact'),
            dict(base, id='warm_prefix', op='cache_create', tokens=[1], cache_id='neutral'),
            dict(base, id='diag_full_R0'), dict(base, id='diag_hit', cache_policy='TT10_REQUIRE_HIT', cache_id='neutral'),
            dict(base, id='app_R0', application={}, tt10_diagnostic=False),
            dict(base, id='app_hit', application={}, cache_policy='TT10_REQUIRE_HIT', tt10_diagnostic=False)]
        template = (Path(__file__).resolve().parents[3] / 'artifacts/qwen35-0.8b/source/chat_template.jinja').read_text()
        question = '哪里痛'
        t = Transcript.parse(dict(request_id='fixture',text=question,source='typed',final=True))
        p = plan(load_case('SYN_CP_01'),t,())
        prompt = ImmutableSandboxedEnvironment().from_string(template).render(
            messages=prompt_messages(p,question),add_generation_prompt=True,enable_thinking=False)
        for request in requests[-2:]:
            request['application'] = dict(case_id='SYN_CP_01', question=question)
            request['prompt'] = prompt
        for name, obj in (('requests.json', requests), ('workloads.json', {'real_inputs': []})):
            (self.bundle / 'control' / name).write_text(json.dumps(obj))
        (self.bundle / 'control/chat_template.jinja').write_text(template)
        self.schedule = types.SimpleNamespace(blocked=False)
        self.mem = dict(MemAvailable=1500000, CmaFree=500000, CmaTotal=819200, Cached=1, Dirty=0, Writeback=0)
        self.finished = []
        self.corrupt = False
        self.lower_before_app = False
        def emit(event, **data):
            if event == 'CASE_FINISHED':
                self.finished.append(data['case_id'])
                if data['case_id'] == 'diag_hit' and self.lower_before_app:
                    self.mem['CmaFree'] = 98303
        platform = types.SimpleNamespace(gate_lock=threading.RLock(), health_schedule=self.schedule, emit=emit)
        def health():
            if self.schedule.blocked:
                raise DiagnosticBlocked('PC owner fixture latched')
        self.owner = types.SimpleNamespace(platform=platform, owner_check=lambda: None, health=health)
        test = self
        class Worker:
            task10_launch_ns = time.monotonic_ns()
            real = False
            runs = 0
            loads = 0
            sequence = 0
            quarantined = False
            delivery_cancelled = False
            process = types.SimpleNamespace(pid=os.getpid(), poll=lambda: None)
            def __init__(self):
                self.sent = []
                self.responses = [dict(type='ready', execution_kind='CPU_REFERENCE',
                    prefix_cache={'enabled': True, 'binding_sha256': 'PC_FIXTURE'})]
            def send(self, request):
                self.sent.append(request['id'])
                if 'application' in request:
                    raise AssertionError('application must be rejected before send in these tests')
                src = 'diag_full_R0' if request['id'] == 'diag_exact' else request['id']
                shutil.copytree(test.data / src / 'diag', Path(request['diagnostic_dir']))
                if request['id'] == 'diag_hit' and test.corrupt:
                    (Path(request['diagnostic_dir']) / 'x.bin').write_bytes(b'efgi')
                self.responses.append(test.result(request['id']))
        self.worker = Worker()
        reference = self.root / 'old-reference/run-v1/s1/diag_exact'
        shutil.copytree(self.data / 'diag_full_R0/diag', reference / 'diag')
        (reference / 'result.json').write_text(json.dumps(self.result('diag_exact')))
        ob = types.SimpleNamespace(ENABLED=False, start_request=lambda r: None, finish_request=lambda *a: None)
        def save(path, obj):
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('x') as f:
                json.dump(obj, f)
        self.api = dict(save=save, sha=lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest(),
            receive=lambda *a: self.worker.responses.pop(0), validate_bo=lambda r: [], BUNDLE=self.bundle,
            SPEC=dict(request_limit=6, prompt_token_limit=128, output_token_limit=2, prefix_tokens=1,
                      legacy_reference=str(self.root / 'old-reference')), ob=ob)

    def result(self, name):
        return dict(id=name, type='cache_created' if name == 'warm_prefix' else 'result', status='OK',
            state_cleared_before_response=True, state_position_before_clear=1, state_position_after_clear=-1,
            prefix_cache_request={'new_tokens': 1 if name == 'diag_hit' else 2},
            prefix_cache={'entries': [{'tokens': 1}], 'binding_sha256': 'PC_FIXTURE'}, capture_ms=0,
            output_tokens=[10, 11], text='PC_CONTROL_FIXTURE', eos=True, decode_calls=1,
            last_prompt_logits_fnv64='fixture', last_prompt_logits_sha256=hashlib.sha256(bytes([2]) * 993280).hexdigest(),
            state_fingerprint={'bytes': 17, 'fnv64': 'fixture', 'sha256': 'f' * 64})

    def tearDown(self):
        if not os.environ.get('SP_CMA_TEST_ARTIFACTS'):
            shutil.rmtree(self.root)

    def run_adapter(self):
        def path(value):
            if str(value) == '/proc/meminfo':
                return types.SimpleNamespace(read_text=lambda: '\n'.join(k + ': ' + str(v) + ' kB' for k, v in self.mem.items()))
            return Path(value)
        def observer(owner, worker, root, real):
            return PhaseObserver(owner, worker, root, real=real,
                sample=lambda pids, full: dict(observed_monotonic_ns=time.monotonic_ns(), memory_kib=dict(self.mem), processes={'PC_FIXTURE': {}}))
        self.application_enter_ns = None
        def measure_application(*args):
            self.application_enter_ns = time.monotonic_ns()
            return actual_measure(*args)
        with mock.patch.object(adapter, 'Path', path), \
             mock.patch.object(adapter, 'DiagnosticReader', lambda *a, **kw: DiagnosticReader(*a, expected_uid=os.getuid(), **kw)), \
             mock.patch.object(adapter, 'PhaseObserver', observer), \
             mock.patch.object(adapter, 'measure', side_effect=measure_application) as measure:
            with self.assertRaises((DiagnosticBlocked, AssertionError)):
                adapter.execute_case(self.worker, self.owner, self.side, real=False, api=self.api)
            if self.corrupt:measure.assert_not_called()
            else:measure.assert_called_once()
        self.assertTrue(self.schedule.blocked)
        self.assertEqual(self.worker.sent, ['diag_exact', 'warm_prefix', 'diag_full_R0', 'diag_hit'])
        self.assertTrue((self.side / 'diag_hit/diag/x.bin').exists())

    def test_corrupt_prefix_stream_rejected_before_application(self):
        self.corrupt = True
        self.run_adapter()
        gate = json.loads((self.side / 'diag_hit/prefix-numerical-gate.json').read_text())
        self.assertFalse(gate['all_bytes']['equal'])
        self.assertTrue(gate['result']['equal'])
        self.assertNotIn('diag_hit', self.finished)

    def test_low_cma_after_equal_gate_rejected_before_application_send(self):
        self.lower_before_app = True
        self.run_adapter()
        gate = json.loads((self.side / 'diag_hit/prefix-numerical-gate.json').read_text())
        self.assertTrue(gate['all_bytes']['equal'])
        rows = [json.loads(x) for x in (self.side / 'diagnostic-resources.jsonl').read_text().splitlines()]
        refusal = next(r for r in rows if r['event'] == 'BEFORE_APPLICATION_SEND')
        self.assertFalse(refusal['allowed'])
        self.assertEqual(refusal['sample']['memory_kib']['CmaFree'], 98303)
        self.assertGreaterEqual(refusal['monotonic_ns'], self.application_enter_ns)


if __name__ == '__main__':
    unittest.main()
