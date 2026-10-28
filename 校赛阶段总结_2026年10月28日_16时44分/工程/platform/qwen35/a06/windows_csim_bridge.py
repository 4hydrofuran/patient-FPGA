"""Hold the existing Linux build queue while executing native Windows Vitis.

WSL interop is disabled; do not re-enable it. A bounded file handshake allows
the Windows caller to run only after the normal shared queue owns its lock.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

R = Path(__file__).resolve().parents[3]
E = R / 'evidence/A06_acceptance/a-owned-closeout-v1'


def put(path, value):
    with path.open('x', encoding='utf-8') as f:
        json.dump(value, f, indent=2)


def linux_holder():
    # run-next already owns flock and active.json; never take a second lock.
    put(E / 'windows-ready.json', {'job_work': str(Path.cwd()), 'pid': os.getpid()})
    for unused in range(240):
        result = E / 'windows-done.json'
        if result.exists():
            try:
                return int(json.loads(result.read_text())['exit_code'])
            except json.JSONDecodeError:
                pass
        time.sleep(1)
    raise RuntimeError('Windows bridge timed out; retained failed queue marker')


def windows_run():
    assert not (E / 'windows-ready.json').exists()
    assert not (E / 'windows-done.json').exists()
    sys.path.insert(0, str(R / 'platform/a1'))
    from record import run
    command = ['wsl.exe', '-d', 'KV260-A-2204', '--', 'python3',
               '/mnt/c/Patientqwen/platform/ra02/build_queue.py', 'run-next']
    with (E / 'windows-queue.stdout').open('xb') as stdout, (E / 'windows-queue.stderr').open('xb') as stderr:
        proc = subprocess.Popen(command, stdout=stdout, stderr=stderr)
        for unused in range(60):
            if (E / 'windows-ready.json').exists():
                break
            if proc.poll() is not None:
                raise RuntimeError('Queue failed before handshake')
            time.sleep(1)
        else:
            raise RuntimeError('No queue readiness handshake')
        code = 127
        try:
            code = run([sys.executable, str(R / 'platform/qwen35/a06/closeout_csim.py'),
                        '--work', str(R / 'platform/build/a06-closeout-native-csim-v2'),
                        '--label', 'windows-csim-v2'], E / 'commands/windows-csim-native.json')
        finally:
            put(E / 'windows-done.json', {'exit_code': code})
        queue_code = proc.wait(timeout=60)
    put(E / 'windows-queue.json', {'argv': command, 'exit_code': queue_code, 'Csim_runner_exit': code})
    return code


if __name__ == '__main__':
    raise SystemExit(windows_run() if os.name == 'nt' else linux_holder())
