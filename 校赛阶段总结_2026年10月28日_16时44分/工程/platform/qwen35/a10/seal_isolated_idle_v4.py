"""Seal this completed idle window on the PC; no hardware contact or A10 PASS."""
import argparse
import json
from pathlib import Path

import audit_isolated_idle_result as audit
from isolated_idle_policy import SOURCES, digest, verify_bundle


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    evidence, root = audit.EVIDENCE, audit.ROOT
    reproduced = audit.assess(*audit.load_inputs())
    assert reproduced == audit.read(evidence / 'audit_01.json')
    status = audit.read(root / 'docs/PROJECT_STATUS.json')['a10_isolated_idle_v4_board_20261023']
    profile = audit.read(evidence / 'board_profile.observed_irq2.json')
    assert status['status'] == reproduced['status'] and status['A10'] == reproduced['A10'] == profile['A10']
    assert status['controller_elapsed_s'] == reproduced['controller_elapsed_s']
    assert status['sampled_temperature_range_mC'] == profile['controller_sampled_temperature_range_mC'] == reproduced['sampled_temperature_range_mC']
    assert profile['boot_id'] == status['boot_id'] == audit.BOOT
    assert profile['sources']['kernel_raw_sha256'] == reproduced['kernel_raw_sha256']
    tests = audit.read(evidence / 'host_pc_tests_02.json')
    assert tests['status'] == 'PASS_PC_HOST_PLANS' and all(r['exit_code'] == 0 for r in tests['records'])
    assert 'Ran 13 tests' in tests['records'][0]['stderr'] and tests['records'][0]['stderr'].endswith('OK\n')
    assert json.loads(tests['records'][1]['stdout'])['plans'] == 8
    for name, pin in tests['host_sha256'].items():
        assert digest(Path(__file__).parent / name) == pin
    manifest = verify_bundle(root / 'platform/local' / audit.WINDOW, audit.MANIFEST_SHA)
    # The already-tested production controller/worker bytes were not changed this window.
    for name in SOURCES:
        assert digest(Path(__file__).parent / name) == manifest['files'][name]['sha256']
    files = [p for p in evidence.rglob('*') if p.is_file() and p.resolve() != args.output.resolve()]
    files += [Path(__file__).parent / name for name in tests['host_sha256']]
    files += [Path(__file__), Path(__file__).parent / 'verify_isolated_host_pc.py']
    files += [root/'docs'/name for name in ('PROJECT_STATUS.json', 'DESIGN_GAP.md', 'DECISIONS.md',
              'TEST_MATRIX.md', 'AI_ASSISTANCE.md', 'status/A.md', 'A10_REMAINING_MINIMUM_20261021.md',
              'A10_ACCEPTANCE_SAFE_20261019.md')]
    result = dict(status='PASS_PC_ARCHIVE_CONSISTENCY', board_contact=False,
                  board_scope='ONE_IDLE_LIFECYCLE_ALREADY_COMPLETED', A10=reproduced['A10'],
                  production_bundle_unchanged=True, new_compute_submissions=0,
                  files={p.relative_to(root).as_posix(): dict(bytes=p.stat().st_size, sha256=digest(p)) for p in files})
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps(dict(status=result['status'], A10=result['A10'], files=len(result['files']), board_contact=False)))


if __name__ == '__main__':
    main()
