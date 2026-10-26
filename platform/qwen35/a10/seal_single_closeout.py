"""PC archive consistency seal for completed minimal A10; no board contact."""
import argparse
import json
from pathlib import Path
import shutil

import audit_single_result as audit
from closeout_single import DOCS, resource_ledger
import isolated_idle_policy as idle
import single_compute_policy as policy


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    root, evidence = audit.ROOT, audit.EVIDENCE
    inputs = audit.load_inputs()
    checked = audit.assess(*inputs)
    assert checked == audit.read(evidence/'audit_01.json')
    acceptance = audit.read(evidence/'A10_ACCEPTANCE.json')
    profile = audit.read(evidence/'board_profile.json')
    project = audit.read(root/'docs/PROJECT_STATUS.json')
    current = project['a10_final_minimal_acceptance_20261023']
    assert acceptance['status'] == profile['A10'] == current['status'] == project['stage_status'] == 'PASS_MINIMAL_WITH_LIMITATIONS'
    assert current['new_compute_submissions'] == checked['new_compute_submissions'] == acceptance['new_compute_submissions'] == 1
    assert current['controller_elapsed_s'] == checked['controller_elapsed_s']
    assert current['sampled_temperature_range_mC'] == profile['controller_sampled_temperature_range_mC'] == checked['sampled_temperature_range_mC']
    assert profile['sources']['kernel_raw_sha256'] == checked['kernel_raw_sha256']
    assert profile['physical_bo_peak_bytes'] is None
    assert acceptance['broad_performance_or_stability_accepted'] is False
    release = next(r for r in inputs[0] if r['event'] == 'RELEASE_PRECHECK_PASSED_NOT_UNLOADED')
    reproduced = resource_ledger(evidence/'result_readback_01/worker.stdout.jsonl',
                                audit.read(evidence/'result_readback_01/worker-result.json'), release)
    assert reproduced == audit.read(evidence/'resource_ledger.json')
    assert project['linux_memory_bytes'] == profile['observed_memory_KiB']['MemTotal']*1024
    for row in acceptance['requirements']:
        assert (evidence/row['evidence']).resolve().is_file(), row['evidence']
    frozen = policy.verify_bundle(root/'platform/local'/audit.WINDOW, audit.MANIFEST_SHA)
    for name in policy.SOURCES:
        assert policy.digest(Path(__file__).parent/name) == frozen['files'][name]['sha256']
    old = idle.verify_bundle(root/'platform/local/a10-isolated-idle-20261023-v4',
                            '726723f471aa6bb3f6902b5a65a543402be0cf94202c25e169f89b9703867b06')
    for name in idle.SOURCES:
        assert policy.digest(Path(__file__).parent/name) == old['files'][name]['sha256']
    previous = audit.read(evidence/'docs_before/PROJECT_STATUS.json')
    allowed = {'stage_status', 'a10_board_identity_verified', 'a10_branch', 'a10_board_profile',
               'updated_at', 'branch', 'blockers', 'blocker_scope', 'next_action',
               'board_availability_basis', 'linux_memory_bytes', 'a10_final_minimal_acceptance_20261023'}
    assert {k for k in project if project.get(k) != previous.get(k)} <= allowed
    assert set(previous) <= set(project)
    # Preserve exact current sources and governance, not a mutable-source-only index.
    snapshot = evidence/'source_snapshot'
    snapshot.mkdir()
    code = Path(__file__).parent
    names = set(policy.SOURCES) | {p.name for p in code.glob('*single*.py')} | {
        'single_prepare_uart.ps1', 'collect_readonly_uart.ps1', 'import_isolated_readonly.py'}
    for name in sorted(names):
        shutil.copyfile(code/name, snapshot/name)
    docs_snapshot = evidence/'docs_after'
    docs_snapshot.mkdir()
    for name in (*DOCS, 'handoffs/A_A10_MINIMAL_COMPLETE_20261023.md'):
        out = docs_snapshot/name
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root/'docs'/name, out)
    pc = root/'evidence/board_platform/A10_20261023_single_isolation_pc_v1'
    files = [p for directory in (evidence, pc) for p in directory.rglob('*')
             if p.is_file() and p.resolve() != args.output.resolve()]
    # The command recorder is still RESERVED while this runs; seal it separately later.
    files = [p for p in files if p.name != 'seal_command_01.json']
    result = dict(status='PASS_PC_ARCHIVE_CONSISTENCY', A10='PASS_MINIMAL_WITH_LIMITATIONS',
        board_contact=False, board_scope='ALREADY_COMPLETED_ONE_N32_RELEASE_AND_DEFAULT_RECOVERY',
        no_new_trial=True, original_idle_sources_unchanged=True, prior_A00_A17_records_preserved=True,
        files={p.relative_to(root).as_posix(): dict(bytes=p.stat().st_size, sha256=policy.digest(p)) for p in sorted(files)})
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps(dict(status=result['status'], A10=result['A10'], files=len(result['files']), board_contact=False)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
