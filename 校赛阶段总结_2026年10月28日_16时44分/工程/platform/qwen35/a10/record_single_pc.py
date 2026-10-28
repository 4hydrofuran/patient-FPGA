"""Record bounded PC-only checks for the pending one-call release workflow."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[3]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--phase', choices=['contracts', 'tests', 'package', 'host_tests', 'abi', 'audit_tests'], required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    if args.phase == 'contracts':
        commands = [['D:/Python/Python314/python.exe', '-B', str(ROOT/'scripts/release'/name)]
                    for name in ('check_contracts.py', 'qwen35_config.py')]
    elif args.phase == 'tests':
        commands = [['wsl.exe', '-d', 'KV260-A-2204', '--cd', '/mnt/c/Patientqwen/platform/qwen35/a10',
                     '/usr/bin/python3', '-B', '-m', 'unittest', '-v',
                     'test_single_compute', 'test_single_integration_pc']]
    elif args.phase == 'package':
        commands = [['D:/Python/Python314/python.exe', '-B', str(ROOT/'platform/qwen35/a10/prepare_isolated_single.py'),
                     '--project-root', str(ROOT), '--output', str(ROOT/'platform/local/a10-isolated-single-20261023-v1')]]
    elif args.phase in ('host_tests', 'audit_tests'):
        commands = [['D:/Python/Python314/python.exe', '-B', '-m', 'unittest',
                     'discover', '-v', '-s', str(ROOT/'platform/qwen35/a10'), '-p',
                     'test_single_host.py' if args.phase == 'host_tests' else 'test_single_result_audit.py']]
    else:
        base = '/home/member-a/a10-driver-audit-20261018/xrt-userspace/usr/include/xrt/xrt/'
        paths = [base+'xrt_bo.h', base+'xrt_kernel.h']
        symbols = '^(xrtBOAlloc|xrtBOFree|xrtBOMap|xrtBOAddress|xrtBOSize|xrtBOSync|xrtRunOpen|xrtRunClose|xrtRunSetArg|xrtRunStart|xrtRunState)\\('
        commands = [['wsl.exe', '-d', 'KV260-A-2204', '--exec', '/usr/bin/sha256sum', *paths],
                    ['wsl.exe', '-d', 'KV260-A-2204', '--exec', '/usr/bin/grep', '-B', '2', '-A', '1', '-E', symbols, *paths]]
    result = dict(domain='PC_ONLY', board_contact=False, phase=args.phase, records=[])
    with args.output.open('x', encoding='utf-8') as stream:
        for command in commands:
            start = time.monotonic()
            utc = datetime.now(timezone.utc).isoformat()
            proc = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=60)
            result['records'].append(dict(argv=command, cwd=str(ROOT), started_utc=utc,
                                          elapsed_s=time.monotonic()-start, exit_code=proc.returncode,
                                          stdout=proc.stdout.decode('utf-8', errors='replace'),
                                          stderr=proc.stderr.decode('utf-8', errors='replace')))
        result['status'] = 'PASS_PC_ONLY' if all(r['exit_code'] == 0 for r in result['records']) else 'FAIL_PC'
        json.dump(result, stream, indent=2)
    print(json.dumps(result))
    return 0 if result['status'] == 'PASS_PC_ONLY' else 2


if __name__ == '__main__':
    raise SystemExit(main())
