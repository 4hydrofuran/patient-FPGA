"""Unmodified frozen gate bodies, fixtures only; never initialize a board manager."""
import ast
import errno
import io
from pathlib import Path
import sys
import tempfile
import time
import types
import unittest

from health_fence import HealthFence,HealthBlocked
from health_fence_evidence import ROOT,OUT,save

BUNDLE=ROOT/'evidence/model_pl_A/20261025-resource-probe-v1/bundle-v2'
sys.path.insert(0,str(BUNDLE/'platform/qwen35/a12'))
sys.path.insert(0,str(BUNDLE/'control/support'))
import cpu01b_observer as ob
ob.ENABLED=False
from cpu01b_health import PersistentKmsg,StableTemperatures,HealthBlocked as OldBlocked
from cpu01b_kernel_gate import MinimalGate
from capacity_policy import admission


class FrozenHealthTests(unittest.TestCase):
    def monitor(self,observe):
        m=HealthFence(observe);self.addCleanup(m.stop);return m

    def live(self,memory):
        # Only compile this exact body. No imports/constructors/platform commands
        # from resource_probe_manager are executed.
        tree=ast.parse((BUNDLE/'control/resource_probe_manager.py').read_bytes())
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Platform')
        node=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='live_health')
        class File:
            def __init__(self,path):self.path=path
            def read_text(self):
                if self.path.endswith('boot_id'):return 'fixture-boot\n'
                return ''.join(f'{k}: {v} kB\n' for k,v in memory.items())
        temperatures=types.SimpleNamespace(read=lambda:[54999],verify_topology=lambda:None)
        scope=dict(ob=ob,time=time,Path=File,HealthBlocked=OldBlocked,
            StableTemperatures=lambda:temperatures,admission=admission)
        exec(compile(ast.Module(body=[node],type_ignores=[]),'unmodified_frozen_live_health','exec'),scope)
        obj=types.SimpleNamespace(stable_temperatures=temperatures,topology_checked_ns=0,
            health_parts=dict(temperature_memory_ms=0.0))
        return lambda:scope['live_health'](obj,'fixture-boot',True)

    def test_original_memory_and_cma_floors_unchanged_and_already_charged(self):
        okay=dict(MemAvailable=1114112,CmaFree=98304,CmaTotal=131072)
        m=self.monitor(self.live(okay));t=m.fence();m.authorize(t)
        import json
        r=json.loads(t.observation)['actual_reserve'];self.assertTrue(r['allowed'])
        self.assertEqual(r['pending_bo_bytes'],0);self.assertEqual(r['required_CmaFree_kib'],98304)
        for key in ('MemAvailable','CmaFree'):
            memory=dict(okay);memory[key]-=1;m=self.monitor(self.live(memory))
            with self.assertRaises(HealthBlocked):m.fence()
            self.assertIn('extra reserve',m.status()['fault'])

    def test_missing_resource_and_changed_boot_never_authorize(self):
        m=self.monitor(self.live(dict(MemAvailable=1114112,CmaTotal=131072)))
        with self.assertRaises(HealthBlocked):m.fence()
        gate=MinimalGate();self.assertTrue(gate.observe_action('a','<6>[ 0.000001] ready\n',None,'none')['allowed'])
        def observe():
            r=gate.observe_action('b',gate.previous,None,'none')
            if not r['allowed']:raise OldBlocked(r['reason'])
            return r
        m=self.monitor(observe)
        with self.assertRaises(HealthBlocked):m.fence()
        self.assertTrue(gate.blocked)

    def test_frozen_temperature_gate_and_topology_checked_from_private_fixtures(self):
        with tempfile.TemporaryDirectory(prefix='a12-temp-fixture-') as d:
            root=Path(d);h=root/'hwmon0';h.mkdir();p=h/'temp1_input';p.write_text('54999\n')
            temps=StableTemperatures(root);self.assertEqual(temps.read(),[54999])
            p.write_text('55000\n');m=self.monitor(lambda:dict(temperatures=temps.read()))
            with self.assertRaises(HealthBlocked):m.fence()
            p.write_text('50000\n');(h/'temp2_input').write_text('50000\n')
            def observe():temps.verify_topology();return dict(temperatures=temps.read())
            m=self.monitor(observe)
            with self.assertRaises(HealthBlocked):m.fence()

    def test_kmsg_new_warning_and_sequence_loss_latch_without_archiving(self):
        for fault in ('warning','gap'):
            records=[b'6,1,1,-;ready\n'];gate=MinimalGate()
            def read():
                if records:return records.pop(0)
                raise BlockingIOError(errno.EAGAIN,'fixture drained')
            reader=PersistentKmsg(read=read);self.addCleanup(reader.close)
            def observe():
                raw=reader.drain();r=gate.observe_action('fixture-boot',raw,None,'none')
                if not r['allowed']:raise OldBlocked(r['reason'])
                return dict(kernel_sha256=__import__('hashlib').sha256(raw.encode()).hexdigest())
            m=self.monitor(observe);m.authorize(m.fence())
            records.append(b'4,2,2,-;WARNING: fixture fault\n' if fault=='warning' else b'6,3,2,-;ready\n')
            with self.assertRaises(HealthBlocked):m.fence()
            self.assertEqual(m.status()['counters']['authorizations'],1)


if __name__=='__main__':
    target=OUT/'frozen-gate-tests-01';target.mkdir(exist_ok=False);stream=io.StringIO()
    r=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    (target/'unittest.txt').write_text(stream.getvalue(),encoding='utf-8')
    save(target/'RESULT.json',dict(status='PASS' if r.wasSuccessful() else 'FAIL',tests=r.testsRun,
        errors=len(r.errors),failures=len(r.failures),BOARD='NOT_TESTED',PL_calls=0,
        scope='FROZEN_PREDICATES_WITH_PRIVATE_PC_INPUT_FIXTURES'))
    print(stream.getvalue());raise SystemExit(0 if r.wasSuccessful() else 1)
