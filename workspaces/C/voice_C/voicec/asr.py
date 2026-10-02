"""Pinned local Zipformer CTC. No references, network fetches or decoder bias."""
import hashlib
import importlib.metadata
import inspect
import json
import time
from pathlib import Path
from .audio import VoiceError, read_pcm16
from .memory import memory_snapshot

ROOT = Path(__file__).resolve().parents[1]
MODEL_ID = 'csukuangfj/sherpa-onnx-streaming-zipformer-small-ctc-zh-int8-2025-04-01'
REVISION = 'a5f60fe00dcfbaf68fcc1c6b5cf53061e144d6da'
MODEL_HASH = '68c9c943840f7d9cf3e8a4970ba50f404feb5277f611fa82b7e72267786fa84a'
TOKEN_HASH = '6fed8c6c248516f38e7faa19404b57413e8ce259f1cbc1fa4aebc86eac32fdfd'
VERSIONS = {'sherpa-onnx': '1.13.8', 'sherpa-onnx-core': '1.13.8', 'numpy': '2.5.3'}


def validate_config(config):
    expected = {'api_version', 'num_threads', 'provider', 'decoding_method', 'tail_padding_ms'}
    if not isinstance(config, dict) or set(config) != expected:
        raise ValueError('ASR config fields must match the pinned local configuration')
    if type(config['api_version']) is not int or config['api_version'] != 1:
        raise ValueError('Require ASR api_version=1')
    if type(config['num_threads']) is not int or config['num_threads'] not in (1, 2, 4):
        raise ValueError('Threads must be 1, 2 or 4')
    if config['provider'] != 'cpu' or config['decoding_method'] != 'greedy_search':
        raise ValueError('Only CPU greedy CTC without bias is configured')
    if type(config['tail_padding_ms']) is not int or config['tail_padding_ms'] != 660:
        raise ValueError('Pinned official-example tail flush is 660 ms; original audio is never trimmed')
    return dict(config)


class Asr:
    def __init__(self, config_path, endpoint_config=None):
        start = time.perf_counter()
        self.config = validate_config(json.loads(Path(config_path).read_text(encoding='utf-8')))
        versions = {k: importlib.metadata.version(k) for k in VERSIONS}
        if versions != VERSIONS:
            raise ValueError('Installed dependencies do not match C01 lock')
        import numpy as np
        import sherpa_onnx
        self.np = np
        lock = json.loads((ROOT/'assets/asr/model.lock.json').read_text(encoding='utf-8'))
        if lock['model_id'] != MODEL_ID or lock['revision'] != REVISION:
            raise ValueError('Model provenance differs from pinned candidate')
        directory = ROOT/'assets/asr/zipformer-small-ctc-zh-int8-2025-04-01'
        model, tokens = directory/'model.int8.onnx', directory/'tokens.txt'
        for path, digest in ((model, MODEL_HASH), (tokens, TOKEN_HASH)):
            if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                raise ValueError('ASR model or token hash mismatch')
        factory = sherpa_onnx.OnlineRecognizer.from_zipformer2_ctc
        endpoint_parameters = {} if endpoint_config is None else {
            k: endpoint_config[k] for k in ('rule1_min_trailing_silence', 'rule2_min_trailing_silence', 'rule3_min_utterance_length')}
        self.recognizer = factory(tokens=str(tokens), model=str(model),
            num_threads=self.config['num_threads'], sample_rate=16000,
            enable_endpoint_detection=endpoint_config is not None,
            decoding_method='greedy_search', provider='cpu', **endpoint_parameters)
        self.metadata = dict(model_id=MODEL_ID, revision=REVISION, model_sha256=MODEL_HASH,
            tokens_sha256=TOKEN_HASH, dependencies=versions, config=self.config,
            decoder_bias='NONE', hotwords_configured=False,
            hotwords_factory_parameter_supported='hotwords_file' in inspect.signature(factory).parameters,
            underlying_model_streaming=True, public_streaming_ops=False,
            upstream_declared_license=lock['upstream_declared_license'],
            onnx_license_status='REVIEW_PENDING', redistribution='PENDING_NOT_APPROVED',
            load_ms=(time.perf_counter()-start)*1000, memory_after_load=memory_snapshot())

    def transcribe(self, path, cancelled=lambda: False):
        info, pcm = read_pcm16(path, asr=True)
        samples = self.np.frombuffer(pcm, dtype='<i2').astype(self.np.float32) / 32768.0
        stream = self.recognizer.create_stream()  # No recognition state shared between utterances.
        stream.accept_waveform(16000, samples)
        stream.accept_waveform(16000, self.np.zeros(10560, dtype=self.np.float32))
        stream.input_finished()
        steps = 0
        while self.recognizer.is_ready(stream):
            if cancelled():
                raise VoiceError('CANCELLED', 'ASR cancelled between decoder steps')
            self.recognizer.decode_stream(stream)
            steps += 1
        warnings = []
        if info['silent']: warnings.append('SILENT_INPUT')
        if info['clipped_samples']: warnings.append('CLIPPED_INPUT')
        if info['audio_duration_ms'] < 200: warnings.append('VERY_SHORT_INPUT')
        return dict(text=self.recognizer.get_result(stream), confidence=None, **info,
            warnings=warnings, tail_padding_ms=660, decode_steps=steps,
            amplitude_policy='PCM16_DIV_32768_NO_AGC_NO_TRIMMING_NO_DENOISING',
            model_sha256=MODEL_HASH, num_threads=self.config['num_threads'])
