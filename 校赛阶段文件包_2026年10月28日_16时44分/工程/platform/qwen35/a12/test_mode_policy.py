"""PC control doubles for mode policy; real native integration is separate."""
import copy
import io
from pathlib import Path
import tempfile
import types
import unittest
from unittest import mock
import sys
from mode_evidence import OUT,save
from mode_coordinator import ModeCoordinator
from mode_journal import ModeBlocked
from mode_history import validate_history

class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='a12-mode-policy-');self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.capsule=self.root/'capsule.json';self.capsule.write_text('{}')
        self.patch=mock.patch('mode_coordinator.verify',return_value={});self.patch.start();self.addCleanup(self.patch.stop)
        self.c=ModeCoordinator(self.root/'state',self.capsule,trusted_worker=True)
        self.addCleanup(lambda:self.c.journal.dispose() if not self.c.journal.closed else None)
    def failure(self):
        c=self.c;c.switch('PC_BATCH_CANDIDATE');c.used.add('failed')
        window='a'*32;tag='mc-fixture'
        c._append('WINDOW_BEGIN',window_id=window,input_id='failed',mode=c.mode,grant_size=72,tag=tag,
            capsule_sha256=c.capsule_sha,independent_test_input=True)
        c._append('WINDOW_MANAGER_OBSERVED',window_id=window,manager_pid=10,manager_start_ticks=20)
        c._append('WINDOW_NATIVE_OBSERVED',window_id=window,native_pid=11,native_start_ticks=21,
            page_epoch='b'*32,page_snapshot_sha256='c'*64)
        page=dict(manager_pid=10,worker_pid=11,worker_start_ticks=21,manager_epoch='b'*32,revoked=True,
            active=True,inflight_or_unknown=True,shared_claims=5,request_generation=1)
        proof=dict(window_id=window,input_id='failed',tag=tag,mode=c.mode,manager_exit_code=1,
            manager_pidfd_terminal=True,native_pidfd_terminal=True,page=page,
            independent_audit=dict(status='REJECTED_OR_INCOMPLETE_RETAIN_OWNER',release_allowed=False,replay_allowed=False),
            outcome='FAILED_PC_DRAINED_NO_REPLAY',BOARD='NOT_TESTED',release_allowed=False,capsule_unchanged=True)
        c._append('WINDOW_FAILED',**proof)
        obs=lambda:types.SimpleNamespace(terminal=mock.Mock(return_value=True),close=mock.Mock())
        r=dict(window_id=window,input_id='failed',proof=proof,manager=obs(),native=obs(),
            page=types.SimpleNamespace(snapshot=mock.Mock(return_value=page),close=mock.Mock()),
            socket=mock.Mock(),log=mock.Mock(),cancelled=False)
        c.active=r;c.phase='FAILED_DRAINED_PC';c.disabled=True;return r
    def test_unknown_and_active_modes_cannot_switch_or_close(self):
        for phase in ('ACTIVE','QUARANTINED'):
            self.c.phase=phase;self.c.active={'fixture':True}
            with self.assertRaises(ModeBlocked):self.c.switch('PC_BATCH_CANDIDATE')
            with self.assertRaises(ModeBlocked):self.c.close()
            with self.assertRaises(ModeBlocked):self.c.fallback_for_new_input('fresh')
    def test_all_production_modes_refused(self):
        for mode in ('RESOURCE_PROBE','STRICT_NUMERIC','PERF_ACCEPTANCE','SERVICE','BOARD'):
            with self.assertRaises(ModeBlocked):self.c.switch(mode)
        self.assertEqual(self.c.mode,'PC_STRICT_CONTROL')
    def test_untrusted_worker_cannot_choose_batch(self):
        self.c.trusted_worker=False
        with self.assertRaises(ModeBlocked):self.c.switch('PC_BATCH_CANDIDATE')
    def test_fallback_only_new_input_and_candidate_stays_disabled(self):
        self.failure()
        with self.assertRaises(ModeBlocked):self.c.fallback_for_new_input('failed')
        self.c.fallback_for_new_input('fresh');self.assertEqual(self.c.mode,'PC_STRICT_CONTROL')
        with self.assertRaises(ModeBlocked):self.c.switch('PC_BATCH_CANDIDATE')
        with self.assertRaises(ModeBlocked):self.c.launch('failed')
        with self.assertRaises(ModeBlocked):self.c.launch('different_fresh')
        self.c.close();state=validate_history(self.c.journal.rows,closed_required=True)
        self.assertTrue(state['candidate_disabled']);self.assertEqual(state['used_inputs'],['failed'])
    def test_missing_current_drain_observation_blocks_fallback(self):
        r=self.failure();r['native'].terminal.return_value=False
        with self.assertRaises(ModeBlocked):self.c.fallback_for_new_input('fresh')
        r['native'].terminal.return_value=True;r['page'].snapshot.return_value={'revoked':False}
        with self.assertRaises(ModeBlocked):self.c.fallback_for_new_input('fresh')
    def test_cancellation_is_sent_before_journal_failure(self):
        calls=[];self.c.phase='ACTIVE';self.c.active=dict(window_id='d'*32,socket=mock.Mock(),cancelled=False)
        self.c.active['socket'].send.side_effect=lambda _:calls.append('cancel')
        def fail(*a,**kw):calls.append('disk');raise OSError('fixture fsync')
        with mock.patch.object(self.c.journal,'append',side_effect=fail):
            with self.assertRaises(OSError):self.c.cancel()
        self.assertEqual(calls[:2],['cancel','disk']);self.assertEqual(self.c.phase,'QUARANTINED')
    def test_capsule_change_invalidates_mode_boundary(self):
        self.capsule.write_text('{"changed":true}')
        with self.assertRaises(ModeBlocked):self.c.switch('PC_BATCH_CANDIDATE')
    def test_history_semantics_reject_unsafe_close_even_with_valid_hash_structure(self):
        self.failure();rows=copy.deepcopy(self.c.journal.rows)
        close=dict(rows[0],event='SESSION_CLOSE',candidate_disabled=True,replay_allowed=False,release_allowed=False)
        # A failed, observed window may be archived. An active unknown one may not.
        validate_history(rows+[close],closed_required=True)
        with self.assertRaises(ModeBlocked):validate_history(rows[:-1]+[close],closed_required=True)
    def test_failure_observation_is_idempotent(self):
        self.failure();before=self.c.journal.serial
        for _ in range(5):self.assertEqual(self.c.observe()['outcome'],'FAILED_PC_DRAINED_NO_REPLAY')
        self.assertEqual(before,self.c.journal.serial)
    def test_persisted_complete_hash_chain_with_active_window_cannot_reopen(self):
        from mode_journal import read_journal
        c=self.c;c._append('WINDOW_BEGIN',window_id='f'*32,input_id='never_completed',mode=c.mode,grant_size=1,
            tag='mc-semantic-fixture',capsule_sha256=c.capsule_sha,independent_test_input=True)
        # Low-level fixture writer deliberately bypasses coordinator.close.
        c.journal.append('SESSION_CLOSE',candidate_disabled=False,replay_allowed=False,release_allowed=False)
        c.journal.finish();rows=read_journal(self.root/'state/coordinator.jsonl')
        self.assertEqual(rows[-1]['event'],'SESSION_CLOSE') # valid structural chain
        with self.assertRaises(ModeBlocked):ModeCoordinator(self.root/'state',self.capsule,trusted_worker=True)
        self.assertTrue((self.root/'state/DIRTY.json').exists())
        save(OUT/'INVALID_SEMANTIC_HISTORY_FIXTURE.json',dict(scope='PC_CONTROL_DOUBLE_REAL_FILE',rows=rows,
            complete_hash_chain=True,reopen_rejected=True,new_model_runs=0,BOARD='NOT_TESTED'))

if __name__=='__main__':
    target=OUT/'policy-tests-02';target.mkdir(exist_ok=False);stream=io.StringIO()
    r=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    (target/'unittest.txt').write_text(stream.getvalue());save(target/'RESULT.json',dict(status='PASS' if r.wasSuccessful() else 'FAIL',
        tests=r.testsRun,errors=len(r.errors),failures=len(r.failures),domain='PC_CONTROL_DOUBLES_MODE_POLICY_ONLY',BOARD='NOT_TESTED',PL_calls=0))
    print(stream.getvalue());raise SystemExit(0 if r.wasSuccessful() else 1)
