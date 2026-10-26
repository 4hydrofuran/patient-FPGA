"""Targeted PC checks for changed lifecycle; no real device or board is opened."""
import ast
import fcntl
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / 'evidence/a13_A/20261026-fast-preboard-v1/candidate-01'
sys.path.insert(0, str(OUT))
from control import CloseRequested, Supervisor, request
from runtime import FastAdapter, STEPS, run
from runner import validate_request


class Link:
    def __init__(self): self.rows = []; self.fail = None
    def publish(self, phase, **kw): self.rows.append((phase, kw))
    def checkpoint(self):
        if self.fail: raise self.fail


class Core:
    def __init__(self):
        self.FDS = [1]; self.LEASE_SHA = 'pc-fixture'; self.CHILDREN = []
        self.paths = {'fixture': True}; self.saves = []; self.proofs = 0
    def save(self, name, value): self.saves.append((name, value))
    def lease(self): pass
    def states(self, paths): self.proofs += 1; return {'fixture_only': True}


class Adapter(FastAdapter):
    def __init__(self, core, link, fail=None): super().__init__(core, link); self.fail = fail
    def action(self, name):
        if name == self.fail: raise OSError('fixture failure')
        self.finished.append(name)


def fixture_worker(config, link):
    fd = os.open(config['lock'], os.O_CREAT | os.O_RDWR, 0o600)
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    c = Core(); c.FDS = [fd]
    def park(a, phase):
        handled = False
        while not Path(config['finish']).exists():
            if link.close_event.is_set() and not handled:
                handled = True; link.cleaning = True
                a.checked_close(phase, 'PC close')
                link.publish('FIXTURE_IDLE_CLOSE_OWNER_HELD', default_restored=False)
            time.sleep(.005)
        os.close(fd)
        return 0
    return run(Adapter(c, link), link, park)


class FastTests(unittest.TestCase):
    def test_success_retains_audio_no_restore(self):
        c, link = Core(), Link(); a = Adapter(c, link)
        run(a, link, lambda *_: 0)
        self.assertEqual(a.finished, list(STEPS))
        self.assertEqual(c.saves[-1][1]['status'], 'AUDIO_IDLE_RESERVED')
        self.assertFalse(c.saves[-1][1]['default_restored'])
        self.assertFalse(c.saves[-1][1]['safe_release'])

    def test_each_current_stage_failure_stops_without_cleanup(self):
        for index, step in enumerate(STEPS):
            with self.subTest(step=step):
                c, link = Core(), Link(); a = Adapter(c, link, step)
                run(a, link, lambda *_: 0)
                self.assertEqual(a.finished, list(STEPS[:index]))
                self.assertEqual(link.rows[-1][0], 'QUARANTINED_OWNER_RETAINED')
                self.assertFalse(c.saves)

    def test_close_never_releases_unknown_or_live_child(self):
        c, link = Core(), Link(); a = FastAdapter(c, link)
        with self.assertRaises(RuntimeError): a.checked_close('bind', 'PC fixture')
        a.finished = ['bind']
        class Child:
            def poll(self): return None
        c.CHILDREN = [Child()]
        with self.assertRaises(RuntimeError): a.checked_close('short', 'PC fixture')
        c.CHILDREN = []
        self.assertFalse(a.checked_close('full', 'PC fixture')['safe_release'])

    def test_stop_before_ownership_returns_normally(self):
        c, link = Core(), Link(); c.FDS = []; c.LEASE_SHA = None
        link.fail = CloseRequested('PC stop before starting')
        self.assertEqual(run(Adapter(c, link), link), 2)
        self.assertEqual(link.rows[-1][0], 'STOPPED_BEFORE_OWNERSHIP')

    def test_template_not_authorized_and_stale_fields_refused(self):
        r = json.loads((OUT/'REQUEST.template.json').read_text())
        with self.assertRaises(ValueError): validate_request(r)
        r['authorized'] = True
        with self.assertRaises(ValueError): validate_request(r)

    def test_overlay_events_include_close_and_applied_verification(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t); data = root/'input.dtbo'; data.write_bytes(b'PC fixture only')
            c, link = Core(), Link(); events = []
            c.event = lambda name, **kw: events.append(name)
            class Target:
                def __init__(self): self.path = root/'overlay'
                def __str__(self): return str(self.path)
                def mkdir(self):
                    self.path.mkdir(); (self.path/'status').write_text('applied')
                def __truediv__(self, name): return self.path/name
            FastAdapter(c, link).apply_overlay(Target(), data)
            self.assertLess(events.index('OVERLAY_WRITE_RETURN'), events.index('OVERLAY_CLOSE_COMMIT_ENTER'))
            self.assertLess(events.index('OVERLAY_CLOSE_COMMIT_RETURN'), events.index('OVERLAY_APPLIED_VERIFIED'))

    def test_no_restore_functions_and_one_combined_scan(self):
        text = (OUT/'candidate_core.py').read_text(); tree = ast.parse(text)
        names = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
        self.assertNotIn('candidate_cleanup', names)
        self.assertNotIn('candidate_restore_default', names)
        prep = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'candidate_prepare')
        source = ast.get_source_segment(text, prep)
        self.assertEqual(source.count('before = collect('), 1)
        self.assertLess(source.index('fcntl.flock('), source.index('before = collect('))
        self.assertIn('a13_audio_bus.ko', source)
        self.assertIn('pl-load.dtbo', source)
        rt = (OUT/'runtime.py').read_text()
        for forbidden in ('DEFAULT.mkdir(', 'MUTED.rmdir(', 'rmmod', '.terminate(', '.kill('):
            self.assertNotIn(forbidden, rt)

    def test_real_control_status_close_keeps_actual_PC_flock(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t); root.chmod(0o700)
            config = {'lock': str(root/'owner.lock'), 'finish': str(root/'finish')}
            manager = Supervisor(root, 'pc-fast-fixture-only', fixture_worker, config)
            try:
                deadline = time.monotonic()+5
                while time.monotonic() < deadline:
                    state = manager.tick(.005)
                    if state['phase'] == 'AUDIO_IDLE_RESERVED': break
                self.assertEqual(state['phase'], 'AUDIO_IDLE_RESERVED')
                # Drive the client in another process while supervisor ticks.
                import multiprocessing as mp
                ctx = mp.get_context('spawn'); parent, child = ctx.Pipe(False)
                p = ctx.Process(target=client, args=(str(manager.path), str(root/'client.sock'), child))
                p.start(); child.close()
                while not parent.poll() and time.monotonic() < deadline: manager.tick(.005)
                reply = parent.recv(); p.join(2); parent.close()
                self.assertTrue(reply['accepted'])
                while manager.tick(.005)['phase'] != 'FIXTURE_IDLE_CLOSE_OWNER_HELD' and time.monotonic() < deadline: pass
                with (root/'owner.lock').open('r+') as lock:
                    with self.assertRaises(BlockingIOError): fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                self.assertIsNone(manager.worker.exitcode)
            finally:
                (root/'finish').touch()
                deadline = time.monotonic()+5
                while manager.worker.exitcode is None and time.monotonic() < deadline: manager.tick(.005)
                self.assertEqual(manager.worker.exitcode, 0)
                manager.close_endpoint_after_worker_exit()


def client(endpoint, socket, pipe):
    pipe.send(request(endpoint, socket, 'pc-fast-fixture-only', 'close'))
    pipe.close()


if __name__ == '__main__': unittest.main()
