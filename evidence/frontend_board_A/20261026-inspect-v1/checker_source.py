import json,zlib,base64
from pathlib import Path
b=Path('/home/ubuntu/patient-web-demo-20261026/web_gateway')
r={n:(b/n).read_text() for n in ['src/patient_web/reference/checking.py','tests/gateway/native_pl_reference.txt','src/patient_web/static/console.js'] if (b/n).is_file()}
print('__FRONTEND_'+'BEGIN__',flush=True)
print(base64.b64encode(zlib.compress(json.dumps(r).encode())).decode(),flush=True)
print('__FRONTEND_'+'END__',flush=True)
