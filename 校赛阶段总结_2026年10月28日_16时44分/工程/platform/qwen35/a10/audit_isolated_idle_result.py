"""PC-only audit of the frozen v4 BOARD capture; never grants another trial."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import zlib

from isolated_idle_policy import KERNEL, MACHINE, need
from minimal_gate import MinimalGate

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / 'evidence/board_platform/A10_20261023_isolated_idle_v4'
BOOT = 'c5baeabe-273d-447e-b323-ff07dd7af201'
WINDOW = 'a10-isolated-idle-20261023-v4'
MANIFEST_SHA = '726723f471aa6bb3f6902b5a65a543402be0cf94202c25e169f89b9703867b06'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def verify_packet(directory, packet):
    for name, entry in {**packet['files'], 'kernel.raw.txt': packet['kernel_log']}.items():
        need(Path(name).name == name, 'unsafe evidence name')
        path = directory / name
        if entry is None:
            need(not path.exists(), 'absent file unexpectedly materialized')
            continue
        raw = zlib.decompress(base64.b64decode(entry['zlib_base64'], validate=True))
        need(len(raw) == entry['bytes'] and sha(raw) == entry['sha256'] and path.read_bytes() == raw,
             'raw capture/local evidence mismatch: ' + name)


def assess(rows, worker_rows, receipt, packet, lease, baseline, final_raw):
    need(rows and all(r['boot_id'] == BOOT and r['window_id'] == WINDOW for r in rows), 'identity differs')
    need(all(a['monotonic_ns'] < b['monotonic_ns'] for a, b in zip(rows, rows[1:])), 'event order differs')
    need(not any('QUARANTINED' in r['event'] for r in rows), 'quarantine cannot pass')
    need(receipt['status'] == 'PASS_IDLE_XRT_PROCESS_LIFECYCLE_ONLY' and receipt['kernel'] == KERNEL,
         'wrong completion receipt')
    need(receipt['A10'] == 'NOT_PASSED_POSTCOMPUTE_VERIFICATION_OPEN', 'idle cannot certify A10')
    result = receipt['worker_result']
    need(result['normal_handles_closed'] is True and result['real_submissions'] == 0 and
         result['explicit_bo_allocations'] == 0 and result['groups'] == [3, 3, 3], 'not idle-only evidence')
    need(result['manager_pid'] == packet['manager_pid'] and result['boot_id'] == BOOT and
         result['window_id'] == WINDOW, 'worker identity differs')
    need(packet['boot_id'] == BOOT and packet['manager_proc'] is None and packet['active_lease'] is None,
         'live manager/lease or wrong boot')
    need(not lease['active_exists'] and not lease['lease_exists'] and lease['boot_id'] == BOOT and
         len(lease['locks']) == 2 and all(not r['matching_rows'] for r in lease['locks']), 'maintenance remains')
    need(packet['module_present'] is False and packet['render_nodes'] == [] and
         packet['overlays'] == {'k26-starter-kits_image_1': 'applied'} and
         packet['gdm_state'] == 'active' and packet['gdm_read_exit'] == 0, 'default restoration differs')
    calls = [r['call'] for r in worker_rows if r['event'] == 'XRT_CALL_BEGIN']
    need(calls == ['xrtDeviceOpen', 'xrtDeviceLoadXclbinFile', 'xrtDeviceGetXclbinUUID',
                   'xrtPLKernelOpenExclusive', *(['xrtKernelArgGroupId'] * 3),
                   'xrtKernelClose', 'xrtDeviceClose'], 'native calls outside idle scope')
    need([r['call'] for r in worker_rows if r['event'] == 'XRT_CALL_END'] == calls,
         'native completion missing')
    need(all(r['worker_pid'] == result['worker_pid'] and r['window_id'] == WINDOW for r in worker_rows),
         'native worker identity differs')
    reaped = [r for r in rows if r['event'] == 'WORKER_REAPED']
    release = [r for r in rows if r['event'] == 'RELEASE_PRECHECK_PASSED_NOT_UNLOADED']
    need(len(reaped) == len(release) == 1 and reaped[0]['exit_code'] == 0 and
         reaped[0]['worker_pid'] == release[0]['worker_pid'] == result['worker_pid'], 'normal waitpid required')
    scan = release[0]['scan']
    need(type(release[0]['module_refcount']) is int and release[0]['module_refcount'] == 0 and
         scan['scan_complete'] is True and not scan['scan_issues'] and
         not scan['device_holders'] and not scan['device_mappings'], 'release incomplete')
    need(reaped[0]['monotonic_ns'] <= scan['scan_started_ns'] < scan['scan_finished_ns'] <=
         release[0]['monotonic_ns'] and release[0]['monotonic_ns'] - scan['scan_finished_ns'] <= 2_000_000_000,
         'release scan stale or before process exit')
    commands = [r for r in rows if r['event'] == 'COMMAND_END']
    expected = [['dfx-mgr-client', '-listPackage'], ['dfx-mgr-client', '-remove', '0'],
                ['insmod', '/var/lib/kv260-a10/' + WINDOW + '/zocl.refcount.ko'],
                ['dfx-mgr-client', '-load', WINDOW], ['dfx-mgr-client', '-listPackage'],
                ['dfx-mgr-client', '-remove', '0'], ['rmmod', 'zocl'],
                ['dfx-mgr-client', '-load', 'k26-starter-kits']]
    need([r['argv'] for r in commands] == expected and all(r['exit_code'] == 0 for r in commands),
         'hardware command count/order/completion differs')
    need(commands[5]['monotonic_ns'] > release[0]['monotonic_ns'], 'unload before release gate')
    services = [r for r in rows if r['event'] == 'GDM_ACTION']
    need([r['action'] for r in services] == ['stop', 'start'] and all(r['exit_code'] == 0 for r in services),
         'graphical restoration incomplete')
    need(rows[-1]['event'] == 'IDLE_LIFECYCLE_COMPLETE_DEFAULT_PL_RESTORED', 'lifecycle incomplete')
    gate = MinimalGate()
    need(gate.observe_action(BOOT, baseline.decode(), sha(baseline), 'none')['allowed'], 'baseline rejected')
    irq = [r for r in rows if r['event'] == 'EXACT_IRQ_DT_VERIFIED']
    need(len(irq) == 1 and irq[0]['count'] == 32, 'IRQ evidence missing')
    advisories = []
    for row in rows:
        if row['event'] != 'KERNEL_LOG_GATE':
            continue
        action = row['action']
        checked = gate.observe_action(BOOT, row['raw_log'], None, action,
                                      action == 'load_test' and irq[0]['monotonic_ns'] < row['monotonic_ns'])
        need(checked['allowed'] and row['allowed'] is True, 'kernel gate rejected')
        advisories.extend(checked.get('reviewed_advisories', []))
    late = gate.observe_action(BOOT, final_raw.decode(), None, 'none')
    need(late['allowed'], 'independent delayed kernel readback rejected')
    health = [r for r in rows if r['event'] == 'READBACK']
    temps = [t for r in health for t in r['temperatures_mC']]
    return dict(status='PASS_BOARD_IDLE_WITH_KNOWN_LIMITATIONS', A10='NOT_PASSED_POSTCOMPUTE_RELEASE_OPEN',
                boot_id=BOOT, kernel=KERNEL, machine_sha256=MACHINE, bundle_manifest_sha256=MANIFEST_SHA,
                new_compute_submissions=0, explicit_compute_bo_allocations=0,
                controller_elapsed_s=(rows[-1]['monotonic_ns']-rows[0]['monotonic_ns'])/1e9,
                native_worker_observed_s=(worker_rows[-1]['monotonic_ns']-worker_rows[0]['monotonic_ns'])/1e9,
                sampled_temperature_range_mC=[min(temps), max(temps)],
                minimum_sampled_mem_available_KiB=min(r['memory_kib']['MemAvailable'] for r in health),
                minimum_sampled_cma_free_KiB=min(r['memory_kib']['CmaFree'] for r in health),
                release_scan_processes=len(scan['inspected_processes']), module_refcount_before_unload=0,
                command_exit_codes=[dict(argv=r['argv'], exit_code=r['exit_code']) for r in commands],
                reviewed_advisories=advisories, delayed_kernel_readback_allowed=True,
                delayed_readback_after_controller_s=(packet['monotonic_ns']-rows[-1]['monotonic_ns'])/1e9,
                final_readback=dict(temperature_mC=packet['temperatures_mC'],
                                   default_pl='applied', gdm='active', zocl_present=False,
                                   manager_present=False, active_lease_present=False),
                kernel_raw_sha256=sha(final_raw), normal_kernel_restore='NOT_PERFORMED_STILL_IRQ2',
                physical_bo_peak_bytes=None, performance_conclusion=None,
                measurement_scope='Single idle lifecycle; sampled health, not stress/performance or postcompute proof')


def load_inputs():
    result = EVIDENCE / 'result_readback_01'
    packet = read(result / 'stdout.json')
    verify_packet(result, packet)
    need(sha((result / 'manifest.json').read_bytes()) == MANIFEST_SHA, 'bundle pin differs')
    preflight = read(EVIDENCE / 'final_preflight_01.json')
    need(preflight['closed'] and all(r['completion_marker'] and r['exit_code'] == 0 for r in preflight['records']),
         'final serial read incomplete')
    entry = next(r for r in preflight['records'] if r['name'] == 'lease_and_lock_metadata')
    lease = [json.loads(r) for r in entry['raw'].splitlines() if r.startswith('{"active_exists":')]
    need(len(lease) == 1, 'unique lock observation required')
    return ([json.loads(r) for r in (result/'lifecycle.jsonl').read_text().splitlines()],
            [json.loads(r) for r in (result/'worker.stdout.jsonl').read_text().splitlines()],
            read(result/'idle-receipt.json'), packet, lease[0],
            (EVIDENCE/'candidate_review_01/baseline.raw.txt').read_bytes(), (result/'kernel.raw.txt').read_bytes())


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    report = assess(*load_inputs())
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2)
    print(json.dumps(report))


if __name__ == '__main__':
    main()
