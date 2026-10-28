"""PC evidence extraction from an already completed, framed UART receipt."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import re
import zlib


def extract(record):
    if not record.get('closed') or record.get('exit_code')!=0 or record.get('error'):
        raise ValueError('UART command incomplete or failed')
    rows=[]
    for event in record['events']:
        if event['kind']!='result':continue
        for line in re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','',event['text']).splitlines():
            if line.startswith('{') and line.endswith('}'):rows.append(json.loads(line))
    if len(rows)!=1:raise ValueError('unique framed result object required')
    return rows[0]


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--record',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True);args=ap.parse_args()
    obj=extract(json.loads(args.record.read_text(encoding='utf-8-sig')))
    args.out.mkdir(exist_ok=False)
    with (args.out/'result.json').open('x',encoding='utf-8') as f:json.dump(obj,f,indent=2)
    if 'baseline_zlib_base64' in obj:
        raw=zlib.decompress(base64.b64decode(obj['baseline_zlib_base64'],validate=True))
        assert len(raw)==obj['baseline_bytes'] and hashlib.sha256(raw).hexdigest()==obj['baseline_sha256']
        with (args.out/'baseline.raw.txt').open('xb') as f:f.write(raw)
    print(json.dumps({k:v for k,v in obj.items() if k not in ('baseline_zlib_base64','process_scan','native_mappings')}))


if __name__=='__main__':main()
