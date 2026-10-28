"""PC-only orchestration doubles and real native quantization; never FPGA evidence."""
import argparse
import copy
import ctypes as C
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import Mock
from mlp_engine import comparison,run_plan,sha,resources

ROOT=Path(__file__).resolve().parents[3]
VECTORS=ROOT/'evidence/mlp_board_A/20261023-preparation-v1/vectors-v2'
QUANT=None


class Parked(Exception):pass


class FakeNative:
    """Explicit test double: outputs fixtures, not CPU/FPGA computation."""
    def __init__(self,source,plan,quant,fault=None):
        self.source,self.plan,self.quant,self.fault=source,plan,quant,fault
        self.calls=[];self.loads=0;self.jobs=0;self.closed=False;self.handle=0
        self.live=False
    def open(self,path,out):C.cast(out,C.POINTER(C.c_void_p))[0]=123;return 0
    def load(self,ctx,n,k,w,wb,s,sb,h):
        self.loads+=1;self.handle+=1;self.live=True;C.cast(h,C.POINTER(C.c_uint64))[0]=self.handle;return 0
    def quantize(self,*args):return self.quant(*args)
    def run(self,ctx,h,t,x,xb,s,sb,y,yb,job,timeout):
        self.calls.append(('run',job,h.value));self.jobs=job
        if self.fault=='timeout':return 5
        row=self.plan['schedule'][job-1]
        data=(self.source/'vectors/pc_reference'/row['case']/'y.bin').read_bytes()
        C.memmove(y,data,len(data))
        if self.fault=='numeric':C.memset(y,0,yb)
        if self.fault=='overrun':C.memset(y.value+yb,0,1)
        return 0
    def report(self,ctx,buf,capacity,required):
        r=dict(status='READY',execution_kind='FPGA_REAL',output_consumable=True,job_id=self.jobs,
               kernel_build_id=0xB3030002,last_status_code=0,host_verified_completions=self.jobs,
               private_meta_host_seeded_count=1,weight_load_count=self.loads,TEST_DOUBLE=True)
        r.update(a11_io_bo_addresses=[0x10000,0x20000,0x30000,0x60000],
                 a11_io_bo_charged_sizes=[40960,8192,155648,8192],a11_argument_groups=[3]*6,
                 a11_explicit_bo_allocations_host_counter=4+2*self.loads,
                 a11_live_weights=[dict(handle=self.handle,addresses=[0x70000,0x80000],charged_sizes=[8192,8192])] if self.live else [],
                 owned_bo_charged_bytes=212992+(16384 if self.live else 0))
        if self.jobs and self.fault=='job':r['job_id']=999
        if self.jobs and self.fault=='build':r['kernel_build_id']=0
        if self.jobs and self.fault=='poison':r['status']='POISONED';r['output_consumable']=False
        data=json.dumps(r).encode()+b'\0';C.memmove(buf,data,len(data))
        C.cast(required,C.POINTER(C.c_uint64))[0]=len(data);return 0
    def unload(self,ctx,h):self.calls.append(('unload',h.value));self.live=False;return 0
    def close(self,ctx):self.closed=True;return 0


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='a11-PC-ONLY-')
        self.addCleanup(self.tmp.cleanup);self.source=Path(self.tmp.name)
        (self.source/'vectors').symlink_to(VECTORS,target_is_directory=True)
        (self.source/'outputs').mkdir()
        self.plan=json.loads((VECTORS/'manifest.json').read_text())
        self.quant=C.CDLL(str(QUANT)).a11_quant
        p,u,q=C.c_void_p,C.c_uint32,C.c_uint64
        self.quant.argtypes=[u,u,u,p,q,p,q,p,q];self.quant.restype=C.c_int
    def test_native_quant_all_frozen_cases(self):
        for case,info in self.plan['cases'].items():
            path=VECTORS/'inputs'/case;raw=(path/'x.f32').read_bytes()
            x=C.create_string_buffer(raw);q=C.create_string_buffer(info['files']['xq.bin']['bytes'])
            s=C.create_string_buffer(info['files']['sx.bin']['bytes'])
            self.assertEqual(self.quant(info['N'],info['K'],info['T'],x,len(raw),q,len(q),s,len(s)),0)
            self.assertEqual(q.raw,(path/'xq.bin').read_bytes());self.assertEqual(s.raw,(path/'sx.bin').read_bytes())
    def test_invalid_quant_rejected(self):
        self.assertEqual(self.quant(1,1,0,None,0,None,0,None,0),1)
    def test_bo_page_floor_and_observed_high_address_rejected(self):
        r=dict(a11_io_bo_addresses=[0x10000,0x20000,0x30000,0x60000],
               a11_io_bo_charged_sizes=[40960,8192,155648,8192],
               a11_argument_groups=[3]*6,a11_explicit_bo_allocations_host_counter=4,
               a11_live_weights=[],owned_bo_charged_bytes=212992)
        self.assertEqual(resources(r,0),r['a11_io_bo_addresses'])
        high=copy.deepcopy(r);high['a11_io_bo_addresses'][1]=34507137024
        with self.assertRaisesRegex(RuntimeError,'low-address window'):resources(high,0)
        page=copy.deepcopy(r);page['a11_io_bo_charged_sizes'][1]=4096
        page['owned_bo_charged_bytes']-=4096
        with self.assertRaisesRegex(RuntimeError,'layout differs'):resources(page,0)
    def execute(self,fault=None,permit=None):
        self.api=FakeNative(self.source,self.plan,self.quant,fault)
        self.events=[];self.park=Mock(side_effect=Parked)
        return run_plan(self.api,self.source,self.plan,permit or Mock(),
                        lambda e,**r:self.events.append((e,r)),self.park)
    def test_whole_schedule_single_context_and_resident_handles(self):
        result=self.execute();self.assertEqual((result['real_submissions'],result['weight_loads']),(23,5))
        self.assertTrue(self.api.closed);self.park.assert_not_called()
        self.assertEqual(len(list((self.source/'outputs').glob('*.f32'))),23)
        for row in result['calls']:
            self.assertTrue(row['numeric_pass'] and row['guards_intact'] and row['quant_bytes_match'])
            self.assertGreaterEqual(row['service_ms'],row['input_quant_ms']+row['api_run_ms'])
        runs=[r for r in self.api.calls if r[0]=='run']
        self.assertEqual([r[2] for r in runs],[1,2]+[3]*7+[4]*7+[5]*7)
    def test_timeout_no_close_or_next_submission(self):
        with self.assertRaises(Parked):self.execute('timeout')
        self.assertFalse(self.api.closed);self.assertEqual(self.api.jobs,1)
        self.assertEqual(list((self.source/'outputs').iterdir()),[])
    def test_wrong_job_preserved_then_stopped(self):
        with self.assertRaises(Parked):self.execute('job')
        self.assertFalse(self.api.closed);self.assertEqual(self.api.jobs,1)
        self.assertTrue((self.source/'outputs/job-01.f32').exists())
    def test_wrong_build_stops(self):
        with self.assertRaises(Parked):self.execute('build')
        self.assertFalse(self.api.closed);self.assertEqual(self.api.jobs,1)
    def test_poison_no_output_consumption(self):
        with self.assertRaises(Parked):self.execute('poison')
        self.assertFalse(self.api.closed);self.assertEqual(self.api.jobs,1)
    def test_guard_failure_stops(self):
        with self.assertRaises(Parked):self.execute('overrun')
        self.assertFalse(self.api.closed)
    def test_numeric_failure_stops(self):
        with self.assertRaises(Parked):self.execute('numeric')
        self.assertFalse(self.api.closed)
    def test_parent_stop_before_native(self):
        with self.assertRaises(Parked):self.execute(permit=Mock(side_effect=RuntimeError('STOP')))
        self.assertEqual(self.api.jobs,0);self.assertFalse(self.api.closed)
    def test_nonfinite_reference_rejected(self):
        self.assertFalse(comparison(bytes.fromhex('0000c07f')+b'\0'*124,b'\0'*128,1,1)['numeric_pass'])


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--quant',type=Path,required=True)
    args,remaining=ap.parse_known_args();QUANT=args.quant
    unittest.main(argv=[sys.argv[0],*remaining],verbosity=2)
