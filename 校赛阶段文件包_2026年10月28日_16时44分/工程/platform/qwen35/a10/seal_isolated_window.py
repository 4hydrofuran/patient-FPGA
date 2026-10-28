"""PC-only consistency/hash receipt; does not contact the board or claim A10 PASS."""
import argparse
import hashlib
import json
from pathlib import Path
import re


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[3]
    evidence = root / 'evidence/board_platform/A10_20261023_isolated_idle_v1'
    read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
    final = read(evidence/'final_readback_01/state.json')
    packet = read(evidence/'final_readback_01/stdout.json')
    cleanup = read(evidence/'final_readback_01/prepl-cleanup.json')
    profile = read(evidence/'board_profile.observed_irq2.json')
    status = read(root/'docs/PROJECT_STATUS.json')['a10_isolated_idle_20261023']
    assert final['manager_proc'] is None and packet['active_lease'] is None
    assert final['module_present'] is False and final['test_package_present'] is False
    assert final['render_nodes'] == [] and final['gdm_state'] == 'active'
    assert final['overlays'] == {'k26-starter-kits_image_1': 'applied'}
    assert cleanup['status'] == 'PREPL_ABORT_CLEANUP_COMPLETE_DEFAULT_PL_UNTOUCHED'
    assert cleanup['pidfd_exit_confirmed'] is True and cleanup['pl_loads'] == cleanup['compute_runs'] == 0
    assert profile['boot_id'] == final['boot_id'] == status['final_observation']['boot_id']
    assert profile['temperature_mC'] == final['temperatures_mC'] == status['final_observation']['temperature_mC']
    assert digest(evidence/'final_readback_01/kernel.raw.txt') == profile['sources']['kernel_raw_sha256']
    baseline = (evidence/'candidate_review_02/baseline.raw.txt').read_bytes()
    end = (evidence/'final_readback_01/kernel.raw.txt').read_bytes()
    assert end.startswith(baseline)
    extra = end[len(baseline):].decode()
    assert re.fullmatch(r'<7>\[\s*1450\.481873\] rfkill: input handler enabled\n'
                        r'<7>\[\s*1974\.558819\] rfkill: input handler disabled\n', extra), extra
    test = read(evidence/'idle_components_wsl_06.json')
    assert test['exit_code'] == 0 and 'Ran 73 tests' in test['stderr'] and test['stderr'].endswith('OK\n')
    for n in (1, 2, 3):
        bundle = root/f'platform/local/a10-isolated-idle-20261023-v{n}'
        manifest = read(bundle/'manifest.json')
        for name, meta in manifest['files'].items():
            assert digest(bundle/name) == meta['sha256'] and (bundle/name).stat().st_size == meta['bytes']
    source_names = ('isolated_idle_trial.py', 'accelerator_release_gate_v2.py', 'test_prepl_quiet.py',
                    'test_idle_checkpoint.py', 'test_ps_display_release.py', 'cleanup_prepl_isolated_once.py',
                    'read_isolated_result.py', 'fetch_isolated_result.py', 'seal_isolated_window.py')
    files = [p for p in evidence.rglob('*') if p.is_file() and p.resolve() != args.output.resolve()]
    files += [Path(__file__).parent/name for name in source_names]
    files += [root/'docs'/name for name in ('PROJECT_STATUS.json','DESIGN_GAP.md','DECISIONS.md',
              'TEST_MATRIX.md','AI_ASSISTANCE.md','status/A.md','handoffs/A_A10_ISOLATED_IDLE_20261023.md')]
    report = dict(status='PASS_PC_EVIDENCE_CONSISTENCY_NOT_A10', A10='NOT_PASSED',
                  board_contact=False, current_window_hardware_calls=0, latest_linux_methods=73,
                  source_revision='Bounded pre-PL readiness fix is PC-only; no new bundle/board run',
                  files={p.relative_to(root).as_posix(): dict(bytes=p.stat().st_size, sha256=digest(p)) for p in files})
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2)
    print(json.dumps(dict(status=report['status'], hashed_files=len(files), A10='NOT_PASSED', board_contact=False)))


if __name__ == '__main__':
    main()
