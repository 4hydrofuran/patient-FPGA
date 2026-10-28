"""Record local host-plan tests only; no serial/SSH/board execution."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import time


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('output', type=Path)
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[3]
    source = Path(__file__).resolve().parent
    commands = [
        ['D:/Python/Python314/python.exe', '-B', '-m', 'unittest', '-v',
         'test_upload_isolated_idle', 'test_isolated_launch', 'test_idle_result_audit'],
        ['C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe',
         '-NoLogo', '-NoProfile', '-ExecutionPolicy', 'Bypass',
         '-File', str(source / 'test_isolated_prepare_uart.ps1')],
    ]
    names = ('upload_isolated_idle.py', 'stage_isolated_idle.py', 'isolated_candidate_readonly.py',
             'launch_isolated_idle_once.py', 'read_isolated_result.py', 'fetch_isolated_result.py',
             'test_isolated_launch.py', 'isolated_prepare_uart.ps1',
             'audit_isolated_idle_result.py', 'test_idle_result_audit.py')
    result = dict(domain='PC_ONLY', board_contact=False, records=[],
                  host_sha256={name: hashlib.sha256((source / name).read_bytes()).hexdigest() for name in names})
    with args.output.open('x', encoding='utf-8') as stream:
        for argv in commands:
            now = datetime.now(timezone.utc).isoformat()
            start = time.monotonic()
            proc = subprocess.run(argv, cwd=source, capture_output=True, text=True, timeout=60)
            result['records'].append(dict(argv=argv, cwd=str(source), started_utc=now,
                                          elapsed_s=time.monotonic()-start, exit_code=proc.returncode,
                                          stdout=proc.stdout, stderr=proc.stderr))
        result['status'] = 'PASS_PC_HOST_PLANS' if all(r['exit_code'] == 0 for r in result['records']) else 'FAIL_PC'
        json.dump(result, stream, indent=2)
    print(json.dumps(result))
    return 0 if result['status'] == 'PASS_PC_HOST_PLANS' else 2


if __name__ == '__main__':
    raise SystemExit(main())
