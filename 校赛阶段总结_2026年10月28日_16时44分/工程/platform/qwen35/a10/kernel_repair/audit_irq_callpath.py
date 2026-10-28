"""PC-only source evidence: interrupt-enabled xclbin reaches sleepable IRQ APIs.

This is a static risk finding, not a board failure reproduction or a fix.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path('/mnt/c/Patientqwen')
XRT = Path('/home/member-a/a10-driver-audit-20261018/source/usr/src/xrt-2.18.0/driver')
KERNEL = Path('/home/member-a/a10-kernel-full-20261019-v1/source')


def snapshot(path, needles):
    raw = path.read_bytes()
    lines = raw.decode().splitlines()
    matches = []
    for needle in needles:
        found = [i + 1 for i, line in enumerate(lines) if needle in line]
        if not found:
            raise ValueError(f'Missing reviewed evidence: {path}: {needle}')
        matches.append({'needle': needle, 'lines': found})
    return {'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest(), 'matches': matches}


def collect():
    layout_path = ROOT / 'platform/a1/evidence/offline-link-kv260-vadd-20260928-env/sections/ip_layout.json'
    layout = json.loads(layout_path.read_text())['ip_layout']
    assert layout['m_count'] == '1'
    ip = layout['m_ip_data'][0]
    assert ip['m_int_enable'] == '1' and ip['m_name'] == 'krnl_vadd:krnl_vadd_1'
    files = [
        snapshot(layout_path, ['"m_int_enable": "1"', '"m_ip_control": "AP_CTRL_CHAIN"']),
        snapshot(XRT / 'common/kds_core.c', ['info.intr_enable = ip->properties & IP_INT_ENABLE_MASK;']),
        snapshot(XRT / 'zocl/common/cu.c', [
            'if (info->intr_enable && info->protocol != CTRL_NONE)',
            'zocl_ert_intc_add(intc, info->intr_id, cu_isr, zcu)',
            'zocl_ert_intc_remove(intc, info->intr_id)']),
        snapshot(XRT / 'zocl/zert/zocl_xgq_intc.c', [
            'spin_lock_irqsave(&zintc->zei_lock, irqflags);',
            'request_irq(h->zeih_irq, zintc_isr', 'free_irq(h->zeih_irq, h);',
            'disable_irq(h->zeih_irq);', 'spin_unlock_irqrestore(&zintc->zei_lock, irqflags);']),
        snapshot(KERNEL / 'kernel/irq/manage.c', [
            'static struct irqaction *__free_irq', 'mutex_lock(&desc->request_mutex);',
            'void disable_irq(unsigned int irq)', 'might_sleep();',
            'action = kzalloc(sizeof(struct irqaction), GFP_KERNEL);']),
    ]
    return {
        'status': 'OPEN_STATIC_DRIVER_IRQ_CONTEXT_RISK_NOT_BOARD_REPRODUCED',
        'sources': files,
        'reviewed_inference': 'The enabled-CU interrupt path calls request_irq/free_irq/disable_irq inside zei_lock irqsave sections. Matching kernel uses GFP_KERNEL/mutex/wait-capable operations. Actual activation/concurrency and symptoms were not exercised.',
        'polling_is_not_proof_of_bypass': 'CU probe uses xclbin intr_enable; later scheduler polling selection alone does not prove IRQ registration is skipped.',
        'kernel_candidate_fixes_this': False,
        'required_before_compute': 'Resolve and PC-test the concrete driver lifecycle or prove a safe actual non-triggering path without falsifying metadata; do not run a board repro.',
        'board_commands': [], 'source_modified': False,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = collect()
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps({'status': result['status'], 'files': len(result['sources']), 'board_commands': []}))
