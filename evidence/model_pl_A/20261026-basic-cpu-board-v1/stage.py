import json,tarfile,os
from pathlib import Path
source=Path('/home/ubuntu/a12-resident-incoming-20261026-v1/a12-resident-board-candidate-20261026-v1.tar.gz')
root=Path('/home/ubuntu/a12-resident-basic-20261026-v1');root.mkdir(mode=0o700)
with tarfile.open(source) as archive:
    archive.extractall(root,filter='data')
native=root/'a12-resident-20261026-v1/bin/qwen35-a12';native.chmod(0o700)
paths=['/opt/patient-qwen/artifacts/qwen35-0.8b/qwen35-text-Q4_K_M.gguf','/opt/patient-qwen/models/sidecar_A/qwen35-v1/manifest.json','/opt/patient-qwen/modules/linear_A/cpu_threads2_config.json']
mem={r.split(':')[0]:int(r.split()[1]) for r in Path('/proc/meminfo').read_text().splitlines() if r.startswith(('MemAvailable:','CmaFree:'))}
print('__A12_UPLOAD_BEGIN__',flush=True)
print(json.dumps(dict(status='STAGED_CPU_ONLY_NO_MODEL_YET',root=str(root),kernel=os.uname().release,assets={p:Path(p).is_file() for p in paths},memory_kib=mem)),flush=True)
print('__A12_UPLOAD_END__',flush=True)
