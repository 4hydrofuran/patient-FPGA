import json,zlib,base64
from pathlib import Path
b=Path('/home/ubuntu/patient-web-demo-20261026')
names=['README-BOARD.txt','OPEN_ME.txt','deployment.json','start-demo.sh','start-native.sh','board-demo-acceptance.json','web-demo.log','web-demo.pid','web_gateway/UPSTREAM.json','web_gateway/docs/MODEL_HANDOFF.md','web_gateway/docs/BOARD_DEMO_QUICKSTART.md','web_gateway/docs/API.md','web_gateway/src/patient_web/__main__.py','web_gateway/src/patient_web/engine.py','web_gateway/src/patient_web/managed.py','web_gateway/src/patient_web/api.py','web_gateway/src/patient_web/manager.py','web_gateway/pyproject.toml']
r={n:(b/n).read_text()[:90000] for n in names if (b/n).is_file()}
print('__FRONTEND_'+'BEGIN__',flush=True)
print(base64.b64encode(zlib.compress(json.dumps(r,ensure_ascii=True).encode())).decode(),flush=True)
print('__FRONTEND_'+'END__',flush=True)
