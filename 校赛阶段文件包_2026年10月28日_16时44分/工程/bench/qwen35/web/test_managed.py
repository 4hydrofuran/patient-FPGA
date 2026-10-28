"""PC wiring tests with the real NativePL and delivered correlation class.

The worker below is a protocol fixture, not a CPU model or real PL execution.
"""
import ast
import copy
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

from system_qwen35.app import native_pl
from system_qwen35.app.web_managed import OwnerBoundModel, create_app

ROOT = Path(__file__).resolve().parents[3]


class Worker:
    def __init__(self):
        self.sent = []
        self.close_count = 0
        self.bad_id = False
        self.token_before_result = False
        self.token_delivered = False

    def send(self, request):
        self.sent.append(copy.deepcopy(request))
        self.token_delivered = False

    def get(self, timeout):
        if self.token_before_result and not self.token_delivered:
            self.token_delivered=True
            return dict(type='token',id=self.sent[-1]['id'],index=0,token=1)
        return dict(type='result', id='foreign' if self.bad_id else self.sent[-1]['id'],
                    status='OK', text='fixture answer', eos=True, partial_output_usable=True,
                    state_cleared_before_response=True, state_position_after_clear=-1,
                    bridge={'a12_route': {'execution_kind': 'FPGA_REAL'}})

    def close(self):
        self.close_count += 1


class ManagedTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        template = root/'artifacts/qwen35-0.8b/source/chat_template.jinja'
        template.parent.mkdir(parents=True)
        template.write_text('{{ '+json.dumps('fixture<think>\n\n</think>\n\n')+' }}', encoding='utf-8')
        ready = dict(type='ready', execution_kind='FPGA_REAL', physical_ubatch=8,
                     cache_policy='R0_CLEAR_ALL_REPLAY',
                     attention_schedule='SIMD_QUERY_ORDER_NO_SPLIT_KV_OR_QUERY_TILING',
                     non_mlp_projection_schedule='STABLE_PER_TOKEN_SIMD_GEMV',
                     bridge={'a12_route': {'a12_route_scope': 'all',
                             'contract_sha256': '83bd402b39350710d8689d50f79296e9625e9c75ccb0ecee145f08067c4ee3b6'}})
        self.worker = Worker()
        with patch.object(native_pl, 'ROOT', root):
            self.native = native_pl.NativePL(self.worker, ready, max_output_tokens=24)
        self.state = dict(ready=True, remaining=240.0)
        self.model = OwnerBoundModel(self.native, is_ready=lambda: self.state['ready'],
                                    remaining_seconds=lambda: self.state['remaining'])

    def test_actual_native_and_delivered_correlation_keep_ids_and_state(self):
        source = json.loads((ROOT/'evidence/frontend_board_A/20261026-inspect-v1/board-sources.json').read_text(encoding='utf-8'))
        tree = ast.parse(source['web_gateway/src/patient_web/managed.py'])
        node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'CorrelatedPL')
        scope = {}
        exec(compile(ast.Module(body=[node], type_ignores=[]), '<delivered-CorrelatedPL>', 'exec'), scope)
        correlated = scope['CorrelatedPL'](self.model)
        correlated.trace_context = dict(session_id='session', request_id='web1', epoch=2)
        answer = correlated.generate([dict(role='user', content='fixture')], timeout_s=180)
        self.assertEqual(answer['id'], 'session:web1')
        self.assertEqual(answer['native_request_id'], 'a12-1')
        self.assertEqual(answer['actual_backend'], 'FPGA_REAL')
        self.assertEqual(self.worker.sent[0]['session_epoch'], 2)
        self.assertEqual(self.worker.sent[0]['cache_policy'], 'R0')
        self.assertIsNone(self.native.trace_context)
        self.assertEqual(self.worker.close_count, 0)

    def test_owner_not_ready_makes_no_worker_request(self):
        self.state['ready'] = False
        self.assertFalse(self.model.available())
        with self.assertRaisesRegex(RuntimeError, 'not accepting'):
            self.model.generate([], 180)
        self.assertEqual(self.worker.sent, [])
        self.assertFalse(self.native.broken)

    def test_short_budget_does_not_extend_window_or_submit(self):
        self.state['remaining'] = 179
        self.assertFalse(self.model.available())
        with self.assertRaisesRegex(RuntimeError, 'shorter'):
            self.model.generate([], 180)
        self.assertEqual(self.worker.sent, [])
        self.assertEqual(self.state['remaining'], 179)

    def test_invalid_budget_is_not_available(self):
        for value in (float('inf'), float('nan'), True, None, -1):
            self.state['remaining'] = value
            self.assertFalse(self.model.available())

    def test_native_failure_is_preserved_and_not_restarted(self):
        self.worker.bad_id = True
        with self.assertRaisesRegex(RuntimeError, 'identity differs'):
            self.model.generate([], 180)
        self.assertTrue(self.native.broken)
        self.assertFalse(self.model.available())
        self.assertEqual(len(self.worker.sent), 1)
        self.assertEqual(self.worker.close_count, 0)

    def test_factory_reuses_installed_frontend_and_live_owner_callback(self):
        captured = {}
        def factory(model, **kwargs):
            captured.update(model=model, **kwargs)
            return object()
        installed = types.SimpleNamespace(create_managed_app=factory)
        with patch('system_qwen35.app.web_managed.importlib.import_module', return_value=installed) as load:
            app = create_app(self.native, is_ready=lambda: self.state['ready'],
                             remaining_seconds=lambda: self.state['remaining'])
        self.assertIsNotNone(app)
        load.assert_called_once_with('patient_web.managed')
        self.assertEqual(captured['generation_timeout_s'], 180)
        self.assertTrue(captured['is_ready']())
        self.state['ready'] = False
        self.assertFalse(captured['is_ready']())
        self.assertEqual(self.worker.sent, [])

    def test_cpu_or_pc_fixture_cannot_enter_board_web_mode(self):
        self.native.expected = 'PC_MATH_DOUBLE'
        with self.assertRaises(ValueError):
            OwnerBoundModel(self.native, is_ready=lambda: True, remaining_seconds=lambda: 240)

    def test_first_token_and_template_timing_share_backend_clock(self):
        self.worker.token_before_result=True
        result=self.model.generate([dict(role='user',content='fixture')],180)
        clock=result['application_timing']
        self.assertLessEqual(int(clock['adapter_entered_monotonic_ns']),int(clock['worker_send_monotonic_ns']))
        self.assertLessEqual(int(clock['worker_send_monotonic_ns']),int(clock['first_token_monotonic_ns']))
        self.assertGreaterEqual(clock['first_token_from_adapter_ms'],0)
        self.assertIsNotNone(self.native.compiled_template)


if __name__ == '__main__':
    unittest.main()
