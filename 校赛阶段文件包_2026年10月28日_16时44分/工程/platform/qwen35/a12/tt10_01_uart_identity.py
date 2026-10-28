"""Unprivileged, read-only board identity/network probe for an authenticated UART."""
import hashlib
import json
from pathlib import Path
import os
import subprocess

def command(argv):
    p=subprocess.run(argv,capture_output=True,text=True,timeout=5)
    return dict(exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr)

def exists(path):
    try:return dict(exists=Path(path).exists(),observation_error=None)
    except OSError as exc:return dict(exists=None,observation_error=type(exc).__name__+': '+str(exc))

print('__TT10_UART_IDENTITY_BEGIN__',flush=True)
print(json.dumps(dict(scope='READ_ONLY_IDENTITY_AND_NETWORK_NO_SUDO',uid=os.getuid(),machine_sha256=hashlib.sha256(Path('/etc/machine-id').read_bytes()).hexdigest(),
    boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),kernel=os.uname().release,hostname=os.uname().nodename,
    interfaces=command(['ip','-4','-br','addr']),routes=command(['ip','-4','route']),
    old_manager=exists('/proc/167484'),old_worker=exists('/proc/167575'),
    active_lease=exists('/var/lock/kv260-a1/active/lease.json'))),flush=True)
print('__TT10_UART_IDENTITY_END__',flush=True)
