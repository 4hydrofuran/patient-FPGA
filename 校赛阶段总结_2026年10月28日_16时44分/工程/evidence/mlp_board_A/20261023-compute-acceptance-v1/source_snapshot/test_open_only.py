"""Real Linux parent/child/locks/recovery with hardware fixtures; never BOARD."""
import ctypes as C
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

# Reuse the existing integration fixture, retaining its release-failure cases.
# Its test class is compiled with explicit no-compute inputs and expectations.
text=Path(__file__).with_name('test_management.py').read_text()
text=text.replace("'a11-mlp-20261023-v9001'","'a11-open-20261023-v9001'")
text=text.replace("'mlp_engine.py'","'open_only_worker.py'")
text=text.replace('A11_MLP_BUNDLE_V1','A11_OPEN_BUNDLE_V1').replace('A11_MLP_REVIEW_V1','A11_OPEN_REVIEW_V1')
text=text.replace('max_submissions=23','max_submissions=0').replace('compute_authorized=True','compute_authorized=False')
text=text.replace('--execute-authorized-mlp-once','--execute-authorized-open-once')
text=text.replace("self.assertEqual(self.obj.permit_index,53)","self.assertFalse(hasattr(self.obj,'permit_index'))")
text=text.replace('MLP_LIFECYCLE_COMPLETE_DEFAULT_PL_RESTORED','OPEN_DIAGNOSTIC_COMPLETE_DEFAULT_PL_RESTORED')
text=text.replace("receipt['compute_runs'],23","receipt['compute_runs'],0")
start=text.index("CHILD=r'''");end=text.index("'''",start+11)+3
child="""CHILD=r'''
import json,os,sys
from pathlib import Path
args=sys.argv;req=json.loads(args[args.index('--a11-boundary-request')+1])
source=Path(args[args.index('--source')+1]);mode=args[args.index('--mode')+1]
out=Path(args[args.index('--a11-boundary-result')+1])
assert os.fstat(req['inherited_device_lock_fd']).st_ino>0
rc=8 if mode=='open_failure' else 0
r=dict(req,worker_pid=os.getpid(),status='OPEN_DIAGNOSTIC_RETURNED_NO_COMPUTE',
       real_submissions=0,release_proven=False,A11='NOT_PASSED',open_status_code=rc,
       close_status_code=None if rc else 0,normal_handles_closed=not rc,
       explicit_bo_allocations=None,physical_bo_peak_bytes=None,PC_FIXTURE_ONLY=True)
if mode=='worker_identity': r['worker_pid']+=1
if mode=='bad_numeric': r['close_status_code']=6
if mode=='two_runs': r['real_submissions']=1
out.write_text(json.dumps(r))
'''
"""
text=text[:start]+child+text[end:]
text=text.replace("if __name__=='__main__':unittest.main(argv=[sys.argv[0],*remaining],verbosity=2)",'')
exec(compile(text,str(Path(__file__).with_name('test_management.py')),'exec'),globals())

class OpenIntegration(Integration):
    def test_prepl_race_is_preserved_before_two_complete_reads(self):
        self.fault='prepl_race'
        self.assertEqual(self.execute(),0)
        events=self.events()
        scans=[r['scan'] for r in events if r['event']=='PROCESS_RELEASE_OBSERVATION']
        self.assertFalse(scans[0]['scan_complete'])
        self.assertTrue(scans[1]['scan_complete'])
        names=[r['event'] for r in events]
        quiet=names.index('PREPL_TWO_COMPLETE_QUIET_READS')
        mutation=next(i for i,r in enumerate(events) if r['event']=='COMMAND_BEGIN' and r['state_changing'])
        self.assertLess(quiet,mutation)

    def test_consumed_directory_rejected(self):
        self.assertEqual(self.execute(),0)
        with self.assertRaisesRegex(RuntimeError,'consumed'):
            trial.MlpTrial(self.source,self.review_sha)

    def test_open_error_is_preserved_and_normal_release_completes(self):
        self.fault='open_failure'
        self.assertEqual(self.execute(),0)
        result=json.loads((self.source/'mlp-receipt.json').read_text())
        self.assertEqual(result['worker_result']['open_status_code'],8)
        self.assertEqual(result['compute_runs'],0)
        self.assertEqual((self.gdm,self.overlay,self.module),('active',policy.DEFAULT,False))
        self.assertFalse((self.central/'active').exists())

    def test_actual_bundle_policy(self):
        actual=args.derived.resolve()
        # Pins patched by the integration fixture are restored for real package validation.
        from unittest.mock import patch
        with patch.object(policy,'DRIVER_SHA','388c45a0edefe221615d71ea948de00d0ef68190bdd8497b053dddf788f72b2c'), \
             patch.object(policy,'PLAN_SHA','63d13c5bb7888eb93fbf35ca5d7d6ff70d09d370f88143640bc6e457504b1604'):
            self.assertEqual(policy.verify_bundle(actual,self.digest(actual/'manifest.json'))['max_submissions'],0)

class NativeFlow(unittest.TestCase):
    def test_all_returned_errors_exit_without_close_or_submit(self):
        from open_only_worker import diagnose
        for rc in range(1,10):
            lib=Mock();lib.sp_linear_open_v1.return_value=rc
            row=diagnose(lib,Path('/CONTROL_ONLY'))
            self.assertEqual(row['open_status_code'],rc)
            lib.sp_linear_close_v1.assert_not_called()
            self.assertEqual(row['real_submissions'],0)
    def test_success_closes_once(self):
        from open_only_worker import diagnose
        lib=Mock()
        def opened(path,out): C.cast(out,C.POINTER(C.c_void_p))[0]=123;return 0
        lib.sp_linear_open_v1.side_effect=opened;lib.sp_linear_close_v1.return_value=0
        self.assertEqual(diagnose(lib,Path('/CONTROL_ONLY'))['close_status_code'],0)
        lib.sp_linear_close_v1.assert_called_once()
        lib.sp_linear_run_v1.assert_not_called()
        lib.sp_linear_load_v1.assert_not_called()
    def test_success_null_context_rejected(self):
        from open_only_worker import diagnose
        lib=Mock();lib.sp_linear_open_v1.return_value=0
        with self.assertRaises(RuntimeError):diagnose(lib,Path('/CONTROL_ONLY'))
    def test_failed_close_rejected(self):
        from open_only_worker import diagnose
        lib=Mock()
        def opened(path,out): C.cast(out,C.POINTER(C.c_void_p))[0]=123;return 0
        lib.sp_linear_open_v1.side_effect=opened;lib.sp_linear_close_v1.return_value=6
        with self.assertRaises(RuntimeError):diagnose(lib,Path('/CONTROL_ONLY'))

if __name__=='__main__':
    del Integration  # Run inherited cases once through OpenIntegration.
    unittest.main(argv=[sys.argv[0],*remaining],verbosity=2)
