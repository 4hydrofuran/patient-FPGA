"""Cooperative queue bridge for one offline read-only Windows inspection.

Linux holds its own queue reservation. Only a matching native child exit receipt
releases it; interruption/unknown state retains the reservation. No board APIs.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / 'evidence/a13_A/20261024-audio-offline-signoff-v1'
CENTRAL = Path('/home/member-a/kv260-build/ra02-coordinator')
PWSH = 'C:/Users/Fang/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def status():
    result = subprocess.run(['C:/Windows/System32/wsl.exe', '-d', 'KV260-A-2204',
        '--exec', '/usr/bin/python3', '/mnt/c/Patientqwen/platform/ra02/build_queue.py', 'status'],
        capture_output=True, encoding='utf-8', check=True)
    return json.loads(result.stdout)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('mode', choices=['wait', 'native'])
    p.add_argument('--attempt', choices=['s01', 's02'], default='s01')
    args = p.parse_args()
    mode = args.mode
    WORK = ROOT / ('local/a13s_' + args.attempt)
    request_file = WORK / 'REQUEST.json'
    completion_file = WORK / 'COMPLETION.json'
    if mode == 'wait':
        assert sys.platform == 'linux'
        job = Path.cwd().name
        active = json.loads((CENTRAL / 'active.json').read_text())
        assert active['job'] == job and active['owner'] == 'A'
        assert active['scope'] == 'OFFLINE_BUILD_ONLY' and not active['board_authorized']
        assert Path.cwd().parent == CENTRAL / 'work'
        assert job.split('-A-')[1].startswith('a13-signoff-' + args.attempt + '-')
        request = {'job': job, 'id': uuid.uuid4().hex, 'scope': 'READ_ONLY_DCP_NO_BOARD',
                   'inputs': {name: sha(WORK / name) for name in
                       ['a06_routed.dcp', 'inspect_routed.tcl', 'run_inspect.ps1']}}
        save(request_file, request)
        print(json.dumps(request), flush=True)
        while not completion_file.exists():
            time.sleep(1)
        completion = json.loads(completion_file.read_text())
        assert completion['request'] == request
        assert completion['status'] == 'NATIVE_CHILD_EXITED'
        assert sha(WORK / 'native-execution.json') == completion['native_receipt_sha256']
        assert json.loads((WORK / 'native-execution.json').read_text())['exit_code'] == completion['exit_code']
        return completion['exit_code']
    assert sys.platform == 'win32'
    request = json.loads(request_file.read_text())
    active = status()['active']
    assert active['job'] == request['job'] and active['owner'] == 'A'
    assert not active['board_authorized'] and active['scope'] == 'OFFLINE_BUILD_ONLY'
    assert request['scope'] == 'READ_ONLY_DCP_NO_BOARD'
    for name, digest in request['inputs'].items():
        assert sha(WORK / name) == digest
    assert not completion_file.exists()
    spec = importlib.util.spec_from_file_location('a13_record', ROOT / 'platform/a1/record.py')
    record = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(record)
    code = record.run([PWSH, '-NoProfile', '-File', str(WORK / 'run_inspect.ps1'),
                       '-WorkDir', str(WORK)], WORK / 'native-execution.json', cwd=str(WORK))
    save(completion_file, {'request': request, 'status': 'NATIVE_CHILD_EXITED',
        'exit_code': code, 'native_receipt_sha256': sha(WORK / 'native-execution.json')})
    return code


if __name__ == '__main__':
    raise SystemExit(main())
