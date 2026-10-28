"""Upload only the pinned reviewed gzip to the already selected board."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'platform/qwen35/a10'))
from fetch_single_result import plan


if __name__=='__main__':
    out=ROOT/'evidence/model_pl_A/20261024-cpu-opt-02-v1'
    spec=json.loads((out/'PACKAGE.json').read_text(encoding='utf-8'))
    raw=(out/'board_driver_reviewed.py.gz').read_bytes()
    assert hashlib.sha256(raw).hexdigest()==spec['gzip_sha256']
    fresh=json.loads((out/'preflight_01/stdout.txt').read_text(encoding='utf-8'))
    assert Path(spec['remote_driver']).name not in fresh['home_top_level']
    args,_=plan()
    argv=['C:/Windows/System32/OpenSSH/scp.exe',*args[2:-2],str(out/'board_driver_reviewed.py.gz'),'ubuntu@192.168.2.2:'+spec['remote_driver']]
    with (out/'UPLOAD.json').open('x',encoding='utf-8') as stream:
        json.dump(dict(status='RESERVED',argv=argv,sha256=spec['gzip_sha256']),stream)
    rc=subprocess.run(argv).returncode
    with (out/'UPLOAD_RECEIPT.json').open('x',encoding='utf-8') as stream:json.dump(dict(exit_code=rc,sha256=spec['gzip_sha256']),stream)
    raise SystemExit(rc)
