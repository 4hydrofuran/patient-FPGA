"""Offline audit of this failed minimal window; never turns a waived test into PASS."""
import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(directory):
    hashes = json.loads((directory / 'download_hashes.json').read_text())
    required = {'idle-result.jsonl', 'continuation.jsonl'}
    if set(hashes) != required or any(sha(directory / n) != h for n, h in hashes.items()):
        raise ValueError('missing/changed raw board evidence')
    first, second = [[json.loads(l) for l in (directory / n).read_text().splitlines()]
                     for n in ('idle-result.jsonl', 'continuation.jsonl')]
    rows = first + second
    if first[-1]['event'] != 'STOP_NO_AUTOMATIC_RECOVERY' or second[-1]['event'] != 'STOP_NO_AUTOMATIC_RECOVERY':
        raise ValueError('unexpected outcome; a different audit is required')
    if any(r['event'].startswith('COMPUTE_') or r['event'] == 'MINIMAL_WINDOW_COMPLETE' for r in rows):
        raise ValueError('not the preserved pre-compute failure')
    gates = [r for r in second if r['event'] == 'KERNEL_LOG_GATE']
    last = gates[-1]
    if last['allowed'] or 'kernel BUG at mm/slub.c:553!' not in last['new_text']:
        raise ValueError('missing actual failure')
    commands = [dict(argv=r['argv'], exit_code=r['exit_code']) for r in rows if r['event'] == 'COMMAND_END']
    temps = [v for r in rows if r['event'] == 'READBACK' for v in r['temperatures_mC']]
    readbacks = [r for r in rows if r['event'] == 'READBACK']
    return dict(
        schema='A10_MINIMAL_FAILURE_AUDIT_V1', A10='NOT_PASSED_KERNEL_OOPS',
        evidence_hashes=hashes, boot_id=readbacks[0]['boot_id'], kernel='6.8.12-a10irq1',
        user_scope='MAXIMALLY_SIMPLIFIED_SINGLE_N32_AFTER_IDLE_TEARDOWN',
        numerical_regression='CANCELLED_BY_USER', compute_runs=0, compute_BO_allocations=0,
        test_bitstream_loads=1, normal_reboots_this_window=0, qspi_or_boot_writes=0,
        command_results=commands, first_runner_exit=1, continuation_runner_exit=1,
        min_observed_temperature_mC=min(temps), max_observed_temperature_mC=max(temps),
        first_observed_memory_kib=readbacks[0]['memory_kib'],
        last_pre_fault_memory_kib=readbacks[-1]['memory_kib'],
        final_default_restored=False, active_lease_retained=True,
        final_overlay_state=None, final_zocl_state=None,
        final_state_reason='Oops during remove; no further mutation or state-success claim',
        kernel_oops=last['new_text'], sync_us=None, bo_addresses=None, pss_kib=None, rss_kib=None,
        physical_budget_rule='CMA is part of MemTotal; never add CMA + PSS + BO',
        irq32='SOURCE_AND_REAL_32_DESCRIPTOR_DT_REVIEWED_ENUMERATION_END_ONLY',
        double_free='CANDIDATE_REJECTED; actual stack matches node->data second free',
        pc_fix='platform/build/a10-intc-data-owner-20261021-v1/repair.patch',
        fix_validation='PC_ASAN_LIFECYCLE_ONLY; not full kernel or board acceptance',
        P2='NOT_IMPLEMENTED: stress/maximum BO/bandwidth/long-run/fault injection',
        next='Do not continue on this Oops boot. Review recovery to original boot; build revised independent candidate on PC first.')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--directory', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    result = audit(args.directory)
    with args.output.open('x', encoding='utf-8') as f:
        json.dump(result, f, indent=2)
    print(json.dumps({k: result[k] for k in ('A10', 'compute_runs', 'max_observed_temperature_mC')}))
