"""Archive the specifically observed, finished A07 failure; never erase it."""
import json
import os
from pathlib import Path
import sys
sys.path.insert(0, '/mnt/c/Patientqwen/platform/ra02')
from build_queue import CENTRAL, exclusive
JOB = '01791046699841960446-A-a07-control-20261004-v1-e59d084e'
with exclusive(CENTRAL):
    p = CENTRAL / 'active.json'
    request = json.loads(p.read_text())
    assert request['job'] == JOB and request['owner'] == 'A'
    result = json.loads((CENTRAL / 'results' / (JOB + '.json')).read_text())
    assert result['status'] == 'FAILED' and result['exit_code'] == 1
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit() or int(proc.name) == os.getpid():
            continue
        try:
            command = (proc / 'cmdline').read_bytes()
            cwd = (proc / 'cwd').resolve()
        except OSError:
            continue
        if JOB.encode() in command or JOB in cwd.parts or b'/a07/control/build.sh' in command:
            raise RuntimeError('Related A07 process is still alive: ' + proc.name)
    target = CENTRAL / 'active.failed-a07-control-20261004-v1.json'
    assert not target.exists()
    p.rename(target)
    print(json.dumps({'status': 'FINISHED_FAILURE_MARKER_ARCHIVED', 'job': JOB,
                      'prior_exit_code': 1, 'prior_failure_not_reclassified': True}))
