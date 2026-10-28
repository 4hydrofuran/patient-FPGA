"""PC decode/hash validation of one candidate read-only UART capture."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import zlib

from kernel_log_gate import diagnostics


def decode(capture, output):
    report = json.loads(Path(capture).read_text(encoding='utf-8-sig'))
    assert report['closed'] is True and report['exit_code'] == 0
    rows = [json.loads(line) for event in report['events'] if event['kind'] == 'result'
            for line in event['text'].splitlines() if line.startswith('{"status": "READONLY_CANDIDATE_REVIEW_REQUIRED"')]
    assert len(rows) == 1
    data = rows[0]
    raw = zlib.decompress(base64.b64decode(data.pop('baseline_zlib_base64'), validate=True))
    assert len(raw) == data['baseline_bytes'] and hashlib.sha256(raw).hexdigest() == data['baseline_sha256']
    output = Path(output)
    output.mkdir()
    with (output / 'baseline.raw.txt').open('xb') as stream:
        stream.write(raw)
    entries = diagnostics(raw.decode('utf-8'))
    for name, value in (('candidate_observation.json', data), ('baseline_diagnostics.json', entries)):
        with (output / name).open('x', encoding='utf-8') as stream:
            json.dump(value, stream, indent=2)
    print(json.dumps(dict(status='DECODED_HASH_VERIFIED_NOT_BASELINE_APPROVAL', boot_id=data['boot_id'],
                          baseline_sha256=data['baseline_sha256'], diagnostics=len(entries), output=str(output))))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('capture', type=Path)
    ap.add_argument('output', type=Path)
    args = ap.parse_args()
    decode(args.capture, args.output)
