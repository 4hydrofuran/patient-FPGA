"""Local bundle entry. Default is PLAN_ONLY; future board start needs fresh binding."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import time


def verify_bundle(directory):
    m = json.loads((directory / 'MANIFEST.json').read_text())
    for name, item in m['files'].items():
        data = (directory / name).read_bytes()
        if len(data) != item['bytes'] or hashlib.sha256(data).hexdigest() != item['sha256']:
            raise ValueError('Bundle changed: ' + name)
    return m


def validate_request(r):
    if r.get('authorized') is not True:
        raise ValueError('Request is unbound; no board operation authorized')
    if r['window'] != 'a13-fast-20261026-v1' or r['kernel'] != '6.8.0-1036-xilinx':
        raise ValueError('Window/kernel mismatch')
    if not re.fullmatch(r'[0-9a-f-]{36}', r.get('boot_id') or ''):
        raise ValueError('Fresh boot ID required')
    if not re.fullmatch(r'[0-9a-f]{64}', r.get('kernel_log_sha256') or ''):
        raise ValueError('Fresh reviewed kernel log required')
    if r['audible_output'] is not False or r['recording'] is not False or r['no_hot_restore'] is not True:
        raise ValueError('Only muted, no-hot-restore request supported')
    if not all(r.get(x) is True for x in ('recovery_exit_confirmed', 'physical_supply_confirmed',
                                         'other_PL_users_released')):
        raise ValueError('Maintenance/recovery context incomplete')
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--start', type=Path)
    args = ap.parse_args()
    directory = Path(__file__).resolve().parent
    m = verify_bundle(directory)
    if args.start is None:
        print(json.dumps({'status': 'PLAN_ONLY_NOT_EXECUTED', 'board_actions': 0,
                          'assets': list(m['assets']), 'hot_restore': False}))
        return
    raw = args.start.read_bytes()
    r = validate_request(json.loads(raw))
    if os.geteuid() != 0 or os.uname().machine != 'aarch64' or os.uname().release != r['kernel']:
        raise RuntimeError('Exact board/root/kernel required')
    if hashlib.sha256(Path('/etc/machine-id').read_bytes()).hexdigest() != r['machine_sha256']:
        raise RuntimeError('Board identity differs')
    if Path('/proc/sys/kernel/random/boot_id').read_text().strip() != r['boot_id']:
        raise RuntimeError('Stale boot binding')
    from control import Supervisor
    from runtime import worker_entry
    endpoint = Path('/var/lib/kv260-a13') / (r['window'] + '-control')
    endpoint.mkdir(mode=0o700)
    binding = hashlib.sha256(raw).hexdigest()
    manager = Supervisor(endpoint, binding, worker_entry,
                         {'bundle': str(directory), 'request': r, 'assets': m['assets']})
    print(json.dumps({'control_endpoint': str(manager.path), 'binding': binding,
                      'safe_release': False}), flush=True)
    while manager.worker.exitcode is None:
        manager.tick(.05)
    manager.tick(0)
    manager.close_endpoint_after_worker_exit()
    print(json.dumps(manager.state), flush=True)


if __name__ == '__main__': main()
