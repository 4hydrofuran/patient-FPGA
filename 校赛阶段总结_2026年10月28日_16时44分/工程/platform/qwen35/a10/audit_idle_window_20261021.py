"""PC-only derivation from immutable captured A10 evidence. Never contacts board."""
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]
E = ROOT / 'evidence/board_platform/A10_20261018_intake'
BOOT = '751e617d-c003-4b99-be03-bb5c78235d24'


def load(name):
    return json.loads((E / name).read_text(encoding='utf-8-sig'))


def rows(name):
    return [json.loads(line) for line in (E / name).read_bytes().splitlines()]


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def mutation_summary(events):
    starts = [r for r in events if r['event'] == 'COMMAND_BEGIN' and r['state_changing']]
    ends = [r for r in events if r['event'] == 'COMMAND_END']
    result = []
    for begin in starts:
        matches = [r for r in ends if r['argv'] == begin['argv']
                   and r['monotonic_s'] >= begin['monotonic_s']]
        require(len(matches) == 1, 'unknown/repeated mutation completion')
        end = matches[0]
        result.append(dict(argv=begin['argv'], exit_code=end['exit_code'],
                           elapsed_s=end['monotonic_s'] - begin['monotonic_s']))
    return result


def derive():
    v2 = rows('idle_window_trial_v2_raw_20261021_01.jsonl')
    v3 = rows('idle_window_trial_v3_raw_20261021_01.jsonl')
    failed = rows('idle-window-closeout-v1/a10-candidate-idle-cleanup-20261021.jsonl')
    cleanup = rows('idle-window-closeout-v1/a10-candidate-idle-cleanup-20261021-v2.jsonl')
    readback = load('idle_window_final_readback_20261021_01.json')
    require(readback['exit_code'] == 0 and
            'READONLY_FINAL_DEFAULT_NO_ZOCL_NO_ACTIVE_LEASE' in readback['stdout'],
            'final independent readback failed')
    text = readback['stdout']
    pairs = [
        ('idle_window_trial_v2_raw_20261021_01.jsonl',
         '/home/ubuntu/a10-idle-candidate-20261021-v2/idle-result.jsonl'),
        ('idle_window_trial_v3_raw_20261021_01.jsonl',
         '/home/ubuntu/a10-candidate-idle-20261021-v3/idle-result.jsonl'),
        ('idle-window-closeout-v1/a10-candidate-idle-cleanup-20261021.jsonl',
         '/home/ubuntu/a10-candidate-idle-cleanup-20261021.jsonl'),
        ('idle-window-closeout-v1/a10-candidate-idle-cleanup-20261021-v2.jsonl',
         '/home/ubuntu/a10-candidate-idle-cleanup-20261021-v2.jsonl')]
    hashes = {}
    for local, remote in pairs:
        digest = hashlib.sha256((E / local).read_bytes()).hexdigest()
        require(f'{digest}  {remote}\n' in text, 'download/raw hash mismatch: ' + local)
        hashes[local] = digest
    require(not mutation_summary(v2), 'first preflight changed hardware')
    old = v2[0]['raw_baseline']
    normalized = next(r['raw_log'] for r in v2 if r['event'] == 'KERNEL_LOG_GATE')
    require(old.count('\r') == 41 and old.replace('\r\n', '\n').replace('\r', '\n') == normalized,
            'not the recorded universal-newline defect')
    require(len(failed) == 1 and failed[0]['event'] == 'CLEANUP_STOP_NO_RETRY',
            'first cleanup unexpectedly mutated state')
    mutations = mutation_summary(v3) + mutation_summary(cleanup)
    expected = [
        ['dfx-mgr-client', '-remove', '0'],
        ['insmod', '/usr/lib/modules/6.8.12-a10irq1/extra/zocl.ko'],
        ['rmmod', 'zocl'],
        ['dfx-mgr-client', '-load', 'k26-starter-kits']]
    require([r['argv'] for r in mutations] == expected and
            all(r['exit_code'] == 0 for r in mutations), 'mutation inventory/exit differs')
    final = next(r for r in cleanup if r['event'] == 'READBACK'
                 and r['phase'] == 'default_restored')
    require(final['boot_id'] == BOOT
            and final['overlays'] == {'k26-starter-kits_image_1': 'applied'}
            and final['module_refcount'] is None
            and not final['zocl_bound'] and not final['render_nodes']
            and not final['device_holders'] and not final['accelerator_card_nodes'],
            'not independently restored')
    require(cleanup[-1]['event'] == 'DEFAULT_RESTORED_NO_COMPUTE'
            and cleanup[-1]['active_lease_archived']
            and cleanup[-1]['diagnostic_gate_blocked'], 'not expected closeout')
    new_diagnostics = [
        dict(source=source, phase=r['phase'], new_text=r['new_text'],
             diagnostics=r['diagnostics'])
        for source, capture in [('trial_v3', v3), ('cleanup_v2', cleanup)]
        for r in capture if r['event'] == 'KERNEL_LOG_GATE'
        and r.get('reason') == 'NEW_KERNEL_DIAGNOSTIC']
    temps = [int(x) for x in re.findall(r'temp\d+_input (\d+)', text)]
    memory = {k: int(v) for k, v in re.findall(
        r'^(MemTotal|MemAvailable|CmaTotal|CmaFree):\s+(\d+) kB$', text, re.M)}
    require(len(temps) == 3 and len(memory) == 4, 'incomplete final resource readback')
    original = {
        '/boot/firmware/image.fit': 'b007246e409140c73485a057a0e7ccc1fac7116c14699837e4066e74be7532a9',
        '/boot/firmware/boot.scr.uimg': '690fe1225a017a63796df1517b8b203fe9b7500597b2c5a61a0f524875ea2efc'}
    require(all(f'{sha}  {name}\n' in text for name, sha in original.items()),
            'original boot material differs')
    return dict(
        status='DEFAULT_RESTORED_DIAGNOSTICS_OPEN_A10_NOT_PASSED', boot_id=BOOT,
        kernel='6.8.12-a10irq1', verification_domain='BOARD_IDLE_CONTROL_ONLY',
        numerical_regression='CANCELLED_BY_USER', mutations=mutations,
        test_bitstream_loads=0, compute_runs=0, compute_BO_allocations=0,
        no_pressure_test=True, baseline_CR_translation_reproduced=41,
        exact_new_diagnostics=new_diagnostics, original_boot_sha256=original,
        original_boot_files_unchanged=True, default_overlay_restored=True,
        zocl_loaded=False, active_lease=False, final_temperatures_mC=temps,
        final_memory_kib=memory, raw_download_sha256=hashes,
        test_irq_teardown='NOT_TESTED_TEST_OVERLAY_NEVER_LOADED',
        new_baseline_diagnostics_not_waived_for_compute=True,
        timing_note='Per-command monotonic wall time; not compute latency or CPU-load duration.',
        ssh_connections_closed=True, uart_released=True,
        p2='NOT_IMPLEMENTED_NOT_REQUIRED_FOR_THIS_INCREMENT')


