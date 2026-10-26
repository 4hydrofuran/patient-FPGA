"""PC-only accounting for pinned real-board receipts. Never runs an accelerator.

Structural validation is not independent proof of hardware execution: trusted
launch/transport receipts must be reviewed alongside their raw logs. This tool
never grants an A10 PASS, even if all numeric comparison counts are present.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

LENGTHS = (1, 2, 3, 7, 15, 16, 31, 32, 63, 64, 65, 127, 128, 255, 256, 511, 512, 1023, 2048, 4096)
INIT = ('device_open', 'load_xclbin', 'kernel_open', 'bo_a', 'bo_b', 'bo_c', 'map_and_run_create')
BYTES = 16448


def need(ok, why):
    if not ok:
        raise ValueError(why)


def integer(v):
    return type(v) is int


def duration(v):
    return type(v) in (int, float) and math.isfinite(v) and v >= 0


def temperature(row):
    t = row.get('temperature_mC')
    need(isinstance(t, list) and 1 <= len(t) <= 16 and all(integer(v) and 0 < v < 60000 for v in t), 'missing/unsafe temperature')


def validate_rows(rows, receipt, expected):
    need(receipt.get('schema') == 'A10_REAL_BATCH_RECEIPT_V1', 'receipt schema')
    need(receipt.get('domain') == 'BOARD_REAL_XRT', 'not a real-board domain receipt')
    need(type(receipt.get('process_exit_code')) is int and receipt['process_exit_code'] == 0, 'failed/incomplete process')
    for key in ('machine_id_sha256', 'host_binary_sha256', 'xclbin_sha256'):
        need(receipt.get(key) == expected[key], 'receipt identity/version: ' + key)
    need(receipt.get('boot_id') in expected['boot_ids'], 'unreviewed boot')
    need(len(rows) >= 2 and rows[0].get('event') == 'BEGIN', 'missing BEGIN')
    begin = rows[0]
    need(begin.get('domain') == 'BOARD_REAL_XRT' and begin.get('whole_A10_pass') is False, 'incorrect domain/claim')
    need(begin.get('boot_id') == receipt['boot_id'], 'log/receipt boot mismatch')
    need(begin.get('xclbin_sha256') == expected['xclbin_sha256'], 'log xclbin mismatch')
    need(begin.get('approval_sha256') == receipt.get('approval_sha256') and
         isinstance(begin.get('approval_sha256'), str) and len(begin['approval_sha256']) == 64 and
         all(c in '0123456789abcdef' for c in begin['approval_sha256']), 'approval digest missing/mismatch')
    temperature(begin)
    start, count = begin.get('start_job'), begin.get('requested_jobs')
    need(integer(start) and integer(count) and 0 <= start < 1000 and 1 <= count <= 20 and start + count <= 1000, 'batch bounds')
    pos = 1
    for step in INIT:
        need(pos + 1 < len(rows), 'incomplete initialization')
        first, last = rows[pos:pos + 2]
        need(first.get('event') == 'INIT_STEP_BEGIN' and first.get('step') == step and
             last.get('event') == 'INIT_STEP_COMPLETE' and last.get('step') == step and duration(last.get('elapsed_ms')), 'initialization trace/order')
        pos += 2
    need(pos < len(rows), 'missing BO evidence')
    bo = rows[pos]
    need(bo.get('event') == 'BO_CREATED' and bo.get('groups') == [3, 3, 3] and
         type(bo.get('bytes_each')) is int and bo['bytes_each'] == BYTES and
         bo.get('is_maximum_budget_probe') is False, 'BO metadata differs')
    addresses = bo.get('addresses')
    need(isinstance(addresses, list) and len(addresses) == 3 and
         all(integer(a) and 0 <= a <= 2**31 - BYTES for a in addresses), 'BO outside pinned HP0 window')
    a = sorted(addresses)
    need(a[0] + BYTES <= a[1] and a[1] + BYTES <= a[2], 'overlapping BOs')
    pos += 1
    verified = []
    for job in range(start, start + count):
        need(pos + 1 < len(rows), 'incomplete job')
        prepared, result = rows[pos:pos + 2]
        n = LENGTHS[job % len(LENGTHS)]
        need(prepared.get('event') == 'PREPARED_NOT_SUBMITTED' and
             integer(prepared.get('job')) and prepared['job'] == job and integer(prepared.get('n')) and prepared['n'] == n, 'prepare job/order/length')
        need(result.get('event') == 'VERIFIED' and result.get('pass') is True and
             integer(result.get('job')) and result['job'] == job and integer(result.get('n')) and result['n'] == n, 'verification job/order/length')
        need(all(duration(result.get(k)) for k in ('sync_in_us', 'submit_poll_us', 'sync_out_us')), 'missing/nonfinite timing')
        temperature(result)
        verified.append({'job': job, 'n': n, 'source_line': pos + 2})  # JSONL is 1-based.
        pos += 2
    need(pos == len(rows) - 1, 'extra/duplicate/poisoned events or missing end')
    last = rows[pos]
    need(last.get('event') == 'BATCH_COMPLETE' and type(last.get('verified')) is int and
         last['verified'] == count and last.get('A10') == 'NOT_PASSED_BY_A_BATCH', 'incomplete terminal receipt')
    return verified


def referenced(base, item):
    rel = Path(item['path'])
    need(not rel.is_absolute() and '..' not in rel.parts, 'unsafe evidence path')
    path = (base / rel).resolve()
    need(path.is_relative_to(base.resolve()), 'evidence outside index directory')
    with path.open('rb') as f:
        data = f.read(1048577)
    need(len(data) <= 1048576, 'evidence size cap')
    need(hashlib.sha256(data).hexdigest() == item['sha256'], 'evidence digest mismatch')
    return data


def audit(index_path):
    index = json.loads(index_path.read_text(encoding='utf-8'))
    need(index.get('schema') == 'A10_REAL_BATCH_INDEX_V1', 'index schema')
    need(isinstance(index.get('batches'), list) and len(index['batches']) <= 1000, 'batch list/cap')
    accepted, rejected, seen = [], [], set()
    for entry in index['batches']:
        try:
            receipt = json.loads(referenced(index_path.parent, entry['receipt']))
            raw = referenced(index_path.parent, entry['log'])
            need(receipt.get('log_sha256') == entry['log']['sha256'], 'receipt/log digest mismatch')
            rows = [json.loads(line) for line in raw.decode('utf-8').splitlines()]
            jobs = validate_rows(rows, receipt, index['expected'])
            need(not any(j['job'] in seen for j in jobs), 'duplicate job across receipts')
            seen.update(j['job'] for j in jobs)
            accepted.append({'log': entry['log'], 'receipt': entry['receipt'], 'jobs': jobs})
        except (ValueError, KeyError, TypeError, OSError) as error:
            rejected.append({'input': entry, 'reason': str(error)})
    counts = Counter(j['n'] for batch in accepted for j in batch['jobs'])
    all_counts = not rejected and seen == set(range(1000)) and all(counts[n] == 50 for n in LENGTHS)
    return {'schema': 'A10_BATCH_ACCOUNTING_V1', 'domain': 'PC_EVIDENCE_AUDIT_NOT_BOARD_EXECUTION',
            'index_sha256': hashlib.sha256(index_path.read_bytes()).hexdigest(),
            'status': 'NO_REAL_BATCH_EVIDENCE' if not index['batches'] else 'STRUCTURAL_AUDIT_ONLY',
            'accepted_unique_jobs': len(seen), 'per_length': {str(n): counts[n] for n in LENGTHS},
            'missing_job_ids': sorted(set(range(1000)) - seen), 'accepted': accepted, 'rejected': rejected,
            'comparison_count_criteria_met': all_counts,
            'measured_compute_time_s': None, 'BO_budget_bytes': None,
            'A10': 'NOT_PROVEN_REQUIRES_IDENTITY_PLATFORM_RECOVERY_AND_BO_AUDIT',
            'warning': 'Receipts and host provenance require independent review; structural checks cannot authenticate fabricated hardware claims.'}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('index', type=Path)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    result = audit(a.index)
    with a.out.open('x', encoding='utf-8') as f:
        json.dump(result, f, indent=2)
        f.write('\n')
    print(json.dumps({k: result[k] for k in ('status', 'accepted_unique_jobs', 'comparison_count_criteria_met', 'A10')}))
    raise SystemExit(0 if result['comparison_count_criteria_met'] else 2)
