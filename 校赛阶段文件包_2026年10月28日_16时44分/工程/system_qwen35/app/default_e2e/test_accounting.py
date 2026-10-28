"""PC control tests, not model/BOARD substitutes."""
import io,json,threading,unittest,importlib.util
from unittest.mock import patch
from .resources import aggregate_memory,Sampler
from .provenance import capture
from .policy import ROOT,profile,registry
from ..session import Session
spec=importlib.util.spec_from_file_location('a08_report',ROOT/'platform/qwen35/a08/report.py')
report=importlib.util.module_from_spec(spec);spec.loader.exec_module(report);observed_max=report.observed_max

class Accounting(unittest.TestCase):
    def test_missing_not_zero(self):
        x=aggregate_memory({'app':{'rollup':{'Rss':5,'Pss':3},'status':{'VmSwap':0}},'gone':{'rollup':{},'status':{}}})
        self.assertIsNone(x['rss_kib']);self.assertIsNone(x['pss_kib']);self.assertEqual(x['observed_pss_kib'],3)
        self.assertEqual(x['missing_process_metrics']['pss_kib'],['gone']);self.assertEqual(x['sample_status'],'INCOMPLETE')
    def test_empty_unmeasured(self):
        self.assertIsNone(aggregate_memory({})['rss_kib']);self.assertIsNone(observed_max([None,None]))
    def test_complete_real_zero(self):
        x=aggregate_memory({'a':{'rollup':{'Rss':9,'Pss':4},'status':{'VmSwap':0}}})
        self.assertEqual(x['rss_kib'],9);self.assertEqual(x['process_swap_kib'],0);self.assertEqual(x['sample_status'],'COMPLETE')
        self.assertEqual(observed_max([None,0,4]),4)
    def test_partial_metric(self):
        x=aggregate_memory({'a':{'rollup':{'Rss':9},'status':{'VmSwap':0}}})
        self.assertEqual(x['rss_kib'],9);self.assertIsNone(x['pss_kib'])
    def test_error_retained(self):
        s=Sampler.__new__(Sampler);s.stop=threading.Event();s.f=io.StringIO();s.phase=lambda:'PLAY';s.failed_samples=0
        def fail():s.stop.set();raise PermissionError('controlled test')
        s.sample=fail;s.run();r=json.loads(s.f.getvalue())
        self.assertEqual(s.failed_samples,1);self.assertEqual(r['sample_status'],'ERROR');self.assertIsNone(r['rss_kib'])
    def test_spool_race_partial(self):
        s=Sampler.__new__(Sampler);s.pids=lambda:{};s.spool='unused';s.phase=lambda:'RESET';s.incomplete_samples=0
        s.peak=dict.fromkeys(('rss_kib','pss_kib','spool_bytes','spool_files'));s.f=io.StringIO()
        with patch('system_qwen35.app.default_e2e.resources.spool_usage',return_value=(17,1,1)):s.sample()
        r=json.loads(s.f.getvalue());self.assertIsNone(r['spool_bytes']);self.assertEqual(r['spool_observed_bytes'],17)
        self.assertEqual(s.incomplete_samples,1);self.assertIsNone(s.peak['rss_kib'])
    def test_config_identity(self):
        a=capture(profile(),registry(),'facts_v4','modules/linear_A/manifest.a08.json')
        b=capture(profile(2,1),registry(),'facts_v4','modules/linear_A/manifest.a08.json')
        self.assertNotEqual(a['run_config_sha256'],b['run_config_sha256'])
        self.assertEqual(a['model_revision'],b['model_revision']);self.assertEqual(len(a['identity_files_sha256']),6)
    def test_case_identity(self):
        a=Session('SYN_CP_01',software_test=True).snapshot();b=Session('SYN_CP_02',software_test=True).snapshot()
        self.assertTrue(a['case_version']);self.assertEqual(len(a['case_sha256']),64);self.assertNotEqual(a['case_sha256'],b['case_sha256'])
