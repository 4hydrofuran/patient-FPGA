"""PC-only final requirement/data ledger. Never opens UART/SSH or executes code."""
import argparse
import json
from pathlib import Path
import re
import shutil

import audit_single_result as audit
from single_compute_policy import ASSETS, SOURCES, BO_BYTES, digest, need, verify_bundle

DOCS = ('PROJECT_STATUS.json', 'status/A.md', 'DESIGN_GAP.md', 'DECISIONS.md', 'TEST_MATRIX.md',
        'AI_ASSISTANCE.md', 'A10_REMAINING_MINIMUM_20261021.md', 'A10_ACCEPTANCE_SAFE_20261019.md')


def fields(raw, keys):
    result = {}
    for key in keys:
        found = re.findall(r'^'+re.escape(key)+r':\s+(\d+)(?: kB)?\s*$', raw, re.M)
        need(len(found) <= 1, 'duplicate memory field')
        result[key] = int(found[0]) if found else None
    return result


def resource_ledger(worker_path, result, release):
    samples = []
    for line, text in enumerate(worker_path.read_text().splitlines(), 1):
        row = json.loads(text)
        if row['event'] != 'MEMORY_OBSERVATION':
            continue
        samples.append(dict(source_line=line, monotonic_ns=row['monotonic_ns'], phase=row['phase'],
            process_KiB=fields(row['smaps_rollup'], ('Pss', 'Rss', 'Pss_Anon', 'Pss_File', 'Pss_Shmem')),
            process_status_KiB=fields(row['proc_status'], ('VmRSS', 'VmHWM', 'VmSize', 'VmPeak', 'VmSwap')),
            threads=fields(row['proc_status'], ('Threads',))['Threads'],
            system_KiB=fields(row['meminfo'], ('MemTotal', 'MemAvailable', 'CmaTotal', 'CmaFree', 'SwapTotal', 'SwapFree')),
            explicit_requested_live_bytes=row['explicit_requested_live_bytes'],
            process_exit_release_proven_at_sample=row['process_exit_release_proven']))
    need([s['phase'] for s in samples] == ['before_device_open', 'explicit_bos_live', 'after_api_close_before_process_exit'] and
         [s['explicit_requested_live_bytes'] for s in samples] == [0, 49344, 0], 'memory phase/live counts differ')
    return dict(schema='A10_SINGLE_RESOURCE_LEDGER_V1', domain='BOARD_CAPTURE_PC_DERIVATION',
        source=worker_path.relative_to(audit.ROOT).as_posix(), source_sha256=digest(worker_path), samples=samples,
        physical_view=dict(bo_regions=[dict(start=a, start_hex=hex(a), end_exclusive=a+BO_BYTES,
            bytes_requested=BO_BYTES, memory_group=3) for a in result['addresses']],
            maximum_simultaneously_requested_explicit_bytes=49344, physical_allocation_peak_bytes=None,
            implicit_xrt_allocation_bytes=None, high_address_reachability=None, entire_low_address_reachability=None,
            full_model_3200MiB_envelope_proven=False),
        sync_native_API_observations_us={k: result[k] for k in
            ('sync_in_native_call_total_us', 'sync_in_inclusive_wall_us', 'sync_out_native_call_us')},
        pure_dma_latency_us=None, bandwidth_bytes_per_s=None, performance_improvement=None,
        later_process_exit_release=dict(normal_waitpid=True, complete_fd_vma_scan=True, module_refcount=0,
            source='result_readback_01/lifecycle.jsonl', scan_started_ns=release['scan']['scan_started_ns']),
        accounting_rule='Do not add CMA, PSS/RSS and BO as disjoint physical usage; samples are not atomic or peaks.',
        limits=['API sync timing excludes event writes, but includes native software overhead; not pure DMA.',
                'Old peer sync timing includes logger fsync and is not a comparable speed baseline.',
                'API-close sample is before child exit, not itself full release proof.',
                'No model/voice memory, broad address/peak or sustained performance claim.'])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write-artifacts', action='store_true')
    args = ap.parse_args()
    if not args.write_artifacts:
        print(json.dumps(dict(mode='PLAN_ONLY', board_contact=False)))
        return 0
    root, evidence = audit.ROOT, audit.EVIDENCE
    inputs = audit.load_inputs()
    assessed = audit.assess(*inputs)
    need(assessed == audit.read(evidence/'audit_01.json'), 'independent audit differs')
    pc = root/'evidence/board_platform/A10_20261023_single_isolation_pc_v1'
    for path, count in ((pc/'tests_02.json', 27), (pc/'host_tests_02.json', 7), (evidence/'audit_tests_01.json', 10)):
        record = audit.read(path)
        need(record['status'] == 'PASS_PC_ONLY' and all(r['exit_code'] == 0 for r in record['records']), 'PC check failed')
        need('Ran '+str(count)+' tests' in record['records'][0]['stderr'], 'PC count differs')
    need(all(r['exit_code'] == 0 for r in audit.read(pc/'contracts_01.json')['records']), 'contract check failed')
    manifest = verify_bundle(root/'platform/local'/audit.WINDOW, audit.MANIFEST_SHA)
    for name in SOURCES:
        need(digest(Path(__file__).parent/name) == manifest['files'][name]['sha256'], 'tested source changed')
    prior = audit.read(root/'evidence/board_platform/A10_20261023_isolated_idle_v4/audit_01.json')
    need(prior['status'] == 'PASS_BOARD_IDLE_WITH_KNOWN_LIMITATIONS', 'prior isolated idle not passed')
    peer = audit.read(root/'evidence/board_platform/A10_20261023_peer_intake/verified_intake_receipt.json')
    need(peer['peer_evidence']['normal_1036_cold_restore'] == 'PASS_PEER_RECOVERY_RECEIPTS_REVIEWED' and
         peer['peer_evidence']['postcompute_unload'] == 'FAILED_PRESERVED', 'historical recovery/failure lost')
    result = audit.read(evidence/'result_readback_01/worker-result.json')
    rows = inputs[0]
    release = next(r for r in rows if r['event'] == 'RELEASE_PRECHECK_PASSED_NOT_UNLOADED')
    ledger = resource_ledger(evidence/'result_readback_01/worker.stdout.jsonl', result, release)
    observation = audit.read(evidence/'candidate_review_01/candidate_observation.json')
    packet = inputs[3]
    kernel = (evidence/'result_readback_01/kernel.raw.txt').read_text()
    need('Machine model: ZynqMP KV260 revB' in kernel, 'model evidence missing')
    requirements = [
        dict(id='A10-1', status='PASS_REUSED_AND_FRESH_IDENTITY', evidence='candidate_review_01/candidate_observation.json'),
        dict(id='A10-2', status='PASS_OBSERVED_ARM64_IRQ2_XRT_2_18', evidence='result_readback_01/kernel.raw.txt'),
        dict(id='A10-3', status='PASS_ONE_N32_AND_4080_GUARDS', evidence='audit_01.json'),
        dict(id='A10-4', status='CANCELLED_BY_USER_NOT_PASS', evidence='../../../docs/A10_ACCEPTANCE_SAFE_20261019.md'),
        dict(id='A10-5_D11', status='PASS_LIMITED_SMALL_BO_AND_SEPARATE_MEMORY_VIEWS', evidence='resource_ledger.json'),
        dict(id='A10-6_D09', status='PASS_NORMAL_POSTCOMPUTE_RELEASE_DEFAULT_PL_AND_INDEPENDENT_READBACK', evidence='audit_01.json'),
        dict(id='ABNORMAL_SAFETY', status='PASS_PC_FAILURE_GATES_BOARD_INJECTION_SAFETY_EXCLUDED', evidence='../A10_20261023_single_isolation_pc_v1/tests_02.json'),
        dict(id='P2', status='NOT_IMPLEMENTED_SAFETY_EXCLUDED_NOT_BLOCKING_MINIMAL_SCOPE', evidence='REPORT.md')]
    closeout = dict(schema='A10_FINAL_MINIMAL_ACCEPTANCE_V1', status='PASS_MINIMAL_WITH_LIMITATIONS',
        scope='User-revised A10 minimal platform path, not original 1000-run, A11, A12 or product acceptance',
        requirements=requirements, new_compute_submissions=1, earlier_peer_submissions_kept_separate=1,
        new_reboots=0, new_qspi_writes=0, default_boot_changed=False, pressure_test=False,
        postcompute_defect='FIX_VERIFIED_FOR_THIS_SINGLE_ISOLATED_PROCESS_LIFECYCLE_ONLY_OLD_FAILURE_PRESERVED',
        current_kernel='6.8.12-a10irq2', default_boot_kernel='original 6.8.0-1036-xilinx bundle unchanged',
        normal_1036_restore_this_window='NOT_PERFORMED_PRIOR_RECOVERY_EVIDENCE_REUSED',
        software_reboot='NOT_VERIFIED_RELIABLE_NO_RETRY',
        known_advisories=assessed['reviewed_advisories'], broad_performance_or_stability_accepted=False,
        A11='NOT_STARTED_NOT_ACCEPTED', A12='NOT_STARTED_NOT_ACCEPTED',
        next='A11 PC readiness review and separately authorized bounded actual MLP test; no automatic board operation',
        board_contact_by_this_export=False, independent_audit_sha256=digest(evidence/'audit_01.json'))
    profile = dict(schema='A10_OBSERVED_MINIMAL_BOARD_PROFILE_V1', domain='BOARD', A10=closeout['status'],
        boot_id=audit.BOOT, machine_id_sha256=assessed['machine_sha256'], model='ZynqMP KV260 revB',
        architecture='aarch64', kernel=assessed['kernel'], userspace_xrt='2.18.0',
        cpu_features_from_boot=[line for line in kernel.splitlines() if 'CPU features:' in line],
        os_release_recaptured_this_window=None, platform_file_hashes=observation['platform_hashes'],
        tested_asset_sha256=ASSETS, package_manifest_sha256=audit.MANIFEST_SHA,
        observed_memory_KiB=fields(packet['memory_raw'], ('MemTotal', 'MemAvailable', 'CmaTotal', 'CmaFree')),
        controller_sampled_temperature_range_mC=assessed['sampled_temperature_range_mC'],
        final_temperature_mC=packet['temperatures_mC'], last_state='DEFAULT_PL_AND_GDM_RESTORED_IRQ2_STILL_RUNNING',
        restored_overlay=packet['overlays'], zocl_present=False, render_nodes=[], manager_present=False,
        active_lease_present=False, maintenance_locks_held=False, uart_released=True, ssh_released=True,
        temporary_ethernet_ip='192.168.2.2/24', network_changed_this_window=False,
        default_boot_changed=False, normal_1036_return_this_window='NOT_PERFORMED',
        staged_test_files_retained_not_loaded='/lib/firmware/xilinx/'+audit.WINDOW,
        metadata_groups=[3,3,3], explicit_bo_budget_bytes=49344, physical_bo_peak_bytes=None,
        model_memory_budget_bytes=None, model_hardware_accepted=False, performance_conclusion=None,
        sources=dict(audit='audit_01.json', resources='resource_ledger.json',
                     kernel_raw_sha256=assessed['kernel_raw_sha256'], final_uart='final_preflight_01.json'))
    artifacts = {'resource_ledger.json': ledger, 'board_profile.json': profile, 'A10_ACCEPTANCE.json': closeout}
    need(all(not (evidence/name).exists() for name in artifacts), 'no overwrite of prior closeout')
    backup = evidence/'docs_before'
    backup.mkdir()
    for name in DOCS:
        destination = backup/name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root/'docs'/name, destination)
    for name, data in artifacts.items():
        with (evidence/name).open('x', encoding='utf-8') as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
    print(json.dumps(dict(status=closeout['status'], artifacts=list(artifacts), board_contact=False,
                          controller_seconds=assessed['controller_elapsed_s'], PC_methods=44)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
