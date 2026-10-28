"""Retain completed closeout failure; release only its proven-inactive marker."""
import json
import argparse
import os
from pathlib import Path
import sys
sys.path.insert(0, '/mnt/c/Patientqwen/platform/ra02')
from build_queue import CENTRAL, exclusive
ap = argparse.ArgumentParser()
ap.add_argument('--job', default='01791036929066514943-A-a06-closeout-v1-def2a14f')
ap.add_argument('--suffix', default='a06-closeout-v1')
args = ap.parse_args()
import re
assert re.fullmatch(r'[A-Za-z0-9-]+', args.suffix) and args.suffix.startswith('a06-')
JOB = args.job
with exclusive(CENTRAL):
    active = CENTRAL / 'active.json'
    request = json.loads(active.read_text())
    assert request['job'] == JOB
    assert request['owner'] == 'A' and '-A-a06-' in JOB
    receipt = json.loads((CENTRAL / 'results' / (JOB + '.json')).read_text())
    assert receipt['status'] == 'FAILED' and receipt['exit_code'] == 1
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit() or int(proc.name) == os.getpid():
            continue
        try:
            command = (proc / 'cmdline').read_bytes()
            cwd = (proc / 'cwd').resolve()
        except OSError:
            continue
        if JOB.encode() in command or JOB in cwd.parts:
            raise RuntimeError('Job-related process still alive: ' + proc.name)
    target = CENTRAL / ('active.failed-' + args.suffix + '.json')
    assert not target.exists()
    active.rename(target)
    print(json.dumps({'job': JOB, 'status': 'FAILED_MARKER_ARCHIVED_NOT_DELETED'}))
