"""Capture actual ASR responses only after authorized-audio validation."""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from voicec.client import Client
from voicec.dataset import validate_plan
from voicec.metrics import aggregate


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--audio-root', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--asr-config', type=Path, required=True)
    args = p.parse_args()
    rows = [json.loads(s) for s in args.manifest.read_text(encoding='utf-8').splitlines() if s.strip()]
    validate_plan(rows, args.audio_root, require_recordings=True)
    outputs = []
    with Client(args.audio_root, asr_config=args.asr_config) as c:
        hello = c.call('hello')
        if not hello['capabilities']['real_asr']:
            raise RuntimeError('No real ASR engine configured; cannot produce speech-quality report')
        for row in rows:
            start = time.perf_counter()
            response = c.call('transcribe', session_id=row['recording_id'], language='zh', wav_path=row['audio_path'])
            outputs.append(dict(recording_id=row['recording_id'], status='SUCCESS' if response['type'] == 'result' else 'ERROR',
                audio_sha256=row['audio_sha256'], execution_kind=response['execution_kind'],
                text=response.get('text'), compute_ms=response.get('compute_ms'),
                audio_duration_ms=response.get('audio_duration_ms'), ready_ms=response.get('ready_ms'),
                peak_rss_bytes=response.get('memory', {}).get('peak_rss_bytes'),
                client_elapsed_ms=(time.perf_counter()-start)*1000, response=response))
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output/'responses.jsonl').write_text('\n'.join(json.dumps(r, ensure_ascii=False) for r in outputs)+'\n', encoding='utf-8')
    (args.output/'report.json').write_text(json.dumps(aggregate(rows, outputs), ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()
