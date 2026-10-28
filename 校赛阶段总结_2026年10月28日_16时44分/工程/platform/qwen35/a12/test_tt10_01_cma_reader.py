"""Linux I/O and fail-closed tests. Fixtures never represent BOARD resources."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
import types
import unittest
from unittest import mock
from tt10_01_diag_reader import CHUNK, DiagnosticBlocked, DiagnosticReader, NumericalStreams
from tt10_01_cma_observer import PhaseObserver
from tt10_01_numeric import concatenated


def put(path, data):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_bytes(data)
    path.chmod(0o600)


def fixture(root):
    for name, body, positions in (('warm_prefix', b'abcd', [0]),
            ('diag_full_R0', b'abcdefgh', [0, 1]), ('diag_hit', b'efgh', [1])):
        diag = root / name / 'diag'
        diag.mkdir(mode=0o700, parents=True)
        put(diag / 'x.bin', body)
        put(diag / 'y.bin', body.upper())
        put(diag / 'hybrid-state.bin', b'warm' if name == 'warm_prefix' else b'complete-state-17')
        logits = []
        for position in positions:
            filename = 'logits-prefill-%d.f32' % position
            put(diag / filename, bytes([position + 1]) * 993280)
            logits.append(dict(file=filename, position=position))
        manifest = dict(projections=[dict(id='l00_gate', T=len(body) // 4, K=1, N=1, input='x.bin', output='y.bin')],
            logits=logits, prompt_tokens=[1, 2], teacher_tokens=[10, 11], scope='all', prefill_chunk=256)
        put(diag / 'manifest.json', (json.dumps(manifest) + '\n').encode())


def file_hashes(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file() and not p.is_symlink()}


class ReaderTests(unittest.TestCase):
    def setUp(self):
        base = os.environ.get('SP_CMA_TEST_ARTIFACTS')
        self.root = Path(tempfile.mkdtemp(prefix=self._testMethodName + '-', dir=base))
        self.root.chmod(0o700)
        fixture(self.root)
        self.events = []
        self.reader = DiagnosticReader(self.root, lambda event, **kw: self.events.append(dict(event=event, **kw)), expected_uid=os.getuid())

    def tearDown(self):
        self.reader.close()
        # Retain every generated fixture when an explicit evidence directory is used.
        if not os.environ.get('SP_CMA_TEST_ARTIFACTS'):
            import shutil
            shutil.rmtree(self.root)

    def scan(self, name, streams=None):
        s = streams or NumericalStreams()
        return s, s.scan(self.reader, name, completed=True, quiescent=True)

    def reject_begin(self):
        with self.assertRaises((DiagnosticBlocked, OSError, ValueError)):
            self.reader.begin('warm_prefix', completed=True, quiescent=True)
        self.assertTrue(self.reader.blocked)
        with self.assertRaises(DiagnosticBlocked):
            self.reader.begin('diag_hit', completed=True, quiescent=True)

    def test_streams_match_old_all_fields_and_originals_unchanged(self):
        before = file_hashes(self.root)
        old = concatenated(self.root / 'diag_full_R0', self.root / 'warm_prefix', self.root / 'diag_hit')
        joined, _ = self.scan('warm_prefix')
        full, _ = self.scan('diag_full_R0')
        self.scan('diag_hit', joined)
        self.assertEqual(full.compare(joined), old)
        self.assertTrue(old['equal'])
        self.assertEqual(file_hashes(self.root), before)
        self.reader.verify()

    def test_real_fsync_advice_same_open_fd_once_per_file(self):
        synced, advised, read_bytes, sizes, requested = [], [], {}, {}, []
        real_sync, real_advice, real_read = os.fsync, os.posix_fadvise, os.read
        def sync(fd):
            synced.append(os.fstat(fd).st_ino)
            return real_sync(fd)
        def advice(fd, offset, length, which):
            st = os.fstat(fd)
            self.assertIn(st.st_ino, synced)
            self.assertEqual((offset, length, which), (0, 0, os.POSIX_FADV_DONTNEED))
            self.assertEqual(read_bytes[st.st_ino], st.st_size)
            advised.append(st.st_ino)
            sizes[st.st_ino] = st.st_size
            return real_advice(fd, offset, length, which)
        def read(fd, n):
            st = os.fstat(fd)
            requested.append(n)
            data = real_read(fd, n)
            read_bytes[st.st_ino] = read_bytes.get(st.st_ino, 0) + len(data)
            return data
        with mock.patch('os.fsync', sync), mock.patch('os.posix_fadvise', advice), mock.patch('os.read', read):
            _, audit = self.scan('warm_prefix')
        self.assertEqual(len(advised), len(set(advised)))
        self.assertEqual(len(advised), audit['raw_files'])
        self.assertEqual(sum(sizes.values()), audit['raw_bytes'])
        self.assertTrue(all(n <= CHUNK for n in requested))
        self.assertEqual(audit['read_passes_per_file'], 1)

    def test_non_page_aligned_multi_chunk_state_preserved(self):
        p = self.root / 'warm_prefix/diag/hybrid-state.bin'
        raw = b'q' * (CHUNK + 17)
        put(p, raw)
        _, audit = self.scan('warm_prefix')
        self.assertEqual(audit['files'][p.name], dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
        self.assertEqual(p.read_bytes(), raw)

    def test_projection_corruption_is_not_equal(self):
        put(self.root / 'diag_hit/diag/x.bin', b'efgi')
        joined, _ = self.scan('warm_prefix'); full, _ = self.scan('diag_full_R0'); self.scan('diag_hit', joined)
        result = full.compare(joined)
        self.assertFalse(result['equal'])
        self.assertTrue(result['projection_difference'])

    def test_logit_corruption_is_not_equal(self):
        put(self.root / 'diag_hit/diag/logits-prefill-1.f32', b'z' * 993280)
        joined, _ = self.scan('warm_prefix'); full, _ = self.scan('diag_full_R0'); self.scan('diag_hit', joined)
        self.assertFalse(full.compare(joined)['equal'])
        self.assertTrue(full.compare(joined)['logits_difference'])

    def test_state_corruption_is_not_equal(self):
        put(self.root / 'diag_hit/diag/hybrid-state.bin', b'wrong-state')
        joined, _ = self.scan('warm_prefix'); full, _ = self.scan('diag_full_R0'); self.scan('diag_hit', joined)
        self.assertFalse(full.compare(joined)['prefill_state_equal'])

    def test_missing_file_rejected(self):
        (self.root / 'warm_prefix/diag/y.bin').unlink()
        self.reject_begin()

    def test_unlisted_file_rejected(self):
        put(self.root / 'warm_prefix/diag/extra.bin', b'unlisted')
        self.reject_begin()

    def test_symlink_file_rejected_without_advice_to_target(self):
        p = self.root / 'warm_prefix/diag/manifest.json'
        target = self.root / 'protected-model'
        p.rename(target)
        p.symlink_to(target)
        with mock.patch('os.posix_fadvise') as advice:
            self.reject_begin()
        advice.assert_not_called()

    def test_hardlink_file_rejected(self):
        os.link(self.root / 'warm_prefix/diag/manifest.json', self.root / 'second-link')
        self.reject_begin()

    def test_fifo_rejected_without_blocking(self):
        p = self.root / 'warm_prefix/diag/manifest.json'
        p.unlink(); os.mkfifo(p, 0o600)
        self.reject_begin()

    def test_symlink_directory_rejected(self):
        p = self.root / 'warm_prefix/diag'
        p.rename(p.with_name('real-diag')); p.symlink_to(p.with_name('real-diag'), target_is_directory=True)
        self.reject_begin()

    def test_wrong_owner_rejected(self):
        self.reader.close()
        with self.assertRaises(DiagnosticBlocked):
            DiagnosticReader(self.root, lambda *a, **kw: None, expected_uid=os.getuid() + 1)

    def test_uncompleted_or_inflight_case_rejected(self):
        with self.assertRaises(DiagnosticBlocked):
            self.reader.begin('warm_prefix', completed=True, quiescent=False)
        self.assertTrue(self.reader.blocked)

    def test_path_escape_rejected(self):
        p = self.root / 'warm_prefix/diag/manifest.json'
        m = json.loads(p.read_text()); m['projections'][0]['input'] = '../protected-model'; put(p, json.dumps(m).encode())
        self.reject_begin()

    def test_duplicate_file_rejected(self):
        p = self.root / 'warm_prefix/diag/manifest.json'
        m = json.loads(p.read_text()); m['projections'][0]['output'] = 'x.bin'; put(p, json.dumps(m).encode())
        self.reject_begin()

    def test_json_position_string_rejected(self):
        p = self.root / 'warm_prefix/diag/manifest.json'
        m = json.loads(p.read_text()); m['logits'][0]['position'] = '0'; put(p, json.dumps(m).encode())
        self.reject_begin()

    def test_fsync_error_latches_no_advice(self):
        with mock.patch('os.fsync', side_effect=OSError('injected fsync failure')), mock.patch('os.posix_fadvise') as advice:
            self.reject_begin()
        advice.assert_not_called()

    def test_advice_error_latches_and_original_retained(self):
        before = file_hashes(self.root)
        with mock.patch('os.posix_fadvise', side_effect=OSError('injected advice failure')):
            self.reject_begin()
        self.assertEqual(file_hashes(self.root), before)

    def test_truncation_during_read_latches(self):
        self.reader.begin('warm_prefix', completed=True, quiescent=True)
        p = self.root / 'warm_prefix/diag/x.bin'
        with self.assertRaises(DiagnosticBlocked):
            self.reader.read('warm_prefix', 'x.bin', lambda block: put(p, b'x'))
        self.assertTrue(self.reader.blocked)
        self.assertEqual(p.read_bytes(), b'x')

    def test_replacement_during_read_latches(self):
        self.reader.begin('warm_prefix', completed=True, quiescent=True)
        p = self.root / 'warm_prefix/diag/x.bin'
        def replace(block):
            q = p.with_name('replacement'); put(q, block); q.replace(p)
        with self.assertRaises(DiagnosticBlocked):
            self.reader.read('warm_prefix', 'x.bin', replace)
        self.assertTrue(self.reader.blocked)

    def test_post_read_rewrite_with_restored_mtime_rejected(self):
        self.scan('warm_prefix')
        p = self.root / 'warm_prefix/diag/x.bin'; st = p.stat()
        put(p, b'xxxx'); os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns))
        with self.assertRaises(DiagnosticBlocked):
            self.reader.verify()
        self.assertTrue(self.reader.blocked)

    def test_root_replaced_after_open_rejected(self):
        moved = self.root.with_name(self.root.name + '-original')
        self.root.rename(moved); self.root.mkdir(mode=0o700)
        with self.assertRaises(DiagnosticBlocked):
            self.reader.begin('warm_prefix', completed=True, quiescent=True)
        self.assertTrue(moved.exists())

    def test_empty_streams_cannot_pass(self):
        with self.assertRaises(DiagnosticBlocked):
            NumericalStreams().compare(NumericalStreams())


class ObserverTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix=self._testMethodName + '-', dir=os.environ.get('SP_CMA_TEST_ARTIFACTS')))
        self.samples = dict(MemAvailable=1114112, CmaFree=98304, CmaTotal=819200, Cached=42, Dirty=0, Writeback=0)
        schedule = types.SimpleNamespace(blocked=False)
        self.platform = types.SimpleNamespace(gate_lock=threading.RLock(), health_schedule=schedule)
        self.checks = 0
        def health():
            self.checks += 1
            if schedule.blocked:
                raise DiagnosticBlocked('old latch')
        self.owner = types.SimpleNamespace(platform=self.platform, owner_check=lambda: None, health=health)
        self.worker = types.SimpleNamespace(runs=7, loads=72, sequence=81, quarantined=False, delivery_cancelled=False,
            process=types.SimpleNamespace(pid=os.getpid(), poll=lambda: None))
        def sample(pids, full):
            return dict(observed_monotonic_ns=1, memory_kib=dict(self.samples), processes={'PC_FIXTURE': dict(pss_kib=1)})
        self.observer = PhaseObserver(self.owner, self.worker, self.root, real=True, sample=sample)

    def tearDown(self):
        self.observer.close()
        if not os.environ.get('SP_CMA_TEST_ARTIFACTS'):
            import shutil
            shutil.rmtree(self.root)

    def test_exact_minimum_gate_and_fresh_before_application(self):
        self.observer.before_request(dict(id='app_R0', application={}))
        self.assertEqual(self.checks, 1)
        self.assertTrue(self.observer.busy)
        row = json.loads((self.root / 'diagnostic-resources.jsonl').read_text().splitlines()[0])
        self.assertEqual(row['event'], 'BEFORE_APPLICATION_SEND')
        self.assertTrue(row['fresh_owner_health'])

    def test_one_kib_below_cma_rejected_before_send_and_never_unlatched(self):
        self.samples['CmaFree'] = 98303
        sent = []
        with self.assertRaises(DiagnosticBlocked):
            self.observer.before_request(dict(id='app_R0', application={}))
            sent.append('sent')
        self.samples['CmaFree'] = 500000
        with self.assertRaises(DiagnosticBlocked):
            self.observer.before_request(dict(id='app_R0', application={}))
        self.assertEqual(sent, [])
        self.assertTrue(self.platform.health_schedule.blocked)

    def test_one_kib_below_available_rejected(self):
        self.samples['MemAvailable'] = 1114111
        with self.assertRaises(DiagnosticBlocked):
            self.observer.before_request(dict(id='app_R0', application={}))

    def test_old_latch_rejected_without_sampling_success(self):
        self.platform.health_schedule.blocked = True
        with self.assertRaises(DiagnosticBlocked):
            self.observer.event('FILE_ADVISED', advice_return=0)
        self.assertEqual(self.checks, 0)

    def test_advice_success_with_low_actual_cma_still_fails(self):
        self.samples['CmaFree'] = 47392
        with self.assertRaises(DiagnosticBlocked):
            self.observer.event('FILE_ADVISED', advice_return=0)
        row = json.loads((self.root / 'diagnostic-resources.jsonl').read_text().splitlines()[0])
        self.assertFalse(row['allowed'])
        self.assertEqual(row['sample']['memory_kib']['CmaFree'], 47392)

    def test_permit_count_changed_during_comparison_rejected(self):
        self.worker.runs += 1
        with self.assertRaises(DiagnosticBlocked):
            self.observer.event('READ_PROGRESS')

    def test_control_sequence_changed_during_comparison_rejected(self):
        self.worker.sequence += 1
        with self.assertRaises(DiagnosticBlocked):
            self.observer.event('READ_PROGRESS')

    def test_read_headroom_separate_from_unchanged_original_gate(self):
        with self.assertRaises(DiagnosticBlocked):
            self.observer.event('FILE_BEFORE', file_bytes=17)
        row = json.loads((self.root / 'diagnostic-resources.jsonl').read_text().splitlines()[0])
        self.assertEqual(row['required_CmaFree_kib'], 98304)
        self.assertEqual(row['required_phase_CmaFree_kib'], 98304 + 8192 + 1)

    def test_observation_journal_cache_advice_failure_latches(self):
        self.samples['MemAvailable'] = 1500000
        self.samples['CmaFree'] = 500000
        with mock.patch('os.posix_fadvise', side_effect=OSError('journal advice failure')):
            with self.assertRaises(OSError):
                self.observer.event('OBSERVATION_JOURNAL_TEST', force=True, padding='x' * 8192)
        self.assertTrue(self.platform.health_schedule.blocked)
        self.assertTrue((self.root / 'diagnostic-resources.jsonl').stat().st_size > 8192)

    def test_sampling_error_latches(self):
        self.observer.sample = mock.Mock(side_effect=OSError('proc missing'))
        with self.assertRaises(OSError):
            self.observer.event('FILE_BEFORE')
        self.assertTrue(self.platform.health_schedule.blocked)

    def test_completed_result_requires_verified_completion(self):
        self.observer.before_request(dict(id='diag_hit'))
        with self.assertRaises(DiagnosticBlocked):
            self.observer.completed(dict(id='diag_hit', status='OK', state_cleared_before_response=True,
                state_position_after_clear=-1, bridge={'a12_route': {'host_verified_completions': 6}}))

    def test_result_completion_permits_diagnostic_scan(self):
        self.observer.before_request(dict(id='diag_hit'))
        self.observer.completed(dict(id='diag_hit', status='OK', state_cleared_before_response=True,
            state_position_after_clear=-1, bridge={'a12_route': {'host_verified_completions': 7}}))
        self.assertTrue(self.observer.quiescent())


if __name__ == '__main__':
    unittest.main()
