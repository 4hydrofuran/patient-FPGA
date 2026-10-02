"""Pinned Matcha Baker + Vocos, original text, normal speed, no waveform cache."""
import hashlib
import importlib.metadata
import json
import time
from pathlib import Path
from .asr import VERSIONS
from .audio import VoiceError, write_speech
from .memory import memory_snapshot

ROOT = Path(__file__).resolve().parents[1]
MODEL_ID = 'csukuangfj/matcha-icefall-zh-baker'
REVISION = '75e64a57a80fb370abb18a4e4d86bb090ed46e93'
MODEL_HASH = 'ef7ebdf5987e16a5836136a51d6f3560ca997ffd33d06a40daab5af92b4b86e5'
VOCODER_HASH = '0574a135aa1db2de6e181050db2ec528496cacd4a4701fc5d7faf9f9804c0081'
MAX_TTS_TEXT = 160


def validate_config(config):
    expected = {'api_version', 'num_threads', 'provider', 'max_num_sentences',
                'speed', 'noise_scale', 'length_scale', 'silence_scale'}
    if not isinstance(config, dict) or set(config) != expected:
        raise ValueError('TTS requires the complete pinned configuration')
    if type(config['api_version']) is not int or config['api_version'] != 1:
        raise ValueError('Require api_version=1')
    if type(config['num_threads']) is not int or config['num_threads'] not in (1, 2, 4):
        raise ValueError('Threads must be 1, 2 or 4')
    if type(config['max_num_sentences']) is not int or config['max_num_sentences'] not in (1, 2):
        raise ValueError('Native sentence batch must be 1 or 2')
    if config['provider'] != 'cpu':
        raise ValueError('Only CPU is configured')
    for field in ('speed', 'noise_scale', 'length_scale', 'silence_scale'):
        if type(config[field]) not in (int, float) or config[field] != 1.0:
            raise ValueError('Normal speed and fixed native noise/pause settings required')
    return dict(config)


class Tts:
    def __init__(self, config_path):
        start = time.perf_counter()
        self.config = validate_config(json.loads(Path(config_path).read_text(encoding='utf-8')))
        versions = {k: importlib.metadata.version(k) for k in VERSIONS}
        if versions != VERSIONS:
            raise ValueError('Dependencies differ from existing C01 lock')
        lock = json.loads((ROOT/'assets/tts/model.lock.json').read_text(encoding='utf-8'))
        if lock['acoustic_model'] != MODEL_ID or lock['revision'] != REVISION:
            raise ValueError('Unexpected TTS provenance')
        assets = {}
        for item in lock['files']:
            relative = Path(item['path'])
            if relative.is_absolute() or '..' in relative.parts:
                raise ValueError('Invalid asset lock path')
            path = ROOT/relative
            if not path.resolve().is_relative_to((ROOT/'assets/tts').resolve()) or path.is_symlink():
                raise ValueError('Asset must remain in local TTS directory')
            if path.stat().st_size != item['bytes'] or hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
                raise ValueError('TTS asset hash mismatch')
            assets[path.name] = path
        if hashlib.sha256(assets['model-steps-3.onnx'].read_bytes()).hexdigest() != MODEL_HASH:
            raise ValueError('Pinned acoustic model hash mismatch')
        if hashlib.sha256(assets['vocos-22khz-univ.onnx'].read_bytes()).hexdigest() != VOCODER_HASH:
            raise ValueError('Pinned vocoder hash mismatch')
        # Initialize NumPy on the startup thread, before stdin and job threads.
        # Evidence: secondary-thread first import hung in create_module on Windows.
        import numpy
        self.np = numpy
        import sherpa_onnx
        self.generation_config = sherpa_onnx.GenerationConfig()
        self.generation_config.sid = 0
        self.generation_config.speed = 1.0
        self.generation_config.silence_scale = 1.0
        model = sherpa_onnx.OfflineTtsModelConfig(
            matcha=sherpa_onnx.OfflineTtsMatchaModelConfig(
                acoustic_model=str(assets['model-steps-3.onnx']), vocoder=str(assets['vocos-22khz-univ.onnx']),
                lexicon=str(assets['lexicon.txt']), tokens=str(assets['tokens.txt']),
                noise_scale=1.0, length_scale=1.0),
            num_threads=self.config['num_threads'], provider='cpu', debug=False)
        self.engine = sherpa_onnx.OfflineTts(sherpa_onnx.OfflineTtsConfig(
            model=model, rule_fsts=','.join(str(assets[k]) for k in ('phone.fst','date.fst','number.fst')),
            max_num_sentences=self.config['max_num_sentences'], silence_scale=1.0))
        if self.engine.sample_rate != 22050:
            raise ValueError('Expected native Baker 22050 Hz')
        self.metadata = dict(model_id=MODEL_ID, revision=REVISION, model_sha256=MODEL_HASH,
            vocoder_sha256=next(x['sha256'] for x in lock['files'] if x['path'].endswith('vocos-22khz-univ.onnx')),
            dependencies=versions, config=self.config, native_sample_rate=22050,
            weight_license='REVIEW_PENDING', training_data_restriction=lock['training_data_restriction'],
            cache_policy='MODEL_RESIDENCY_ONLY_NO_WAVEFORM_CACHE', text_policy='UNCHANGED_INPUT_NATIVE_FST_FRONTEND',
            generation_config=dict(sid=0, speed=1.0, silence_scale=1.0, api='EXPLICIT_GENERATION_CONFIG'),
            max_text_characters=MAX_TTS_TEXT,
            cancellation='NATIVE_BATCH_BOUNDARIES_AND_DISCARD_AFTER_RETURN',
            load_ms=(time.perf_counter()-start)*1000, memory_after_load=memory_snapshot())

    def synthesize(self, text, path, cancelled=lambda: False):
        if (not isinstance(text, str) or not text.strip() or len(text) > MAX_TTS_TEXT or
                any(ord(c) < 32 and c not in '\t\n' for c in text)):
            raise VoiceError('BAD_TTS_TEXT', 'Require nonempty short text of at most 160 characters')
        if cancelled():
            raise VoiceError('CANCELLED', 'TTS cancelled before native inference')
        start = time.perf_counter()
        callbacks = []

        def callback(samples, progress):
            callbacks.append(dict(elapsed_ms=(time.perf_counter()-start)*1000,
                                  frames=len(samples), progress=float(progress)))
            # Pinned C++ multi-batch implementation: 1 continues, 0 stops.
            # Single batch ignores callback return; check again after generate.
            return 0 if cancelled() else 1

        audio = self.engine.generate(text, self.generation_config, callback=callback)
        if cancelled():
            raise VoiceError('CANCELLED', 'Native TTS returned; cancelled audio discarded')
        result = write_speech(path, audio.samples, audio.sample_rate)
        result.update(text_sha256=hashlib.sha256(text.encode('utf-8')).hexdigest(),
            output_kind='SYNTHESIZED_SPEECH', speech_quality='HUMAN_REVIEW_PENDING',
            native_callbacks=callbacks, first_internal_chunk_ms=callbacks[0]['elapsed_ms'] if callbacks else None,
            internal_chunk_is_client_ready=False, first_sentence_ready_ms=None,
            model_sha256=MODEL_HASH, num_threads=self.config['num_threads'],
            speed=1.0, cache_hit=False, waveform_cache='DISABLED')
        return result
