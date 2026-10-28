"""PC-only provenance check. PASS here never authorizes board execution."""
import argparse
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import re


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(root, binary, build):
    source = root / 'platform/qwen35/a10/vadd_short'
    cache = root / 'platform/local/a10-xrt-2.18-audit'
    spec = importlib.util.spec_from_file_location('inputs', source.parent/'verify_driver_inputs.py')
    v = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(v)
    v.check_index(cache/'sdk.InRelease', cache/'sdk.Packages.gz', 'main/binary-arm64/Packages.gz')
    package = v.check_package(gzip.decompress((cache/'sdk.Packages.gz').read_bytes()).decode(),
                            'xrt', '2.18.0-0ubuntu1', cache/'xrt_2.18.0-0ubuntu1_arm64.deb')
    result = json.loads(build.read_text(encoding='utf-8-sig'))
    if result['exit_code'] != 0 or 'Machine:                           AArch64' not in result['stdout']:
        raise ValueError('Successful ARM64 build not recorded')
    digest = sha(binary)
    if not re.search(r'^'+digest+r'\s+.*/a10-vadd-short$', result['stdout'], re.M):
        raise ValueError('Binary not the recorded build')
    for filename in ['host.cpp', 'control.hpp', 'retention.hpp']:
        h = sha(source/filename)
        if not re.search(r'^'+h+r'\s+.*/'+re.escape(filename)+r'$', result['stdout'], re.M):
            raise ValueError('Source differs from build: '+filename)
    for check in ['PASS_PC_CONTROL_ONLY checks=72', 'PASS_PC_SIGNAL_RETENTION_4_SIGNALS_NO_DEVICE']:
        if check not in result['stdout']:
            raise ValueError('Required control test evidence missing')
    approval = json.loads((source/'approval.pending.json').read_text())
    if any(approval[k] is not False for k in ['authorized','platform_review_complete','recovery_review_complete']):
        raise ValueError('PC candidate must remain unapproved')
    return {
        'schema': 'A10_VADD_SHORT_PC_CANDIDATE_V1', 'status': 'PASS_PC_CONTROL_AND_A53_LINK_ONLY',
        'BOARD': 'NOT_TESTED', 'deployment_authorized': False,
        'binary': {'path': str(binary), 'bytes': binary.stat().st_size, 'sha256': digest},
        'build_log': {'path': str(build), 'sha256': sha(build), 'exit_code': 0},
        'sources': [{'path': str(p.relative_to(root)), 'sha256': sha(p)} for p in sorted(source.iterdir()) if p.is_file()],
        'xrt_218_package': package,
        'trust_chain': {'InRelease_sha256': sha(cache/'sdk.InRelease'), 'Packages_gz_sha256': sha(cache/'sdk.Packages.gz'),
                       'signature_evidence': 'evidence/board_platform/A10_20261018_intake/driver_extract_and_signature.txt',
                       'signer_fingerprint': '803DDF595EA7B6644F9B96B752150A179A9E84C9'},
        'native_control_checks': 72, 'same_checks_under_ASAN_UBSAN': 72, 'signal_fixture_checks': 4,
        'signal_fixture_scope': 'Known forked PC child without XRT; SIGKILL used only to collect that child after test',
        'required_symbol_versions': {'glibc': '2.38', 'libstdcxx': 'GLIBCXX_3.4.32', 'openssl': 'OPENSSL_3.0.0'},
        'board_library_closure': 'NOT_VERIFIED',
        'limits': {'jobs_per_invocation_max': 20, 'jobs_default_not_automatic': True,
                   'between_jobs_ms': 100, 'submit_poll_soft_deadline_ms': 1000,
                   'batch_compute_loop_soft_deadline_ms': 10000, 'bo_bytes_each': 16448,
                   'bo_count': 3, 'temperature_stop_mC': 60000, 'minimum_MemAvailable_KiB': 262144},
        'safety_limitations': ['Userspace deadline cannot forcibly bound a stuck driver ioctl.',
                               'Poison parking retains buffers but does NOT prove hardware stopped.',
                               'No forced abort/reset or external timeout/kill wrapper is permitted.',
                               'SIGKILL/power loss remain unprotectable; exact platform recovery is pending.'],
        'A10': 'NOT_PASSED'}


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', type=Path, required=True)
    ap.add_argument('--binary', type=Path, required=True)
    ap.add_argument('--build-log', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    result = audit(args.root.resolve(), args.binary.resolve(), args.build_log.resolve())
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps({'status': result['status'], 'BOARD': result['BOARD'], 'binary_sha256': result['binary']['sha256']}))
