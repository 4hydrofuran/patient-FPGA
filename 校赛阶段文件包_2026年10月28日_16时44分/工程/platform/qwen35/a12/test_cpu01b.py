"""Linux PC socket/failure tests of the actual derived permission handler."""
import importlib.util
import json
from pathlib import Path
import socket
import sys
import tempfile
import threading
import time
import types
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[3]
SOURCE=ROOT/'evidence/model_pl_A/20261024-cpu-opt-01b-v1/source'
sys.path.insert(0,str(SOURCE))
import cpu01b_observer as ob
from cpu01b_supervisor import OwnedWorker


class Tests(unittest.TestCase):
    def setUp(self):
        ob.reset_for_test();self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)
        self.worker=OwnedWorker.__new__(OwnedWorker)
        w=self.worker;w.manager_sock,self.child=socket.socketpair();self.child.settimeout(.3)
        w.process=types.SimpleNamespace(pid=1234);w.sequence=w.runs=w.loads=0
        w.directory=self.path;w.records=[];w._lock=threading.Lock();w.quarantined=False
        w.delivery_cancelled=False;w.max_runs=2;w.max_loads=1;w.expires=time.monotonic()+30
        w.owner_check=lambda:None;w.health=lambda:dict(checked_monotonic_ns=time.monotonic_ns(),fresh=True)
        self.thread=None
    def tearDown(self):
        self.child.close()
        if self.thread:self.thread.join(timeout=2)
        self.worker.manager_sock.close();self.temp.cleanup()
    def start(self):
        self.errors=[]
        def run():
            try:self.worker._permissions()
            except BaseException as exc:self.errors.append(type(exc).__name__)
        self.thread=threading.Thread(target=run);self.thread.start()
    def request(self,phase,seq,job=0,pid=1234):
        self.child.sendall((json.dumps(dict(phase=phase,sequence=seq,job=job,pid=pid))+'\n').encode())
        data=b''
        while not data.endswith(b'\n'):
            c=self.child.recv(1)
            if not c:return None
            data+=c
        return json.loads(data)
    def opened(self):
        self.assertTrue(self.request('router_open',1)['allow'])
        self.assertTrue(self.request('device_open',1)['allow'])
        self.assertTrue(self.request('weight_load',2,1)['allow'])
    def test_actual_protocol_and_phase_accounting(self):
        self.start();self.opened();ob.start_request(dict(id='test'))
        self.assertTrue(self.request('submit',3,1)['allow']);self.assertTrue(self.request('submit',4,2)['allow'])
        self.child.shutdown(socket.SHUT_WR);self.thread.join(2)
        result=dict(id='test',request_profile=dict(pl_profile=dict(enabled=True,phases=dict(prefill=dict(calls=1),decode=dict(calls=1)))))
        report=ob.finish_request(result,self.path/'profile.json')
        self.assertEqual(report['totals']['prefill']['rows'],1);self.assertEqual(report['totals']['decode']['rows'],1)
        for row in report['rows']:
            if row.get('permit',{}).get('phase')!='submit':continue
            names={span[0] for span in row['spans']}
            self.assertTrue({'request.parse','request.order','owner.total','health.total','record.json_encode','record.write','record.flush','record.fsync','reply.encode','reply.send'}<=names)
            self.assertTrue(all(row['start_ns']<=a<=b<=row['end_ns'] for _,a,b,_ in row['spans']))
        self.assertFalse(self.worker.quarantined);self.assertFalse(self.errors)
    def test_owner_failure_never_grants(self):
        self.worker.owner_check=lambda:(_ for _ in ()).throw(RuntimeError('owner changed'))
        self.start();self.assertIsNone(self.request('router_open',1));self.assertTrue(self.worker.quarantined)
    def test_health_failure_never_grants(self):
        self.worker.health=lambda:(_ for _ in ()).throw(RuntimeError('health lost'))
        self.start();self.assertIsNone(self.request('router_open',1));self.assertTrue(self.worker.quarantined)
    def test_replay_and_foreign_pid(self):
        self.start();self.assertTrue(self.request('router_open',1)['allow'])
        self.assertIsNone(self.request('device_open',1,pid=5678));self.assertTrue(self.worker.quarantined)
    def test_sequence_replay(self):
        self.start();self.opened();self.assertIsNone(self.request('submit',2,1));self.assertTrue(self.worker.quarantined)
    def test_cancel_denies_submit_but_allows_close(self):
        self.start();self.opened();self.worker.delivery_cancelled=True
        self.assertFalse(self.request('submit',3,1)['allow']);self.assertTrue(self.request('router_close',2)['allow'])
    def test_expiry_and_budget(self):
        self.start();self.opened();self.worker.expires=0
        self.assertFalse(self.request('submit',3,1)['allow'])
        self.worker.expires=time.monotonic()+30;self.worker.runs=self.worker.max_runs
        self.assertFalse(self.request('submit',4,2)['allow'])
    def test_fsync_failure_no_reply(self):
        with patch('cpu01b_supervisor_base.os.fsync',side_effect=OSError('disk fsync failure')):
            self.start()
            with self.assertRaises(socket.timeout):self.request('router_open',1)
            self.thread.join(1);self.assertTrue(self.worker.quarantined)
            self.assertEqual(self.errors,['OSError']) # Existing fault-record failure behavior retained.
    def test_write_failure_no_reply(self):
        class BadStream:
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def write(self,*args):raise OSError('write failed')
        with patch('pathlib.Path.open',return_value=BadStream()):
            self.start()
            with self.assertRaises(socket.timeout):self.request('router_open',1)
            self.thread.join(1);self.assertTrue(self.worker.quarantined)
    def test_phase_mismatch_refused(self):
        ob.start_request(dict(id='mismatch'))
        with self.assertRaises(RuntimeError):ob.finish_request(dict(id='mismatch',request_profile=dict(pl_profile=dict(enabled=True,phases=dict(prefill=dict(calls=1))))),self.path/'bad.json')
        self.assertFalse((self.path/'bad.json').exists())
    def test_plain_stays_unattributed(self):
        ob.start_request(dict(id='plain'))
        with ob.scope('permission'):ob.bind(dict(phase='submit',job=1))
        report=ob.finish_request(dict(id='plain'),self.path/'plain.json')
        self.assertEqual(report['rows'][0]['model_phase'],'UNATTRIBUTED_NO_NATIVE_PHASE_COUNTERS')
    def test_request_reset_and_idle_separation(self):
        for name in ['A','B']:
            ob.start_request(dict(id=name))
            with ob.scope('idle'):
                with ob.span('idle_health'):pass
            report=ob.finish_request(dict(id=name),self.path/(name+'.json'))
            self.assertEqual(len(report['rows']),1);self.assertEqual(report['rows'][0]['request_id'],name)
    def test_durable_record_matches_original(self):
        spec=importlib.util.spec_from_file_location('frozen_record',ROOT/'evidence/model_pl_A/20261024-cpu-opt-00-v1/frozen/health-bundle/platform/qwen35/a12/supervisor.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        module.OwnedWorker.record(self.worker,event='BYTE_TEST',observation={'fresh':True})
        OwnedWorker.record(self.worker,event='BYTE_TEST',observation={'fresh':True})
        rows=[json.loads(line) for line in (self.path/'events.jsonl').read_text().splitlines()]
        for row in rows:row.pop('monotonic_ns')
        self.assertEqual(rows[0],rows[1])


if __name__=='__main__':unittest.main(verbosity=2)