def write_new(name, content):
    with (E / name).open('x', encoding='utf-8', newline='\n') as output:
        output.write(json.dumps(content, indent=2, ensure_ascii=False) + '\n')


if __name__ == '__main__':
    summary = derive()
    write_new('idle_window_audit_20261021.json', summary)
    write_new('board_profile.idle_20261021.json', dict(
        schema='A10_INCREMENTAL_BOARD_PROFILE_V1',
        previous_identity_evidence='board_profile.safe_v2.json',
        status=summary['status'], boot_id=BOOT, kernel=summary['kernel'],
        temperature_mC=summary['final_temperatures_mC'], memory_kib=summary['final_memory_kib'],
        default_overlay='k26-starter-kits_image_1', zocl_loaded=False,
        active_lease=False, fpga_state='operating', test_bitstream_loaded=False,
        compute_runs=0, device_paths={'compute_render': None},
        xrt_compatibility='NOT_ACCEPTED_BY_THIS_IDLE_ATTEMPT',
        current_ip='192.168.2.2/24', ip_persistence='NetworkManager save-no; lost on reboot',
        limitations=['X509 trust', 'boot firmware/pinctrl', 'overlay property lifetime',
                     'test IRQ teardown not exercised', 'PL I/O and BO not measured'],
        authoritative_summary='idle_window_audit_20261021.json'))
    write_new('memory_accounts.idle_20261021.json', dict(
        domain='BOARD_IDLE_ONLY', boot_id=BOOT,
        process_observation=dict(PSS_KiB=None, RSS_KiB=None, compute_BO_bytes=None,
                                 reason='No compute/BO session; not sampled as a process memory experiment'),
        physical_observation=summary['final_memory_kib'],
        accounting_rule='CMA is part of MemTotal; do not add CMA + PSS + BO as disjoint ownership.',
        configuration_buffer_peak_bytes=None, BO_address_range=None, BO_sync_s=None,
        envelope_3200MiB='PLANNING_ONLY_NOT_VALIDATED',
        no_peak_allocation_probe=True))
    print(json.dumps(summary, indent=2, ensure_ascii=False))
