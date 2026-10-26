"""Targeted regression for the 2026-10-26 authorization binding failure."""
import copy
import json
from pathlib import Path
import unittest
import sys

from resource_probe_binding import bind_workload, require_manager_api, adapt_initial_scan
from resource_probe_policy import ProbeBlocked, validate_plan

BUNDLE = Path(__file__).resolve().parents[3] / 'evidence/model_pl_A/20261025-resource-probe-v1/bundle-v2'
sys.path.insert(0,str(BUNDLE/'platform/qwen35/a10'))


class BindingTests(unittest.TestCase):
    def setUp(self):
        self.requests = json.loads((BUNDLE/'control/requests.json').read_text())
        self.spec = json.loads((BUNDLE/'control/window-spec.json').read_text())

    def test_bound_workload_passes_original_policy_and_owner_authority_is_separate(self):
        before = copy.deepcopy(self.spec)
        bound = bind_workload(self.requests, self.spec, window_id='a12-authfix-regression',
                              max_session_seconds=1800)
        self.assertIs(bound['authorization_included'], False)
        self.assertEqual(validate_plan(self.requests, bound), 3024)
        self.assertEqual(self.spec, before)
        manager = (BUNDLE/'control/resource_probe_manager.py').read_text()
        self.assertIn("authorized_compute=True", manager)

    def test_original_failure_is_still_rejected_before_any_device_operation(self):
        bad = dict(self.spec, authorization_included=True)
        with self.assertRaisesRegex(ProbeBlocked, 'cannot carry compute authorization'):
            bind_workload(self.requests, bad, window_id='a12-invalid')

    def test_real_derived_manager_imports_original_application_adapter(self):
        from resource_probe_prepare import PARENT, derive_manager
        import types
        source = derive_manager((PARENT/'control/cpu01_manager.py').read_text())
        manager = types.ModuleType('authfix_manager_import_only')
        manager.__file__ = str(BUNDLE/'control/import_only_derived.py')
        exec(compile(source, manager.__file__, 'exec'), manager.__dict__)
        require_manager_api(manager)
        self.assertEqual(manager.measure_application.__module__, 'tt10_00_app')

    def test_missing_application_adapter_is_rejected_before_owner(self):
        import types
        manager = types.SimpleNamespace(save=lambda:None,receive=lambda:None,validate_bo=lambda:None)
        with self.assertRaisesRegex(ProbeBlocked, 'missing manager adapter: measure_application'):
            require_manager_api(manager)

    def test_initial_admission_reuses_existing_bounded_scan_policy(self):
        source=(BUNDLE/'platform/qwen35/a12/cpu01b_window.py').read_text()
        bound=adapt_initial_scan(source)
        self.assertEqual(bound.count('snapshot = complete_scan('),2)
        self.assertEqual(bound.count('snapshot = collect(allow_ps_display=True)'),1)

    def test_actual_transient_scan_requires_a_subsequent_complete_scan(self):
        from step07_finalize_policy import complete_scan
        from accelerator_release_gate_v2 import require_no_users
        base=BUNDLE.parents[1]/'20261026-pl-authfix-board-v1/board-receipt'
        failed=json.loads((base/'setup-attempt-01/run-v1/s2/owner-initial-resource-scan.json').read_text())
        good=json.loads((base/'bundle/run-v1/s2/owner-initial-resource-scan.json').read_text())
        snapshots=iter([failed,good]);records=[]
        result=complete_scan(lambda **kw:next(snapshots),require_no_users,good['boot_id'],lambda:True,
                             lambda event,**row:records.append(row),pause=lambda seconds:None)
        self.assertEqual(result,good)
        self.assertEqual(len(records),2)
        bad=copy.deepcopy(good);bad['device_holders']=[{'pid':123,'fd':'4','target':'/dev/dri/renderD128'}]
        calls=[]
        def held(**kw):calls.append(1);return bad
        with self.assertRaisesRegex(RuntimeError,'ACCELERATOR_DESCRIPTOR_STILL_OPEN'):
            complete_scan(held,require_no_users,good['boot_id'],lambda:True,lambda *a,**kw:None,pause=lambda seconds:None)
        self.assertEqual(len(calls),1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
