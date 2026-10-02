"""Freeze one development candidate; absent human final data stays absent."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'evidence/c04'


def main():
    path = OUT / 'freeze.json'
    if path.exists():
        raise RuntimeError('Freeze already exists; do not retune a frozen candidate')
    names = ['configs/asr.selected.json', 'configs/tts.selected.json', 'configs/stream.selected.json',
             'assets/asr/model.lock.json', 'assets/tts/model.lock.json', 'requirements-c01.lock.txt',
             'assets/wheels/wheels.lock.json', 'data/c01_public/manifest.jsonl', 'data/c02_scripts/manifest.jsonl',
             'data/recording_plan.jsonl']
    freeze = dict(candidate='C_pc_candidate_v1', status='ENGINEERING_FREEZE_HUMAN_FINAL_TEST_PENDING',
        date='2026-10-02', pc_threads=2, tts_batch=1, tts_speed=1.0, tts_silence_scale=1.0,
        endpoint_seconds=1.2, chunk_ms=200, final_policy='EXPLICIT_FINISH_ONLY',
        datasets=dict(public_asr='EXISTING_C01_DEVELOPMENT_NOT_FINAL_TEST', tts='C02_AUTHORED_DEVELOPMENT',
                      final_authorized_human_audio=0, final_reference_text=None, human_listening_pending=14),
        gates=dict(target_authorized_mandarin_cer=0.15, observed_public_dev_cer=148/606,
                   final_cer=None, human_key_item_errors=None, audible_latency=None,
                   licenses='REVIEW_PENDING', board='NOT_TESTED', adoption='UNDECIDED'),
        prohibited=['tune against final answers', 'substitute planned text for spoken truth', 'include private recordings',
                    'distribute pending-license weights', 'claim PC as board'],
        files=[dict(path=n, sha256=hashlib.sha256((ROOT/n).read_bytes()).hexdigest()) for n in names])
    path.write_text(json.dumps(freeze, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print('Development candidate and existing dataset hashes frozen; human final test remains pending.')


if __name__ == '__main__': main()
