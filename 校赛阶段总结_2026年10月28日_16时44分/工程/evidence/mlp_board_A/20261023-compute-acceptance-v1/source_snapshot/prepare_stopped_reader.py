"""Build a separate read-only stopped-process evidence reader, PC only."""
import ast
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
EV=ROOT/'evidence/mlp_board_A/20261023-integration-v1'

if __name__=='__main__':
    out=EV/'stopped-reader-v1';out.mkdir(exist_ok=False)
    sources={'read_single_result.py':ROOT/'platform/qwen35/a11/read_stopped_open.py',
             'fetch_result.py':EV/'execution-host-v1/fetch_result.py'}
    for name,path in sources.items():
        text=path.read_text();ast.parse(text,str(path))
        with (out/name).open('x') as f:f.write(text)
    print(json.dumps(dict(board_contact=False,out=str(out))))
