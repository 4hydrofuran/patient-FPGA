"""Bind the post-validation board receipt to the exact installed program."""
import base64
import gzip
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'evidence/model_pl_A/20261024-cpu-opt-01-integrated-v1'


if __name__=='__main__':
    assert json.loads((OUT/'BOARD_AUDIT.json').read_text(encoding='utf-8'))['task01_complete']
    package=json.loads((OUT/'PACKAGE.json').read_text(encoding='utf-8'))
    data=dict(preflight=base64.b64encode(gzip.compress((ROOT/'platform/qwen35/a12/step06_preflight.py').read_bytes())).decode(),binary_sha256=package['configurations'][1]['program_sha256'])
    code=(ROOT/'platform/qwen35/a12/cpu01_deployment_receipt.py').read_text(encoding='utf-8')
    assert code.count('DATA=None')==1
    with (OUT/'deployment_reviewed.py').open('x',encoding='utf-8',newline='\n') as stream:stream.write(code.replace('DATA=None','DATA='+repr(data),1))
    print('POST_VALIDATION_DEPLOYMENT_RECEIPT_REVIEWED')
