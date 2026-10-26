"""Synthesize a bounded nonclinical test sentence to two WAV files; never play."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import resource
import sys
import time

import numpy as np
import scipy
import sherpa_onnx as so

from .pcm import convert, float_mono, read_mono, write_pcm16


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_assets(root):
    root = Path(root).resolve(strict=True)
    lock = json.loads((root / 'modules/voice_A/resources.lock.json').read_text())
    paths = [root / name for name in lock['files'] if
             name.startswith('artifacts/voice_A/matcha-icefall-zh-baker/') or
             name == 'artifacts/voice_A/vocos-22khz-univ.onnx']
    if not paths or so.__version__ != lock['sherpa_onnx'] or np.__version__ != '1.26.4' or scipy.__version__ != '1.15.3':
        raise ValueError('pinned model/runtime versions required')
    for path in paths:
        if path.is_symlink() or not path.resolve(strict=True).is_relative_to(root) or sha(path) != lock['files'][path.relative_to(root).as_posix()]:
            raise ValueError('missing, linked or changed model asset: ' + path.name)
    return root, lock, paths


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--text', default='你好，这是离线语音测试。')
    p.add_argument('--threads', type=int, choices=[1, 2], default=1)
    p.add_argument('--gain-db', type=float, default=-30.0)
    p.add_argument('--pc-validation', action='store_true', help='explicit PC-only validation; never changes an audio gate')
    args = p.parse_args()
    if not args.pc_validation and (platform.machine() != 'aarch64' or sys.version_info[:2] != (3, 12)):
        raise RuntimeError('target requires aarch64/CPython3.12; PC evidence must be explicitly labelled')
    if not args.text.strip() or len(args.text) > 128 or '\x00' in args.text:
        raise ValueError('test text must be nonempty and at most 128 characters')
    if not np.isfinite(args.gain_db) or not -90 <= args.gain_db <= 0:
        raise ValueError('invalid file gain')
    root, lock, paths = check_assets(args.root)
    if args.output_dir.is_symlink() or args.output_dir.exists():
        raise FileExistsError('a new output directory is required')
    args.output_dir.mkdir(parents=True, exist_ok=False)
    model = root / 'artifacts/voice_A/matcha-icefall-zh-baker'
    started = time.monotonic()
    config = so.OfflineTtsConfig(model=so.OfflineTtsModelConfig(matcha=so.OfflineTtsMatchaModelConfig(
        acoustic_model=str(model / 'model-steps-3.onnx'), vocoder=str(root / 'artifacts/voice_A/vocos-22khz-univ.onnx'),
        lexicon=str(model / 'lexicon.txt'), tokens=str(model / 'tokens.txt')),
        num_threads=args.threads, provider='cpu'),
        rule_fsts=','.join(str(model / name) for name in ['phone.fst', 'date.fst', 'number.fst']), max_num_sentences=2)
    if not config.validate():
        raise ValueError('invalid fixed TTS configuration')
    tts = so.OfflineTts(config)
    loaded = time.monotonic()
    generation = so.GenerationConfig()
    generation.sid = 0
    generation.speed = 1.0
    generation.silence_scale = 1.0
    audio = tts.generate(args.text, generation)
    generated = time.monotonic()
    x = float_mono(audio.samples)
    if int(audio.sample_rate) != 22050:
        raise ValueError('unexpected TTS sample rate')
    source = args.output_dir / 'tts-22050-mono.wav'
    output = args.output_dir / 'tts-48000-stereo.wav'
    write_pcm16(source, np.rint(x * 32767).astype('<i2'), 22050)
    pcm, conversion = convert(read_mono(source), int(audio.sample_rate), args.gain_db)
    conversion['source'] = 'exact_saved_22050_mono_PCM16_WAV'
    write_pcm16(output, pcm, 48000)
    result = {'status': 'SYNTHESIZED_FILES_ONLY_NOT_PLAYED',
              'domain': 'PC_x86_64' if args.pc_validation else 'BOARD_TTS_FILE_ONLY',
              'architecture': platform.machine(), 'python': platform.python_version(),
              'sherpa_onnx': so.__version__, 'numpy': np.__version__, 'scipy': scipy.__version__,
              'threads': args.threads, 'speaker_id': 0, 'speed': 1.0, 'silence_scale': 1.0,
              'text': args.text, 'load_ms': (loaded - started) * 1000,
              'synthesis_ms': (generated - loaded) * 1000,
              'conversion': conversion, 'source_duration_s': len(x) / 22050,
              'output_duration_s': len(pcm) / 48000,
              'max_rss_KiB_linux': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              'nonzero_output_samples': int(np.count_nonzero(pcm)),
              'pcm_abs_peak': int(np.max(np.abs(pcm.astype(np.int32)))),
              'file_sha256': {path.name: sha(path) for path in [source, output]},
              'verified_tts_asset_count': len(paths), 'playback': False, 'capture': False,
              'measured_current_mA': None, 'audible_onset_ms': None,
              'model_lock_sha256': sha(root / 'modules/voice_A/resources.lock.json'),
              'redistribution_allowed': False}
    if result['nonzero_output_samples'] == 0:
        raise ValueError('empty-signal TTS result')
    with (args.output_dir / 'RESULT.json').open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps({k: result[k] for k in ['status', 'domain', 'load_ms', 'synthesis_ms', 'source_duration_s', 'max_rss_KiB_linux', 'playback']}))


if __name__ == '__main__':
    main()
