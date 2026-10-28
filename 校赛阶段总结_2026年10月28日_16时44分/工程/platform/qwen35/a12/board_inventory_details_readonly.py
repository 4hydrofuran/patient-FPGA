"""Additional inventory of project files and process names; no board writes."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

assert os.geteuid() == 0 and os.uname().machine == 'aarch64'
assert hashlib.sha256(Path('/etc/machine-id').read_bytes()).hexdigest() == 'ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec'
boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
directories = {}
for name in ('/opt/patient-qwen/modules/linear_A', '/opt/patient-qwen/artifacts/qwen35-0.8b',
             '/var/lib/kv260-a12/step08-generation-20261024-v1/bin',
             '/var/lib/kv260-a12/step08-generation-20261024-v1/lib',
             '/var/lib/kv260-a12/step08-generation-20261024-v1'):
    p = Path(name)
    directories[name] = sorted(x.name for x in p.iterdir()) if p.is_dir() else None
processes = subprocess.run(['ps', '-eo', 'pid,comm'], capture_output=True, text=True, check=True)
project_processes = [line for line in processes.stdout.splitlines()
                     if any(s in line.lower() for s in ('qwen', 'llama', 'whisper', 'vosk', 'piper'))]
locks = json.loads(Path('/opt/patient-qwen/models/model.lock.json').read_text())
assert boot == Path('/proc/sys/kernel/random/boot_id').read_text().strip()
print(json.dumps(dict(schema='BOARD_CONTENT_DETAILS_READONLY_V1',boot_id=boot,
    directories=directories, project_processes=project_processes, model_lock=locks,
    new_model_runs=0, PL_loads=0, service_changes=0, configuration_changes=0)), flush=True)
