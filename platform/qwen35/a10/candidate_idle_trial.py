"""Candidate-specific, idle-only entry. Default prints a PC plan; never connects.

Preparation is PC-only. Execution needs a separately authorized maintenance
window, the exact bundle hash, and a fresh manually reviewed kernel baseline.
Neither a plan, a review file nor an execution flag grants user authorization.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import uuid

# A plan-only invocation must leave the sealed bundle byte-for-byte unchanged.
# Set this before importing local helpers; don't weaken the inventory validator.
sys.dont_write_bytecode = True

from idle_board_trial import Trial, HASHES, RESTORE, MACHINE, DEFAULT, digest, need
from kernel_log_gate import diagnostics, digest as text_digest

KERNEL = '6.8.12-a10irq1'
PACKAGE = 'a10-vadd-20261021-candidate'
DRIVER = '/usr/lib/modules/6.8.12-a10irq1/extra/zocl.ko'
DRIVER_SHA = '2aa089c3967e8fa72480310fe2cc12aaa7d920135f5322d8596819835ca087cc'
FIT_SHA = 'a393f397a673a2f3636c8b9f85d8a59f7257c24d33c34d28a67b11c410a11b81'
SCRIPTS = ('candidate_idle_trial.py', 'idle_board_trial.py', 'kernel_log_gate.py')
SHELL = dict(shell_type='XRT_FLAT', num_pl_slots=1, num_aie_slots=0)
REVIEW_SCOPE = 'A10_CANDIDATE_IDLE_BASELINE_ONLY_NO_COMPUTE'


def plan():
    return dict(
        schema='A10_CANDIDATE_IDLE_V1', status='PC_PREPARED_BOARD_NOT_TESTED',
        authorized=False, execution_performed=False, boot_id=None,
        machine_id_sha256=MACHINE, kernel=KERNEL,
        package=PACKAGE, target='/lib/firmware/xilinx/' + PACKAGE,
        driver=dict(path=DRIVER, sha256=DRIVER_SHA), candidate_fit_sha256=FIT_SHA,
        test_artifact_hashes=HASHES, restore_package=DEFAULT,
        restore_artifact_hashes=RESTORE, shell=SHELL,
        limits=dict(temperature_below_mC=55000, mem_available_min_KiB=1048576,
                    cma_free_min_KiB=32768, compute_runs=0, compute_BO_allocations=0),
        numerical_regression='CANCELLED_BY_USER',
        required_before_execution=[
            'separate user maintenance authorization; no implied permission from this plan',
            'candidate Linux boot and fresh identity/health/original boot hash checks',
            'complete raw dmesg from that boot with each diagnostic explicitly reviewed',
            'pin bundle manifest SHA256 independently before transfer',
        ],
        baseline_policy='Exact reviewed snapshot only; all new diagnostics stop further mutations.',
        timeout_policy='Unknown management-call completion parks with locks; no kill/retry/reset.',
        final_policy='Independent default-overlay/module/node/holder/hash readback; exit 0 alone is insufficient.',
        excluded=['compute/XRT device opens', 'xclbin or compute-host payload',
                  'BO allocation or bandwidth tests', 'reboot/QSPI/default boot changes',
                  'forced unload', 'automatic recovery', 'pressure or repeated numeric regression'],
    )


def prepare(root, output):
    """Produce an exclusive PC bundle; a partial directory is never overwritten."""
    payload = {}
    for name, expected in HASHES.items():
        p = root / 'platform/build/a1-overlay-candidate-20260928' / name
        need(not p.is_symlink(), 'artifact symlink')
        payload[name] = p.read_bytes()
        need(hashlib.sha256(payload[name]).hexdigest() == expected, 'artifact changed: ' + name)
    for name in SCRIPTS:
        p = Path(__file__).resolve().parent / name
        need(not p.is_symlink(), 'script symlink')
        payload[name] = p.read_bytes()
    payload['shell.json'] = (json.dumps(SHELL, indent=2) + '\n').encode()
    manifest = dict(plan=plan(), files={
        name: dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
        for name, data in payload.items()})
    output.mkdir()  # no exist_ok, no board API, no automatic transfer
    for name, data in payload.items():
        with (output / name).open('xb') as stream:
            stream.write(data)
    with (output / 'bundle.pending.json').open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(manifest, indent=2) + '\n')
    return dict(status='PC_BUNDLE_ONLY', manifest_sha256=digest(output / 'bundle.pending.json'),
                board_contact=False, authorized=False, directory=str(output))


def verify_bundle(source, expected_sha):
    need(isinstance(expected_sha, str) and re.fullmatch(r'[0-9a-f]{64}', expected_sha),
         'independently pinned bundle SHA required')
    p = source / 'bundle.pending.json'
    need(not source.is_symlink() and not p.is_symlink() and digest(p) == expected_sha,
         'bundle manifest changed')
    manifest = json.loads(p.read_text(encoding='utf-8'))
    need(set(manifest) == {'plan', 'files'} and manifest['plan'] == plan(), 'candidate plan differs')
    expected_names = set(HASHES) | set(SCRIPTS) | {'shell.json'}
    need(set(manifest['files']) == expected_names, 'payload inventory differs')
    # Reject an accidentally included executable/xclbin, not just known suffixes.
    need({p.name for p in source.iterdir()} == expected_names | {'bundle.pending.json'},
         'unexpected bundle entry or prior result; no automatic resume')
    for name, entry in manifest['files'].items():
        p = source / name
        need(p.is_file() and not p.is_symlink() and
             set(entry) == {'bytes', 'sha256'} and type(entry['bytes']) is int and
             p.stat().st_size == entry['bytes'] and digest(p) == entry['sha256'],
             'payload differs: ' + name)
    need(json.loads((source / 'shell.json').read_text()) == SHELL, 'shell differs')
    for name, wanted in HASHES.items():
        need(digest(source / name) == wanted, 'pinned artifact differs')
    return manifest


def validate_review(review, raw):
    """Require a documented decision for EACH existing diagnostic; no new waiver."""
    need(isinstance(review, dict) and review.get('schema') == 'A10_IDLE_BASELINE_REVIEW_V1'
         and review.get('scope') == REVIEW_SCOPE and review.get('kernel') == KERNEL
         and review.get('machine_id_sha256') == MACHINE
         and review.get('driver_sha256') == DRIVER_SHA
         and review.get('compute_authorized') is False, 'baseline review scope/identity differs')
    boot = review.get('boot_id')
    need(isinstance(boot, str) and re.fullmatch(r'[0-9a-f-]{36}', boot), 'fresh boot UUID required')
    need(str(uuid.UUID(boot)) == boot and uuid.UUID(boot).int != 0, 'invalid boot UUID')
    need(isinstance(raw, str) and raw.strip() and raw.endswith('\n') and '\x00' not in raw,
         'incomplete raw baseline')
    need(review.get('raw_dmesg_sha256') == text_digest(raw), 'baseline bytes differ')
    need(isinstance(review.get('reviewer'), str) and review['reviewer'].strip()
         and isinstance(review.get('review_rationale'), str) and review['review_rationale'].strip(),
         'explicit review identity and rationale required')
    decisions = review.get('diagnostic_decisions')
    found = diagnostics(raw)
    need(isinstance(decisions, list) and len(decisions) == len(found),
         'missing diagnostic review; do not deduplicate')
    for decision, diagnostic in zip(decisions, found):
        need(isinstance(decision, dict) and decision.get('diagnostic') == diagnostic
             and decision.get('decision') == 'ACCEPT_BASELINE_FOR_IDLE_ONLY'
             and isinstance(decision.get('rationale'), str) and decision['rationale'].strip(),
             'unreviewed/reordered diagnostic')
    return boot, text_digest(raw)


def command_gate(argv, changing):
    readonly = [['dmesg', '--color=never'], ['dfx-mgr-client', '-listPackage']]
    writes = [['insmod', DRIVER], ['rmmod', 'zocl'],
              ['dfx-mgr-client', '-load', PACKAGE], ['dfx-mgr-client', '-load', DEFAULT]]
    remove = (len(argv) == 3 and argv[:2] == ['dfx-mgr-client', '-remove']
              and isinstance(argv[2], str) and argv[2].isascii() and argv[2].isdigit())
    need((not changing and argv in readonly) or (changing and (argv in writes or remove)),
         'outside candidate idle command allowlist')


class CandidateTrial(Trial):
    kernel_release = KERNEL
    package = PACKAGE
    target = Path('/lib/firmware/xilinx') / PACKAGE
    driver = Path(DRIVER)
    driver_sha256 = DRIVER_SHA
    temperature_limit_mC = 55000
    memory_reserve_KiB = 1048576
    history_name = 'a10-idle-candidate-20261021.json'
    authorization_label = 'SEPARATE_USER_CONFIRMATION_REQUIRED_CANDIDATE_IDLE_ONLY'

    def __init__(self, source, bundle_sha, review, raw):
        # Validate before creating the result, locks or firmware directory.
        verify_bundle(source, bundle_sha)
        self.boot, self.reviewed_baseline_sha256 = validate_review(review, raw)
        super().__init__(source)
        self.emit('CANDIDATE_IDLE_PREPARED_NOT_YET_EXECUTED', kernel=KERNEL, boot_id=self.boot,
                  bundle_sha256=bundle_sha, baseline_review=review, raw_baseline=raw,
                  compute_authorized=False)

    def command(self, argv, state_changing=False):
        command_gate(argv, state_changing)
        return super().command(argv, state_changing)

    def run(self):
        # Baseline errors stop before even staging a firmware package.
        need(os.geteuid() == 0 and os.uname().machine == 'aarch64'
             and os.uname().release == KERNEL, 'wrong root/kernel/architecture')
        self.snapshot('candidate_preflight')
        self.kernel_checkpoint('reviewed_preflight', None)
        super().run()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument('--prepare', type=Path, metavar='NEW_PC_DIRECTORY')
    mode.add_argument('--execute-authorized-idle-once', action='store_true')
    ap.add_argument('--project-root', type=Path, default=Path(__file__).resolve().parents[3])
    ap.add_argument('--bundle-sha256')
    ap.add_argument('--baseline', type=Path)
    ap.add_argument('--review', type=Path)
    args = ap.parse_args(argv)
    if args.prepare:
        print(json.dumps(prepare(args.project_root, args.prepare), indent=2))
    elif not args.execute_authorized_idle_once:
        print(json.dumps(plan(), indent=2))
    else:
        need(args.baseline is not None and args.review is not None, 'fresh baseline and review required')
        raw = args.baseline.read_bytes().decode('utf-8', errors='strict')
        trial = CandidateTrial(Path(__file__).resolve().parent, args.bundle_sha256,
                               json.loads(args.review.read_text(encoding='utf-8')), raw)
        try:
            trial.run()
        except Exception as exc:
            trial.emit('STOP_NO_AUTOMATIC_RECOVERY', error=str(exc), error_type=type(exc).__name__)
            raise
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
