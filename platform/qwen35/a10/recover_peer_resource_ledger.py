"""Offline resource accounting from the pinned historical N32 evidence only.

Does not import/execute the captured XRT program, connect to hardware or rerun
computation. Original bytes and line numbers are preserved as provenance.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re


MANIFEST_SHA = '1474816a0844b78528b38484b94f452da4fcb8f196938a2f01acc3f36b1a4a58'
NATIVE_SHA = '2a986f7fd9a879de16d7d0806b3c8f47585b47cc0b5f930f60346a08c40a24cd'
EMIT_SHA = 'f5562628e9ab3b6be880d4fab5ce8ca06aaff994a2bcd1050f18408700ff6a45'
BOOT = '0e2f466a-87a3-4f5e-9cf4-50d6b7756832'
LOG = 'evidence/02_repaired_trial/lifecycle_stopped.jsonl'
ACTUAL = 'evidence/02_repaired_trial/actual_output.json'
AUDIT = 'evidence/summary/board_result_audit.json'
CONSUMED = 'evidence/02_repaired_trial/consumed_bundle_manifest.json'
PHASES = ('before_device_open', 'explicit_bos_live', 'after_normal_release')


def need(value, reason):
    if not value:
        raise ValueError(reason)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def decode(data):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'duplicate JSON key: ' + key)
            result[key] = value
        return result
    def reject(value):
        raise ValueError('nonfinite JSON number: ' + value)
    return json.loads(data, object_pairs_hook=pairs, parse_constant=reject)


def counters(text, names):
    """Absent counters stay null; each selected present counter must be KiB."""
    result = dict.fromkeys(names)
    seen = set()
    for line in text.splitlines():
        key = line.split(':', 1)[0]
        if key not in result:
            continue
        need(key not in seen, 'duplicate counter: ' + key)
        seen.add(key)
        match = re.fullmatch(re.escape(key) + r':\s*(\d+)\s+kB', line)
        need(match is not None, 'invalid counter units/value: ' + key)
        result[key] = int(match[1])
    return result


def one(rows, event, phase=None):
    matches = [(number, row) for number, row in rows if row.get('event') == event
               and (phase is None or row.get('phase') == phase)]
    need(len(matches) == 1, 'missing/ambiguous event: ' + event + ':' + str(phase))
    return matches[0]


def extract(log_bytes, actual, audit):
    rows = [(number, decode(line)) for number, line in enumerate(log_bytes.splitlines(), 1) if line.strip()]
    need(rows and all(isinstance(row, dict) for _, row in rows), 'invalid log rows')
    need({row['boot_id'] for _, row in rows if 'boot_id' in row} == {BOOT}, 'mixed/missing boot identity')
    need(audit['boot_id'] == BOOT and audit['overall_A10'] == 'NOT_PASSED'
         and audit['status'] == 'BOARD_NUMERIC_AND_IDLE_PASS_POSTCOMPUTE_TEARDOWN_FAILED',
         'historical teardown failure must be retained')
    bo_line, bo = one(rows, 'BO_CREATED')
    output_line, output = one(rows, 'ACTUAL_OUTPUT')
    one(rows, 'SINGLE_SUBMISSION_BEGIN')
    need(actual['n'] == 32 and actual['real_submissions'] == 1 and actual['pass_numeric'] is True,
         'not the audited single N32')
    need(all(output.get(key) == value for key, value in actual.items()), 'output record differs')
    need(bo['groups'] == [3, 3, 3] and bo['bytes_each'] == 16448
         and bo['explicit_bo_total_bytes'] == 49344 and bo['maximum_budget_probe'] is False,
         'small BO contract differs')
    addresses = bo['addresses']
    need(len(addresses) == 3 and all(type(a) is int and 0 <= a <= 0x80000000 - 16448 for a in addresses),
         'invalid historical BO addresses')
    ordered = sorted(addresses)
    need(all(b >= a + 16448 for a, b in zip(ordered, ordered[1:])), 'overlapping historical BOs')
    for key in ('sync_in_us', 'sync_out_us'):
        need(type(actual[key]) in (int, float) and math.isfinite(actual[key]) and actual[key] >= 0,
             'invalid recorded elapsed value')
    process, physical = [], []
    for phase in PHASES:
        number, row = one(rows, 'MEMORY_OBSERVATION', phase)
        need(row['includes_hidden_xrt_allocations'] is False and row['explicit_bo_live_max_bytes'] == 49344,
             'declared envelope changed')
        process.append(dict(source_line=number, phase=phase, monotonic_s=row['monotonic_s'],
                            status_kib=counters(row['proc_status'], ('VmRSS', 'VmHWM', 'RssAnon', 'RssFile', 'RssShmem')),
                            smaps_kib=counters(row['smaps_rollup'], ('Rss', 'Pss', 'Pss_Anon', 'Pss_File', 'Pss_Shmem')),
                            raw_declared_bo_envelope_bytes=row['explicit_bo_live_max_bytes'],
                            observed_current_bo_bytes=None,
                            release_proven=False if phase == 'after_normal_release' else None))
        physical.append(dict(source_line=number, phase=phase,
                             meminfo_kib=counters(row['meminfo'], ('MemTotal', 'MemAvailable', 'CmaTotal', 'CmaFree'))))
    need(process[0]['source_line'] < bo_line < process[1]['source_line'] < output_line < process[2]['source_line'],
         'historical event ordering differs')
    need(all(a['monotonic_s'] <= b['monotonic_s'] for a, b in zip(process, process[1:])), 'time order differs')
    return dict(schema='A10_HISTORICAL_RESOURCE_LEDGER_V1', boot_id=BOOT,
                domain='PC_DERIVED_FROM_PRIOR_REAL_BOARD_RECORDS', new_board_access=False, new_compute_submissions=0,
                historical_compute_submissions=1, historical_teardown='FAILED', A10='NOT_PASSED',
                small_bo=dict(source_line=bo_line, groups=bo['groups'], addresses=addresses,
                              addresses_hex=[hex(a) for a in addresses], bytes_each=16448,
                              observed_intervals_half_open=[[a, a + 16448] for a in addresses],
                              explicit_requested_live_peak_bytes=49344,
                              explicit_requested_live_peak_basis='three successful allocations before any explicit free; not physical allocator peak',
                              physical_allocation_peak_bytes=None, hidden_xrt_allocations_bytes=None,
                              maximum_allocatable_bytes=None, general_low_or_high_address_reachability=None),
                timing=dict(source_line=output_line, recorded_sync_in_us=actual['sync_in_us'],
                            recorded_sync_out_us=actual['sync_out_us'], samples=1,
                            sync_in_scope='three host-to-device sync calls including per-call emit/write/flush/fsync and Python overhead',
                            sync_out_scope='POSITIVE_COMPLETION emit/write/flush/fsync followed by one output sync and Python overhead',
                            pure_sync_in_us=None, pure_sync_out_us=None, bandwidth_bytes_per_second=None),
                process_account=process, physical_account=physical,
                accounting_rule='PSS/RSS, CMA and BO are overlapping views; no sum or ownership attribution from CMA deltas',
                limitations=['Recorded explicit_bo_live_max_bytes is the same declared 49344-byte envelope at all three phases, not instantaneous usage.',
                             'VmHWM includes earlier activity of the same process; three snapshots do not establish a window PSS peak or a model budget.',
                             'The label after_normal_release records handle destruction only: residual mapping and later kernel error disproved complete release.',
                             'Addresses qualify only the three observed BO intervals, never a contiguous/general safe range.',
                             'No stress, numerical replay, fresh hardware trial or performance optimization was performed.'])


def recover(package, native_source):
    package, native_source = Path(package), Path(native_source)
    manifest_bytes = (package / 'MANIFEST.json').read_bytes()
    need(sha(manifest_bytes) == MANIFEST_SHA, 'unreviewed handoff manifest')
    manifest = decode(manifest_bytes)
    data, provenance = {}, {}
    for name in (LOG, ACTUAL, AUDIT, CONSUMED):
        raw = (package / name).read_bytes()
        entry = manifest['files'][name]
        need(len(raw) == entry['bytes'] and sha(raw) == entry['sha256'], 'source hash differs: ' + name)
        data[name] = raw
        provenance[name] = dict(bytes=len(raw), sha256=sha(raw))
    native = native_source.read_bytes()
    native_entry = decode(data[CONSUMED])['files']['single_xrt_call.py']
    need(sha(native) == NATIVE_SHA == native_entry['sha256'] and len(native) == native_entry['bytes'],
         'executed timing source changed')
    emit_path = native_source.parent / 'run_refcount_step5.py'
    emit_source = emit_path.read_bytes()
    emit_entry = decode(data[CONSUMED])['files']['run_refcount_step5.py']
    need(sha(emit_source) == EMIT_SHA == emit_entry['sha256'] and len(emit_source) == emit_entry['bytes'],
         'executed logger source changed')
    result = extract(data[LOG], decode(data[ACTUAL]), decode(data[AUDIT]))
    result['provenance'] = dict(package=str(package.resolve()), manifest_sha256=MANIFEST_SHA,
                                lifecycle_path=LOG, sources=provenance,
                                timing_source=dict(path=str(native_source.resolve()), sha256=NATIVE_SHA,
                                                   reviewed_lines={'sync_in': [103, 106], 'sync_out': [129, 133]}),
                                emit_source=dict(path=str(emit_path.resolve()), sha256=EMIT_SHA,
                                                 reviewed_lines=[69, 76]))
    return result


def write_new(output, result):
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write('\n')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--package', type=Path, required=True)
    ap.add_argument('--native-source', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args(argv)
    result = recover(args.package, args.native_source)
    write_new(args.output, result)
    print(json.dumps(dict(status='HISTORICAL_SMALL_BO_AND_MEMORY_RECOVERED_NOT_A10_PASS',
                          output=str(args.output), sha256=sha(args.output.read_bytes()), board_access=False)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
