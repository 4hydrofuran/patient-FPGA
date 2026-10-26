"""Register CPU02 only after actual safety and predeclared performance acceptance."""
import base64
import gzip
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'evidence/model_pl_A/20261024-cpu-opt-02-v1'


if __name__=='__main__':
    audit=json.loads((OUT/'BOARD_AUDIT.json').read_text(encoding='utf-8'))
    perf=json.loads((OUT/'PERFORMANCE.json').read_text(encoding='utf-8'))
    assert audit['task02_complete'] and perf['accepted']
    package=json.loads((OUT/'PACKAGE.json').read_text(encoding='utf-8'))
    data=dict(preflight=base64.b64encode(gzip.compress((ROOT/'platform/qwen35/a12/step06_preflight.py').read_bytes())).decode(),binary_sha256=package['native_program_sha256'])
    code=(ROOT/'platform/qwen35/a12/cpu01_deployment_receipt.py').read_text(encoding='utf-8')
    code=code.replace('DATA=None','DATA='+repr(data),1).replace('cpu01-integrated-20261024-v1','cpu02-candidate-20261024-v1')
    code=code.replace('==3816','==4896').replace('CPU01_DIAGNOSTIC_VERSION','CPU02_OPTIMIZED_MANAGER_VERSION')
    code=code.replace("rollback='/var/lib/kv260-a12/health-opt-20261024-v1'","rollback='/var/lib/kv260-a12/cpu01-integrated-20261024-v1'")
    compile(code,'cpu02_deployment','exec')
    with (OUT/'deployment_reviewed.py').open('x',encoding='utf-8',newline='\n') as stream:stream.write(code)
    print('CPU02_ACCEPTED_POST_VALIDATION_RECEIPT_READY')
