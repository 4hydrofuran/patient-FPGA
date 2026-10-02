"""Read-only board environment capture; does not install, record or claim pass."""
import json
import os
from pathlib import Path
import platform
import sys

parser_error = None
info=dict(os=platform.system(),machine=platform.machine(),python=platform.python_version(),
    libc=platform.libc_ver(),target_cpu='Cortex-A53 ARMv8-A',board_identity=None,
    worker_execution='NOT_TESTED',microphone='NOT_OPENED')
if sys.platform=='linux':
    for name in ('/proc/cpuinfo','/etc/os-release'):
        p=Path(name)
        info[name]=p.read_text('utf-8',errors='replace') if p.is_file() else None
info['compatible_environment_prerequisites']=sys.platform=='linux' and platform.machine().lower() in ('aarch64','arm64') and sys.version_info[:2]==(3,12)
print(json.dumps(info,ensure_ascii=False,indent=2))
raise SystemExit(0 if info['compatible_environment_prerequisites'] else 2)
