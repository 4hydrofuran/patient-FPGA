"""Explicit continuation of the preserved IRQ-enumeration diagnostic, not a retry.

Verify the real DT's 32 IRQ descriptors before classifying index 32 as end-of-list.
Never bypass refcount/other errors. Finish the original idle unload BEFORE compute.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import time
sys.dont_write_bytecode = True
OLD = Path('/home/ubuntu/a10-minimal-20261021-v1')
sys.path.append(str(OLD))
from minimal_gate import MinimalGate, IRQ_END
from minimal_trial import (MinimalTrial, BOOT, KERNEL, PACKAGE, DRIVER, DRIVER_SHA, BOOT_FILES,
                           MACHINE, CENTRAL, DEFAULT, RESTORE, need, digest,
                           check_loaded, check_removed, active_handle)

STOP_SHA = '64567c47115b809aef701d98ed4c018073ddb8141cbb49bd347b278d19ce5dc5'


def decode_irq_descriptors(raw, parent, cells):
    need(cells == 2 and len(raw) == 32 * 12, 'IRQ DT size/cells differs')
    triples = [struct.unpack('>III', raw[i:i+12]) for i in range(0, len(raw), 12)]
    need(triples == [(parent, i, 4) for i in range(32)], 'IRQ DT sequence/flags/parent differs')
    return triples


class Continuation(MinimalTrial):
    def __init__(self, bundle_sha):
        here = Path(__file__).resolve().parent
        need(digest(here / 'continuation.manifest.json') == bundle_sha, 'continuation manifest differs')
        m = json.loads((here / 'continuation.manifest.json').read_text())
        need(set(p.name for p in here.iterdir()) == set(m) | {'continuation.manifest.json'},
             'continuation inventory differs')
        for name, sha in m.items():
            need(digest(here / name) == sha, 'continuation file differs')
        need(digest(OLD / 'manifest.json') ==
             '2d56e04fc7c05db0ceb188db86e5a2feef3694ca2379acc7f7ec373d2524b528',
             'original manifest differs')
        for name, entry in json.loads((OLD / 'manifest.json').read_text())['files'].items():
            need(digest(OLD / name) == entry['sha256'], 'original payload differs')
        need(digest(OLD / 'idle-result.jsonl') == STOP_SHA, 'failure record differs')
        rows = [json.loads(l) for l in (OLD / 'idle-result.jsonl').read_text().splitlines()]
        need(rows[-1]['event'] == 'STOP_NO_AUTOMATIC_RECOVERY' and
             not any(r['event'].startswith('COMPUTE_') for r in rows), 'unexpected prior progress')
        gate = [r for r in rows if r['event'] == 'KERNEL_LOG_GATE'][-1]
        need(len(gate['rejected_diagnostics']) == 1 and
             gate['rejected_diagnostics'][0]['text'].endswith(IRQ_END), 'not exact IRQ sentinel stop')
        self.source = OLD
        self.log = (here / 'continuation.jsonl').open('x', encoding='utf-8')
        self.kernel_gate = MinimalGate()
        self.emit('CONTINUATION_OF_PRESERVED_STOP', stop_sha256=STOP_SHA,
                  review='XRT zocl_drv.c:1136-1150 enumerates until negative; platform.c:264-267 logs the terminating ENXIO; exact 32-entry DT verified before action')
        self.verify_irq_dt()
        raw = gate['raw_log']
        need(self.kernel_gate.observe_action(BOOT, raw, hashlib.sha256(raw.encode()).hexdigest(),
                                            'none')['allowed'], 'reviewed stop baseline rejected')

    def verify_irq_dt(self):
        base = Path('/sys/firmware/devicetree/base/axi')
        intc = base / 'interrupt-controller@80020000'
        raw = (base / 'zyxclmm_drm/interrupts-extended').read_bytes()
        parent = int.from_bytes((intc / 'phandle').read_bytes(), 'big')
        cells = int.from_bytes((intc / '#interrupt-cells').read_bytes(), 'big')
        triples = decode_irq_descriptors(raw, parent, cells)
        need(int.from_bytes((intc / 'xlnx,num-intr-inputs').read_bytes(), 'big') == 32,
             'controller input count differs')
        check_loaded(self.snapshot('irq_dt_topology_check'), PACKAGE)
        self.emit('EXACT_32_IRQ_DT_VERIFIED', raw_hex=raw.hex(), parent=parent, cells=cells,
                  triples=triples, driver_sha256=DRIVER_SHA, interpretation='index 32 is exclusive end, not missing index 0..31')

    def kernel_checkpoint(self, phase, mutation):
        p = subprocess.run(['dmesg', '--raw'], capture_output=True, timeout=3)
        need(p.returncode == 0 and not p.stderr, 'kernel log unavailable')
        raw = p.stdout.decode()
        action, verified = 'none', False
        if phase == 'after_mutation':
            if mutation == ['dfx-mgr-client', '-load', PACKAGE]:
                self.verify_irq_dt()
                action, verified = 'load_test', True
            elif mutation == ['dfx-mgr-client', '-load', DEFAULT]:
                action = 'load_default'
        result = self.kernel_gate.observe_action(
            Path('/proc/sys/kernel/random/boot_id').read_text().strip(), raw, None, action, verified)
        self.emit('KERNEL_LOG_GATE', phase=phase, mutation=mutation, raw_log=raw, **result)
        need(result['allowed'], 'unreviewed kernel diagnostic; stop')

    def run(self):
        need(os.geteuid() == 0 and os.uname().release == KERNEL, 'wrong root/kernel')
        self.kernel_checkpoint('continuation_preflight', None)
        for p, sha in BOOT_FILES.items():
            need(digest(p) == sha, 'original boot differs')
        need(digest(DRIVER) == DRIVER_SHA, 'driver differs')
        for name, sha in RESTORE.items():
            need(digest(Path('/lib/firmware/xilinx') / DEFAULT / name) == sha, 'restore differs')
        active = CENTRAL / 'active'
        lease = json.loads((active / 'lease.json').read_text())
        need(lease['owner'] == 'A' and lease['scope'] == 'A10_MINIMAL_IDLE_THEN_ONE'
             and lease['identity'] == MACHINE + ':' + BOOT and lease['compute_authorized'] is False,
             'prior lease scope differs')
        need(not Path('/proc', str(lease['pid'])).exists(), 'prior owner PID exists; reconcile first')
        need(not (OLD / 'compute.jsonl').exists() and not (OLD / 'approval.actual.json').exists(),
             'compute may already have occurred')
        self.deploy_lock = (CENTRAL / 'deployment.lock').open('a+')
        fcntl.flock(self.deploy_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.shared_lock = Path('/run/lock/patient-qwen-linear.lock').open('a+')
        fcntl.flock(self.shared_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        initial = self.snapshot('resume_idle_no_compute')
        check_loaded(initial, PACKAGE)
        need(initial['module_refcount'] == 0, 'unexpected module holder')
        self.remove(PACKAGE)
        check_removed(self.snapshot('idle_teardown_verified'), True)
        self.emit('IRQ_TEARDOWN_VERIFIED_THIS_BOOT_NO_COMPUTE')
        self.command(['dfx-mgr-client', '-load', PACKAGE], True)
        self.compute(lease, active)
        self.remove(PACKAGE)
        check_removed(self.snapshot('computed_test_removed'), True)
        self.command(['rmmod', 'zocl'], True)
        check_removed(self.snapshot('driver_removed'), False)
        self.command(['dfx-mgr-client', '-load', DEFAULT], True)
        final = self.snapshot('default_restored')
        need(final['overlays'] == {DEFAULT + '_image_1': 'applied'} and
             final['module_refcount'] is None and not final['device_holders'] and
             not final['zocl_bound'] and not final['render_nodes'] and
             final['fpga_state'] == 'operating' and final['vart_sha256'] == initial['vart_sha256'],
             'default restore differs')
        active_handle(self.command(['dfx-mgr-client', '-listPackage']), DEFAULT)
        for p, sha in BOOT_FILES.items():
            need(digest(p) == sha, 'original boot changed')
        self.kernel_checkpoint('final_readback', None)
        dest = CENTRAL / 'history/a10-minimal-20261021.json'
        need(not dest.exists(), 'existing history')
        (active / 'lease.json').rename(dest)
        active.rmdir()
        self.emit('MINIMAL_WINDOW_COMPLETE', compute_runs=1, n=32, default_restored=True,
                  regression='CANCELLED_BY_USER', status='PENDING_PC_EVIDENCE_AUDIT')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--execute-reviewed-continuation', action='store_true')
    ap.add_argument('--bundle-sha256', required=True)
    args = ap.parse_args()
    need(args.execute_reviewed_continuation, 'explicit continuation switch required')
    t = Continuation(args.bundle_sha256)
    try:
        t.run()
    except Exception as exc:
        t.emit('STOP_NO_AUTOMATIC_RECOVERY', error=str(exc), error_type=type(exc).__name__)
        raise
