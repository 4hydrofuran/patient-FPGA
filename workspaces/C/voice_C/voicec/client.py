"""Independent subprocess client; argument arrays, no shell, UTF-8 protocol only."""
import json
import os
import queue
import subprocess
import sys
import threading
import time
from collections import deque


class Client:
    def __init__(self, spool, contract_tone=False, test_delay_ms=0, asr_config=None, response_timeout=30, tts_config=None, stream_config=None, trace_callback=None, diagnostic_log=None):
        if (asr_config or tts_config) and (contract_tone or test_delay_ms):
            raise ValueError('Real engines cannot be combined with contract fixtures')
        self.response_timeout = response_timeout
        if stream_config and not asr_config:
            raise ValueError('Streaming requires ASR configuration')
        self.trace_callback = trace_callback
        self.trace_lock = threading.Lock()
        self.events = deque(maxlen=128)
        command = [sys.executable, '-m', 'voicec.worker', '--spool', str(spool)]
        if contract_tone:
            command += ['--contract-test-tone']
        if test_delay_ms:
            command += ['--test-delay-ms', str(test_delay_ms)]
        if asr_config:
            command += ['--asr-config', str(asr_config)]
        if tts_config:
            command += ['--tts-config', str(tts_config)]
        if stream_config:
            command += ['--stream-config', str(stream_config)]
        if diagnostic_log:
            command += ['--diagnostic-log', str(diagnostic_log)]
        self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, text=True, encoding='utf-8',
                                        env=os.environ | {'PYTHONUTF8': '1', 'PYTHONDONTWRITEBYTECODE': '1'})
        self.incoming = queue.Queue(maxsize=512)
        self.buffer = []
        self.stderr = []
        self.sequence = 0
        self.write_lock = threading.Lock()
        self.readers = [threading.Thread(target=self.read_stdout, daemon=True),
                        threading.Thread(target=self.read_stderr, daemon=True)]
        for t in self.readers:
            t.start()

    def read_stdout(self):
        try:
            for line in self.process.stdout:
                try:
                    message = json.loads(line)
                    if not isinstance(message, dict) or message.get('type') not in {'result', 'error', 'event'}:
                        raise ValueError('Invalid response')
                    self.trace('response',message)
                    self.incoming.put(message)
                except ValueError:
                    self.incoming.put(RuntimeError('Worker stdout is not protocol JSONL'))
        finally:
            self.incoming.put(EOFError('Worker stdout closed'))

    def read_stderr(self):
        for line in self.process.stderr:
            # Bounded diagnostic retention, never send stderr as protocol responses.
            self.stderr.append(line)
            self.stderr[:] = self.stderr[-64:]

    def send(self, op, request_id=None, **fields):
        with self.write_lock:
            self.sequence += 1
            rid = request_id or f'client-{self.sequence}'
            payload = dict(api_version=1, request_id=rid, op=op, **fields)
            self.trace('request',payload)
            self.process.stdin.write(json.dumps(payload, ensure_ascii=False, allow_nan=False) + '\n')
            self.process.stdin.flush()
            return rid

    def trace(self,direction,message):
        if self.trace_callback:
            with self.trace_lock:
                self.trace_callback(dict(direction=direction,monotonic=time.perf_counter(),message=message))

    def drain_events(self):
        result=list(self.events)
        self.events.clear()
        return result

    def receive(self, request_id, terminal=True, timeout=5):
        deadline = time.monotonic() + timeout
        while True:
            for i, item in enumerate(self.buffer):
                if item.get('request_id') == request_id and (not terminal or item['type'] != 'event'):
                    return self.buffer.pop(i)
            if terminal:
                events=[item for item in self.buffer if item.get('request_id')==request_id and item['type']=='event']
                self.events.extend(events)
                self.buffer=[item for item in self.buffer if not (item.get('request_id')==request_id and item['type']=='event')]
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('No matching worker response within timeout')
            try:
                item = self.incoming.get(timeout=remaining)
            except queue.Empty as exc:
                raise TimeoutError('No matching worker response within timeout') from exc
            if isinstance(item, Exception):
                raise item
            if len(self.buffer) >= 4096:
                raise RuntimeError('Client response buffer limit exceeded')
            self.buffer.append(item)

    def call(self, op, **fields):
        rid = self.send(op, **fields)
        return self.receive(rid, timeout=self.response_timeout)

    def close(self):
        if self.process.poll() is None:
            try:
                self.call('shutdown')
            except (BrokenPipeError, EOFError, TimeoutError):
                pass
            if not self.process.stdin.closed:
                self.process.stdin.close()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                self.process.wait(timeout=5)
        for reader in self.readers:
            reader.join(timeout=2)
        for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
            if not stream.closed:
                stream.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
