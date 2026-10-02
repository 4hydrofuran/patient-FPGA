"""Persistent SP_VOICE_V1 worker; pinned ASR is selected explicitly at startup."""
import argparse
import hashlib
import json
import math
import queue
import re
import sys
import threading
import time
import uuid
from pathlib import Path
from .audio import VoiceError, inspect_wav, write_tone
from .memory import memory_snapshot
from .spool import Spool
from .streaming import STREAM_OPS

MAX_LINE = 32768
MAX_TEXT = 2048
ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z')
MANDATORY = ['hello', 'transcribe', 'synthesize', 'cancel', 'reset', 'shutdown']


def unique_object(pairs):
    d = {}
    for k, v in pairs:
        if k in d:
            raise ValueError('Duplicate JSON field')
        d[k] = v
    return d


class Worker:
    def __init__(self, spool, emit, contract_tone=False, test_delay_ms=0, asr=None, tts=None, streaming=None):
        if (asr is not None or tts is not None) and (contract_tone or test_delay_ms):
            raise ValueError('Real engines cannot be combined with contract fixtures')
        self.asr = asr
        self.tts = tts
        self.streaming = streaming
        self.streams = {}
        self.active_stream = None
        self.spool = Spool(spool)
        self.emit_fn = emit
        self.contract_tone = contract_tone
        self.test_delay_ms = test_delay_ms
        self.lock = threading.RLock()
        self.requests = set()
        self.sessions = {}
        self.jobs = {}
        self.owned = {}
        self.tasks = queue.Queue(maxsize=2)
        self.stopping = False
        self.thread = threading.Thread(target=self.run_jobs, name='voice-c-worker', daemon=False)
        self.thread.start()

    def emit(self, request, kind='result', **payload):
        self.emit_fn(dict(api_version=1, request_id=request.get('request_id'), op=request.get('op'),
                          type=kind, execution_kind='PC_REAL' if self.asr or self.tts else 'CONTRACT_TEST', **payload))

    def error(self, request, code, message):
        self.emit(request, 'error', code=code, message=message)

    def validate(self, r):
        if not isinstance(r, dict):
            raise VoiceError('BAD_REQUEST', 'Require a JSON object')
        if type(r.get('api_version')) is not int or r['api_version'] != 1:
            raise VoiceError('BAD_VERSION', 'Require api_version=1')
        if not isinstance(r.get('request_id'), str) or not ID.fullmatch(r['request_id']):
            raise VoiceError('BAD_ID', 'Invalid request_id')
        allowed_ops = MANDATORY + (STREAM_OPS if self.streaming else [])
        if not isinstance(r.get('op'), str) or r['op'] not in allowed_ops:
            raise VoiceError('UNSUPPORTED_OP', 'Operation not supported; streaming ASR is unavailable')
        fields = {'api_version', 'request_id', 'op'}
        fields |= {'session_id', 'wav_path', 'language'} if r['op'] == 'transcribe' else set()
        fields |= {'session_id', 'text', 'output_dir'} if r['op'] == 'synthesize' else set()
        fields |= {'session_id'} if r['op'] == 'reset' else set()
        fields |= {'target_request_id'} if r['op'] == 'cancel' else set()
        fields |= {'session_id', 'sample_rate', 'channels', 'format'} if r['op'] == 'asr_begin' else set()
        fields |= {'stream_id', 'seq', 'pcm_path', 'final'} if r['op'] == 'asr_push' else set()
        fields |= {'stream_id'} if r['op'] == 'asr_finish' else set()
        if set(r) - fields:
            raise VoiceError('BAD_FIELDS', 'Unrecognized operation fields')
        if r['op'] in {'transcribe', 'synthesize', 'reset', 'asr_begin'}:
            sid = r.get('session_id')
            if not isinstance(sid, str) or not ID.fullmatch(sid):
                raise VoiceError('BAD_SESSION', 'Invalid session_id')
        if r['op'] == 'transcribe':
            if r.get('language') != 'zh':
                raise VoiceError('BAD_LANGUAGE', 'Require language=zh')
            self.spool.resolve(r.get('wav_path'), r['session_id'])
        if r['op'] == 'synthesize':
            text = r.get('text')
            if (not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT or
                    any(ord(c) < 32 and c not in '\t\n' for c in text)):
                raise VoiceError('BAD_TEXT', 'Require bounded nonempty text')
            self.spool.resolve(r.get('output_dir'), r['session_id'], directory=True)
        if r['op'] == 'cancel':
            target = r.get('target_request_id')
            if not isinstance(target, str) or not ID.fullmatch(target):
                raise VoiceError('BAD_TARGET', 'Require target_request_id')
        if r['op'] == 'asr_begin':
            if (type(r.get('sample_rate')) is not int or r['sample_rate'] != 16000 or
                    type(r.get('channels')) is not int or r['channels'] != 1 or r.get('format') != 'pcm_s16le'):
                raise VoiceError('BAD_STREAM_FORMAT', 'Require 16000 Hz mono pcm_s16le')
        if r['op'] in {'asr_push', 'asr_finish'}:
            stream_id = r.get('stream_id')
            if not isinstance(stream_id, str) or not ID.fullmatch(stream_id):
                raise VoiceError('BAD_STREAM_ID', 'Invalid stream_id')
            state = self.streams.get(stream_id)
            if state is None:
                raise VoiceError('UNKNOWN_STREAM', 'Stream not found')
            if state['epoch'] != self.sessions.get(state['session']):
                raise VoiceError('STALE_STREAM', 'Stream belongs to a previous session epoch')
            if state['status'] not in {'OPEN', 'INPUT_CLOSED'} or state['cancelled']:
                raise VoiceError('STREAM_CLOSED', 'Stream has ended, failed, expired or been cancelled')
            if r['op'] == 'asr_push':
                if state['status'] != 'OPEN':
                    raise VoiceError('STREAM_INPUT_CLOSED', 'Final input already queued; only finish is allowed')
                if type(r.get('seq')) is not int or r['seq'] != state['next_seq']:
                    raise VoiceError('BAD_SEQ', 'Require next consecutive integer seq, starting at zero')
                if type(r.get('final', False)) is not bool:
                    raise VoiceError('BAD_FINAL', 'final must be boolean')
                if state['next_seq'] >= self.streaming.config['max_chunks']:
                    raise VoiceError('STREAM_CHUNK_LIMIT', 'Stream chunk limit exceeded')
                self.spool.resolve(r.get('pcm_path'), state['session'])

    def end_stream(self, state, status):
        state['status'] = status
        state['cancelled'] = status != 'FINISHED'
        state['native'] = None
        state.pop('pcm_hash', None)
        if self.active_stream == state['stream_id']:
            self.active_stream = None

    def expire_streams(self):
        if not self.streaming:
            return
        with self.lock:
            state = self.streams.get(self.active_stream)
            if (state and not any(j.get('stream_id') == state['stream_id'] for j in self.jobs.values()) and
                    time.monotonic() - state['last_activity'] > self.streaming.config['idle_timeout_seconds']):
                self.end_stream(state, 'EXPIRED')

    def handle(self, r):
        with self.lock:
            try:
                self.expire_streams()
                self.validate(r)
                if self.stopping:
                    raise VoiceError('STOPPING', 'Worker is shutting down')
                if r['request_id'] in self.requests:
                    raise VoiceError('DUPLICATE_ID', 'request_id cannot be reused in this process')
                if len(self.requests) >= 4096:
                    raise VoiceError('REQUEST_LIMIT', 'Restart worker after request limit')
                self.requests.add(r['request_id'])
                op = r['op']
                if op == 'hello':
                    self.emit(r, module_id='voice_C_c03_stream' if self.streaming else 'voice_C_c02_tts' if self.tts else 'voice_C_c01_asr' if self.asr else 'voice_C_c00_contract',
                              version='0.4.0-stream' if self.streaming else '0.3.0-tts' if self.tts else '0.2.0-asr' if self.asr else '0.1.0-contract',
                              models=[engine.metadata for engine in (self.streaming or self.asr, self.tts) if engine],
                              licenses=([dict(upstream='apache-2.0', onnx='REVIEW_PENDING')] if self.asr else []) +
                                       ([dict(weights='REVIEW_PENDING', training_data='NON_COMMERCIAL_ONLY')] if self.tts else []),
                              mandatory_ops=MANDATORY,
                              capabilities=dict(streaming_asr=self.streaming is not None, real_asr=self.asr is not None, real_tts=self.tts is not None,
                                                contract_test_tone=self.contract_tone),
                              optional_ops=STREAM_OPS if self.streaming else [],
                              scheduling='ONE_NATIVE_TASK; ACTIVE_STREAM_EXCLUDES_TTS_AND_TRANSCRIBE',
                              sample_rates=[16000, 22050] if self.tts else [16000], concurrency_limit=1, queued_limit=2,
                              confidence=None, memory=memory_snapshot())
                    return
                if op == 'cancel':
                    job = self.jobs.get(r['target_request_id'])
                    if job is None:
                        raise VoiceError('TARGET_NOT_ACTIVE', 'Target request is not active')
                    job['cancelled'] = True
                    pending = job['started']
                    if job.get('stream_id'):
                        state = self.streams[job['stream_id']]
                        state['cancelled'] = True
                        pending = any(j.get('stream_id') == state['stream_id'] and j['started'] for j in self.jobs.values())
                        for other in self.jobs.values():
                            if other.get('stream_id') == state['stream_id']:
                                other['cancelled'] = True
                        if not pending:
                            self.end_stream(state, 'CANCELLED')
                    self.emit(r, target_request_id=r['target_request_id'],
                              cancel_pending=pending, stopped=not pending,
                              late_result_policy='DISCARD', state='CANCEL_REQUESTED')
                    return
                if op == 'shutdown':
                    self.stopping = True
                    for job in self.jobs.values():
                        job['cancelled'] = True
                    for state in self.streams.values():
                        state['cancelled'] = True
                    self.emit(r, state='SHUTTING_DOWN', pending_jobs=len(self.jobs))
                    return
                sid = (self.streams[r['stream_id']]['session'] if op in {'asr_push', 'asr_finish'} else r['session_id'])
                if sid not in self.sessions and len(self.sessions) >= 64:
                    raise VoiceError('SESSION_LIMIT', 'Restart worker after session limit')
                epoch = self.sessions.setdefault(sid, 0)
                if op == 'reset':
                    for job in self.jobs.values():
                        if job['session'] == sid:
                            job['cancelled'] = True
                    self.sessions[sid] = epoch + 1
                    for state in self.streams.values():
                        if state['session'] == sid:
                            state['cancelled'] = True
                            if not any(j.get('stream_id') == state['stream_id'] and j['started'] for j in self.jobs.values()):
                                self.end_stream(state, 'RESET')
                    for relative in list(self.owned.get(sid, set())):
                        self.spool.remove_owned_file(relative, sid)
                    self.owned[sid] = set()
                    self.emit(r, session_id=sid, epoch=epoch + 1,
                              pending_compute=any(j['session'] == sid for j in self.jobs.values()),
                              removed_scope='WORKER_OWNED_FILES_ONLY')
                    return
                if self.active_stream and op in {'synthesize', 'transcribe', 'asr_begin'}:
                    raise VoiceError('HALF_DUPLEX_BUSY', 'Active ASR stream reserves the voice service; finish or reset it first')
                if op == 'asr_begin' and any(not j.get('completed') for j in self.jobs.values()):
                    raise VoiceError('HALF_DUPLEX_BUSY', 'Wait for queued or active native work before starting a stream')
                if op == 'asr_begin' and len(self.streams) >= self.streaming.config['max_streams_per_process']:
                    raise VoiceError('STREAM_LIMIT', 'Restart worker after stream limit')
                job = dict(request=r, session=sid, epoch=epoch, cancelled=False, started=False,
                           submitted=time.perf_counter())
                state = None
                if op == 'asr_begin':
                    stream_id = uuid.uuid4().hex
                    state = dict(stream_id=stream_id,session=sid,epoch=epoch,status='OPEN',cancelled=False,
                                 native=None,next_seq=0,last_activity=time.monotonic())
                    self.streams[stream_id] = state
                    self.active_stream = stream_id
                    job['stream_id'] = stream_id
                elif op in {'asr_push', 'asr_finish'}:
                    state = self.streams[r['stream_id']]
                    job['stream_id'] = state['stream_id']
                self.jobs[r['request_id']] = job
                try:
                    self.tasks.put_nowait(job)
                except queue.Full:
                    self.jobs.pop(r['request_id'])
                    if op == 'asr_begin':
                        self.streams.pop(state['stream_id'])
                        self.active_stream = None
                    raise VoiceError('BUSY', 'Bounded work queue is full')
                if state:
                    state['last_activity'] = time.monotonic()
                    if op == 'asr_push':
                        state['next_seq'] += 1
                        if r.get('final', False):
                            state['status'] = 'INPUT_CLOSED'
                    elif op == 'asr_finish':
                        state['status'] = 'FINISH_QUEUED'
                self.emit(r, 'event', event='accepted', session_id=sid, epoch=epoch)
            except VoiceError as exc:
                self.error(r if isinstance(r, dict) else {}, exc.code, str(exc))

    def run_jobs(self):
        while True:
            try:
                job = self.tasks.get(timeout=.25)
            except queue.Empty:
                self.expire_streams()
                continue
            if job is None:
                self.tasks.task_done()
                return
            r = job['request']
            output_relative = None
            state = self.streams.get(job.get('stream_id'))
            with self.lock:
                job['started'] = not job['cancelled']
            try:
                if job['cancelled'] or state and state['cancelled']:
                    if (state and state['status'] == 'ERROR' and not job['cancelled'] and
                            self.sessions.get(job['session']) == job['epoch']):
                        self.error(r, 'STREAM_ABORTED', 'Earlier stream operation failed; start a new stream')
                    continue
                start = time.perf_counter()
                if self.test_delay_ms:
                    time.sleep(self.test_delay_ms / 1000)  # Explicit non-interruptible fixture.
                if r['op'] in STREAM_OPS:
                    cancelled = lambda: job['cancelled'] or state['cancelled']
                    if r['op'] == 'asr_begin':
                        self.streaming.begin(state)
                        payload = dict(stream_id=state['stream_id'],sample_rate=16000,channels=1,format='pcm_s16le',next_seq=0)
                    elif r['op'] == 'asr_push':
                        path = self.spool.resolve(r['pcm_path'],job['session'])
                        payload, text, changed = self.streaming.push(state,path,cancelled)
                        payload.update(stream_id=state['stream_id'],seq=r['seq'],input_closed=r.get('final',False))
                        with self.lock:
                            if changed and text and not cancelled() and self.sessions.get(job['session']) == job['epoch']:
                                self.emit(r,'event',event='partial',stream_id=state['stream_id'],session_id=job['session'],
                                    epoch=job['epoch'],seq=r['seq'],text=text,final=False,display_only=True,commit_allowed=False)
                    else:
                        payload = self.streaming.finish(state,cancelled)
                        payload.update(stream_id=state['stream_id'])
                    kind = 'result'
                elif r['op'] == 'transcribe':
                    path = self.spool.resolve(r['wav_path'], job['session'])
                    if self.asr:
                        payload = self.asr.transcribe(path, lambda: job['cancelled'])
                        kind = 'result'
                    else:
                        info = inspect_wav(path, asr=True)
                        payload = dict(code='MODEL_NOT_CONFIGURED', message='ASR engine is not configured',
                                       text=None, confidence=None, **info)
                        kind = 'error'
                else:
                    if not self.contract_tone and not self.tts:
                        raise VoiceError('MODEL_NOT_CONFIGURED', 'TTS engine is not configured')
                    dirname = r['output_dir']
                    directory = self.spool.make_directory(dirname, job['session'])
                    output_relative = dirname + '/' + uuid.uuid4().hex + '.wav'
                    path = directory / Path(output_relative).name
                    if self.tts:
                        payload = self.tts.synthesize(r['text'], path, lambda: job['cancelled'])
                        payload.update(wav_path=output_relative)
                    else:
                        payload = write_tone(path)
                        payload.update(wav_path=output_relative, text_sha256=hashlib.sha256(r['text'].encode()).hexdigest(),
                                       output_kind='NON_SPEECH_TEST_TONE', speech_quality='NOT_TESTED')
                    kind = 'result'
                payload.update(compute_ms=(time.perf_counter() - start) * 1000,
                               queue_ms=(start - job['submitted']) * 1000,
                               ready_ms=(time.perf_counter() - job['submitted']) * 1000,
                               audible_ms=None, memory=memory_snapshot(), session_id=job['session'], epoch=job['epoch'])
                with self.lock:
                    stale = job['cancelled'] or state and state['cancelled'] or self.sessions.get(job['session']) != job['epoch']
                    if stale:
                        if output_relative:
                            self.spool.remove_owned_file(output_relative, job['session'])
                    else:
                        if state:
                            state['last_activity'] = time.monotonic()
                            if r['op'] == 'asr_finish':
                                self.end_stream(state, 'FINISHED')
                        if output_relative:
                            self.owned.setdefault(job['session'], set()).add(output_relative)
                        job['completed'] = True
                        self.emit(r, kind, **payload)
            except VoiceError as exc:
                with self.lock:
                    if state:
                        self.end_stream(state, 'ERROR')
                    if not job['cancelled'] and self.sessions.get(job['session']) == job['epoch']:
                        self.error(r, exc.code, str(exc))
            except Exception:
                with self.lock:
                    if state:
                        self.end_stream(state, 'ERROR')
                    if not job['cancelled']:
                        self.error(r, 'IO_OR_INTERNAL_ERROR', 'Operation failed; no answer or speech produced')
                print('voice_C: operation failure; request contents omitted', file=sys.stderr, flush=True)
            finally:
                with self.lock:
                    if state and state['status'] not in {'ERROR', 'EXPIRED', 'RESET'} and (job['cancelled'] or state['cancelled'] or self.sessions.get(job['session']) != job['epoch']):
                        self.end_stream(state, 'CANCELLED')
                    self.jobs.pop(r['request_id'], None)
                self.tasks.task_done()

    def close(self):
        with self.lock:
            self.stopping = True
            for job in self.jobs.values():
                job['cancelled'] = True
            for state in self.streams.values():
                state['cancelled'] = True
        self.tasks.join()
        self.tasks.put(None)
        self.thread.join()
        with self.lock:
            for state in self.streams.values():
                self.end_stream(state, 'CLOSED')
            for sid, files in self.owned.items():
                for relative in files:
                    self.spool.remove_owned_file(relative, sid)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spool', type=Path, required=True)
    parser.add_argument('--contract-test-tone', action='store_true')
    parser.add_argument('--test-delay-ms', type=float, default=0)
    parser.add_argument('--asr-config', type=Path)
    parser.add_argument('--tts-config', type=Path)
    parser.add_argument('--stream-config', type=Path)
    parser.add_argument('--diagnostic-log', type=Path, help='New private directory for bounded metadata-only audit logs')
    args = parser.parse_args()
    if not math.isfinite(args.test_delay_ms) or not 0 <= args.test_delay_ms <= 1000:
        parser.error('Test delay must be finite and within 0..1000 ms')
    sys.stdout.reconfigure(encoding='utf-8', errors='strict')
    sys.stderr.reconfigure(encoding='utf-8', errors='strict')
    write_lock = threading.Lock()
    audit = None
    if args.diagnostic_log:
        from .audit import AuditLog
        audit = AuditLog(args.diagnostic_log)

    def emit(message):
        with write_lock:
            if audit:
                audit.write(message)
            print(json.dumps(message, ensure_ascii=False, allow_nan=False), flush=True)

    if (args.asr_config or args.tts_config) and (args.contract_test_tone or args.test_delay_ms):
        parser.error('Real engines cannot be combined with contract fixtures')
    asr = None
    stream_config = None
    if args.stream_config:
        if not args.asr_config:
            parser.error('--stream-config requires --asr-config')
        from .streaming import validate_config
        stream_config = validate_config(json.loads(args.stream_config.read_text(encoding='utf-8')))
    if args.asr_config:
        from .asr import Asr
        asr = Asr(args.asr_config, endpoint_config=stream_config)
    tts = None
    if args.tts_config:
        from .tts import Tts
        tts = Tts(args.tts_config)
    streaming = None
    if stream_config:
        from .streaming import StreamingAsr
        streaming = StreamingAsr(asr,stream_config)
    worker = Worker(args.spool, emit, args.contract_test_tone, args.test_delay_ms, asr=asr, tts=tts, streaming=streaming)
    try:
        stream = sys.stdin.buffer
        while not worker.stopping:
            raw = stream.readline(MAX_LINE + 1)
            if not raw:
                break
            if len(raw) > MAX_LINE:
                while raw and not raw.endswith(b'\n'):
                    raw = stream.readline(MAX_LINE + 1)
                worker.error({}, 'LINE_TOO_LARGE', 'JSONL line exceeds configured byte limit')
                continue
            try:
                r = json.loads(raw.decode('utf-8'), object_pairs_hook=unique_object,
                               parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Non-finite JSON')))
            except (UnicodeDecodeError, ValueError, RecursionError):
                worker.error({}, 'BAD_JSON', 'Invalid UTF-8 JSONL object')
                continue
            worker.handle(r)
    finally:
        worker.close()
        if audit:
            audit.close()


if __name__ == '__main__':
    main()
