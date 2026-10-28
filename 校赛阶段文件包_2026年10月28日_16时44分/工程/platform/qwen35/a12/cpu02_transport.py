"""Reuse pinned SSH/hidden authentication, with explicit CPU02 scope metadata."""
import importlib.util
import sys
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'platform/qwen35/a12'))
import step06_transport


if __name__=='__main__':
    rc=step06_transport.main()
    if '--output' in sys.argv:
        out=Path(sys.argv[sys.argv.index('--output')+1]);p=out/'reservation.json'
        if p.exists():
            original=p.read_bytes()
            with (out/'legacy-transport-reservation.json').open('xb') as stream:stream.write(original)
            data=json.loads(original);data['scope']='CPU02_REVIEWED_SCRIPT_SCOPE: preflight read-only OR bounded CPU+FPGA windows OR post-validation deployment receipt; exact script SHA identifies the action'
            p.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    raise SystemExit(rc)
