from cpu02_support import snapshot
import cpu01b_observer as ob
"""Fresh per-permit health without rescanning every process; complete scans stay at lifecycle boundaries."""
import hashlib
import os
from pathlib import Path
from capacity_policy import admission

def compact_kernel_record(run, data):
    with ob.span('health.archive_total'):
        raw = data.pop('raw_log', None)
        if raw is not None:
            with ob.span('health.archive_encode'):
                representation = snapshot(raw)
                payload = representation.payload
            with ob.span('health.archive_hash'):
                pin = representation.sha256
            folder = Path(run) / 'kernel'
            folder.mkdir(exist_ok=True)
            p = folder / (pin + '.raw')
            with ob.span('health.archive_check_or_write'):
                if p.exists():
                    if p.read_bytes() != payload:
                        raise RuntimeError('kernel snapshot collision')
                else:
                    with p.open('xb') as f:
                        f.write(payload)
                        f.flush()
                        os.fsync(f.fileno())
            data.update(raw_log_file='kernel/' + p.name, raw_log_sha256=pin)
        return data

def live_snapshot(boot, *, full_resident=False):
    if Path('/proc/sys/kernel/random/boot_id').read_text().strip() != boot:
        raise RuntimeError('boot changed')
    temps = [int(p.read_text()) for p in Path('/sys/class/hwmon').glob('hwmon*/temp*_input')]
    if not temps or any((not 0 < t < 55000 for t in temps)):
        raise RuntimeError('temperature gate')
    mem = {l.split(':')[0]: int(l.split()[1]) for l in Path('/proc/meminfo').read_text().splitlines()}
    if mem['MemAvailable'] < 1114112 or mem['CmaFree'] < 98304:
        raise RuntimeError('full-model live extra reserve gate')
    return dict(temperatures_mC=temps, memory_kib={k: mem[k] for k in ('MemAvailable', 'CmaFree', 'CmaTotal')}, full_resident=full_resident, actual_reserve=admission(mem, 140591104, already_charged_bo_bytes=140591104) if full_resident else None)
