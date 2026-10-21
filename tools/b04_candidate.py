"""Package and replay the complete B04 offline candidate, keeping BOARD untested."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import zipfile

from b04_common import ROOT, digest, now, read_json, run, safe_path, write_json
from b04_stage import collect_files, member_name

RECEIPTS = 'reports/b04/joint_20261021/'
A_ROOT = 'evidence/b04/a07_received_20261021/'
REQUIRED = {
    'README_B04_CANDIDATE.md', 'PROJECT_STATUS.json', 'docs/b04/JOINT_PLAN_20261021.md',
    'docs/b04/B04_JOINT_REPORT_20261021.md', 'tools/b04_candidate.py',
    'tools/b04_joint_pc.py', 'tools/b04_joint_audit.py', 'tools/b04_a_preflight.py',
    'tests/b04/native/file_lock.cpp', 'tests/b04/native/sys/file.h', 'tests/b04/native/openssl/evp.h',
    'tests/b04/candidate_checks.py',
    'config/b04/kernel_profile.json', 'contracts/contract_lock.json',
    'artifact/b03_candidate/w4a8_linear_v1.xo', 'src/w4a8_prefill_v1.cpp',
    RECEIPTS + 'pc.json', RECEIPTS + 'artifact_review.json', RECEIPTS + 'receive.json',
    RECEIPTS + 'profile.json', RECEIPTS + 'private.json',
    A_ROOT + 'a_delivery.json', A_ROOT + 'files.sha256.json', A_ROOT + 'artifacts/w4a8.xclbin',
    A_ROOT + 'artifacts/libsp_linear_xrt_candidate.so', A_ROOT + 'artifacts/sp-linear-host',
}


def validate_manifest(manifest, read_member, names):
    """Bind full package, frozen identities and every received A file to real bytes."""
    if manifest.get('package_kind') != 'B04_PC_CANDIDATE' or manifest.get('BOARD') != 'NOT_TESTED':
        raise ValueError('Wrong full candidate identity or fabricated BOARD status')
    files = manifest.get('files', {})
    if set(files) != set(names) - {'manifest.json'} or not REQUIRED.issubset(files):
        raise ValueError('Missing/extra candidate members or required input')
    for name, expected in files.items():
        member_name(name)
        data = read_member(name)
        if len(data) != expected['bytes'] or hashlib.sha256(data).hexdigest() != expected['sha256']:
            raise ValueError('Candidate member differs: ' + name)
    profile = json.loads(read_member('config/b04/kernel_profile.json'))
    if profile['build_id'] != 0xB3030002 or profile['meta']['bytes'] != 40:
        raise ValueError('Wrong frozen kernel identity')
    for name, expected in profile['frozen_files'].items():
        if files[name]['sha256'] != expected:
            raise ValueError('Frozen kernel changed: ' + name)
    lock = json.loads(read_member('contracts/contract_lock.json'))
    if lock['contract_sha256'] != manifest['public_contract_sha256']:
        raise ValueError('Public contract identity mismatch')
    for name, expected in lock['files'].items():
        if files['contracts/' + name]['sha256'] != expected:
            raise ValueError('Public contract changed')
    a_files = json.loads(read_member(A_ROOT + 'files.sha256.json'))
    received = {name[len(A_ROOT):] for name in files if name.startswith(A_ROOT)}
    if received != set(a_files) | {'files.sha256.json'}:
        raise ValueError('A received source closure differs')
    for name, expected in a_files.items():
        if files[A_ROOT + name] != expected:
            raise ValueError('A received member changed: ' + name)
    for name, expected_status in (('pc.json', 'PASS'),
                                  ('artifact_review.json', 'PASS_OFFLINE_ARTIFACT_AND_ORIGINAL_EVIDENCE_REVIEW'),
                                  ('receive.json', 'PASS')):
        if json.loads(read_member(RECEIPTS + name))['status'] != expected_status:
            raise ValueError('Required joint receipt is not passing')
    pc = json.loads(read_member(RECEIPTS + 'pc.json'))
    outputs = pc['outputs']
    if (outputs['host_rules']['assertions'], outputs['meta_replay']['actual_meta_records'],
        outputs['meta_replay']['tamper_rejections'], outputs['control']['cases'],
        outputs['control']['checks'], outputs['kernel_fixture']['output_checks']) != (970, 66, 396, 29, 554, 32):
        raise ValueError('Required joint coverage is incomplete')
    for name, expected in pc['source_sha256'].items():
        if files[name]['sha256'] != expected:
            raise ValueError('PC receipt source differs: ' + name)
    profile_receipt = json.loads(read_member(RECEIPTS + 'profile.json'))
    private = json.loads(read_member(RECEIPTS + 'private.json'))
    if profile_receipt['status'] != 'PASS' or profile_receipt['profile_sha256'] != files['config/b04/kernel_profile.json']['sha256']:
        raise ValueError('Private profile receipt is stale')
    if private['status'] != 'PASS' or (private['unit_checks'], private['archived_rtl_meta_transactions'], private['job_counter_mutation_rejections']) != (40, 66, 108):
        raise ValueError('Private probe coverage is incomplete')
    artifact = json.loads(read_member(RECEIPTS + 'artifact_review.json'))
    if artifact['A_delivery_sha256'] != files[A_ROOT + 'a_delivery.json']['sha256']:
        raise ValueError('Reviewed A delivery differs')
    for receipt in (profile_receipt, private, artifact):
        for name, expected in receipt.get('input_sha256', {}).items():
            if files[name]['sha256'] != expected:
                raise ValueError('Required receipt input differs: ' + name)
    if manifest.get('phase') == 'final':
        trial = json.loads(read_member(RECEIPTS + 'trial_extraction.json'))
        if trial.get('status') != 'PASS':
            raise ValueError('Final candidate requires prior fresh-directory acceptance')
        for name, expected in trial['rebuild_input_sha256'].items():
            if files[name]['sha256'] != expected:
                raise ValueError('Rebuild inputs changed after trial: ' + name)
    elif manifest.get('phase') != 'trial':
        raise ValueError('Unknown candidate verification phase')
    return manifest


def verify_archive(path, expected_sha):
    if expected_sha and digest(path) != expected_sha.lower():
        raise ValueError('External ZIP SHA256 differs')
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        names = [member_name(info.filename) for info in infos]
        if len(set(name.casefold() for name in names)) != len(names):
            raise ValueError('Duplicate/case-colliding members')
        if any(info.is_dir() or stat.S_ISLNK(info.external_attr >> 16) for info in infos):
            raise ValueError('Directory/symlink ZIP members are forbidden')
        if 'manifest.json' not in names or archive.testzip():
            raise ValueError('Missing manifest or failed CRC')
        return validate_manifest(json.loads(archive.read('manifest.json')), archive.read, names)


def payload_files():
    payload = collect_files()
    payload['README_B04_CANDIDATE.md'] = ROOT / 'README_B04_CANDIDATE.md'
    for path in (ROOT / 'tests/b04').rglob('*'):
        if path.is_file() and '__pycache__' not in path.parts:
            payload[path.relative_to(ROOT).as_posix()] = path
    payload['docs/handoff/HANDOFF.md'] = ROOT / 'docs/handoff/HANDOFF.md'
    # 仅添加受管源码/证据，排除 Python 缓存，不把构建目录、开发环境或旧 ZIP 再套进新包。
    return {name: path for name, path in payload.items()
            if '__pycache__' not in path.parts and path.suffix.lower() not in ('.pyc', '.zip')}


def assemble(output, phase):
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError('Preserve old artifacts; select a new output path')
    if phase == 'trial' and output.name == 'B_pc_candidate_v1.zip':
        raise ValueError('The formal name is reserved until the trial extraction passes')
    payload = payload_files()
    manifest = {'schema_version': 1, 'package_kind': 'B04_PC_CANDIDATE', 'phase': phase,
                'created_at': now(), 'kernel_build_id': '0xB3030002',
                'public_contract_sha256': read_json(ROOT / 'config/b04/kernel_profile.json')['public_contract_sha256'],
                'A_revision': '6dd1a93c2fa44b045276c24f4cc79d94e54b88b3',
                'B04_scope': 'Offline candidate only; A shared runtime/SDK/implementation evidence plus B independent review and replay.',
                'BOARD': 'NOT_TESTED', 'ARM_execution': 'NOT_TESTED',
                'B_new_ARM_target_build': False, 'B_new_HLS_RTL_or_route': False,
                'deployment': 'DISABLED_PENDING_BOARD',
                'final_archive_acceptance': 'Requires matching external extraction receipt, never inferred from filename.',
                'files': {name: {'bytes': path.stat().st_size, 'sha256': digest(path)}
                          for name, path in sorted(payload.items())}}
    validate_manifest(manifest, lambda name: payload[name].read_bytes(), [*payload, 'manifest.json'])
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'x', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name, path in sorted(payload.items()):
            archive.write(path, name)
        archive.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    verify_archive(output, None)
    receipt = {'status': 'PASS_ARCHIVE_INTEGRITY', 'phase': phase, 'finished_at': now(),
               'path': str(output), 'sha256': digest(output), 'bytes': output.stat().st_size,
               'members': len(payload) + 1, 'BOARD': 'NOT_TESTED'}
    write_json(output.with_suffix('.receipt.json'), receipt)
    write_json(output.with_suffix('.manifest.json'), manifest)
    output.with_suffix('.sha256.txt').write_text(digest(output) + '  ' + output.name + '\n', encoding='ascii')
    print('PASS full candidate archive integrity; fresh extraction still required:', output.name, flush=True)


def extract_and_test(args):
    archive_path, target = Path(args.archive).resolve(), Path(args.target).resolve()
    if os.name == 'nt' and not str(target).isascii():
        raise ValueError('This MinGW control-test runner requires an ASCII extraction path; Linux production is unaffected. Use a fresh path such as D:/B04_acceptance.')
    manifest = verify_archive(archive_path, args.sha256)
    target.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(archive_path) as archive:
        for name in [*manifest['files'], 'manifest.json']:
            path = safe_path(target, name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(archive.read(name))
    for name, entry in manifest['files'].items():
        if digest(safe_path(target, name)) != entry['sha256']:
            raise ValueError('Extracted file differs: ' + name)
    steps = {}
    common = [sys.executable, '-B']
    commands = {
        'profile': [*common, 'tools/b04_profile.py', '--cxx', args.cxx, '--work', 'build/b04/fresh_profile', '--receipt', 'reports/b04/fresh_profile.json'],
        'private': [*common, 'tools/b04_selftest.py', '--cxx', args.cxx, '--work', 'build/b04/fresh_private', '--receipt', 'reports/b04/fresh_private.json'],
        'pc_joint': [*common, 'tools/b04_joint_pc.py', '--cxx', args.cxx, '--crypto', args.crypto,
                     '--work', 'build/b04/fresh_pc', '--receipt', 'reports/b04/fresh_pc.json'],
        'artifact_audit': [*common, 'tools/b04_joint_audit.py', '--readelf', args.readelf,
                           '--xclbinutil', args.xclbinutil, '--work', 'build/b04/fresh_artifact_audit', '--receipt-dir', 'reports/b04/fresh_artifact_audit'],
        'candidate_rejections': [*common, 'tests/b04/candidate_checks.py', '--archive', str(archive_path),
                                 '--receipt', 'reports/b04/fresh_candidate_checks.json'],
    }
    for name, command in commands.items():
        _, steps[name] = run(command, target, target / 'build/b04/fresh_commands' / (name + '.log'), timeout=420)
    # 接收的 A 快照在构建后仍须逐字节不变。
    for name, entry in manifest['files'].items():
        if digest(safe_path(target, name)) != entry['sha256']:
            raise ValueError('A packaged input was modified by selftest: ' + name)
    rebuilt = {}
    for name, entry in manifest['files'].items():
        if name.startswith(('tools/', 'tests/', 'src/', 'host/', 'config/', 'contracts/', 'fixtures/', 'vectors/b04_meta/', A_ROOT)):
            rebuilt[name] = entry['sha256']
    receipt = {'status': 'PASS', 'finished_at': now(), 'archive_sha256': digest(archive_path),
               'phase': manifest['phase'], 'target': str(target), 'members': len(manifest['files']) + 1,
               'steps': steps, 'rebuild_input_sha256': rebuilt, 'inputs_unchanged_after_tests': True,
               'results': {'profile': read_json(target / 'reports/b04/fresh_profile.json')['status'],
                           'private': read_json(target / 'reports/b04/fresh_private.json')['unit_checks'],
                           'pc': read_json(target / 'reports/b04/fresh_pc.json')['outputs'],
                           'artifact': read_json(target / 'reports/b04/fresh_artifact_audit/artifact_review.json')['status']},
               'BOARD': 'NOT_TESTED', 'ARM_execution': 'NOT_TESTED',
               'scope': 'Complete offline package extraction, source rebuild, control-only replay, actual ELF/xclbin and original implementation evidence review.'}
    write_json(args.receipt, receipt)
    print('PASS full B04 fresh-directory rebuild and verification', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    create = commands.add_parser('assemble')
    create.add_argument('output')
    create.add_argument('--phase', choices=('trial', 'final'), required=True)
    test = commands.add_parser('extract-test')
    test.add_argument('archive')
    test.add_argument('--target', required=True)
    test.add_argument('--sha256', required=True)
    test.add_argument('--receipt', required=True)
    test.add_argument('--cxx', required=True)
    test.add_argument('--crypto', default='')
    test.add_argument('--readelf', required=True)
    test.add_argument('--xclbinutil', required=True)
    args = parser.parse_args()
    if args.command == 'assemble':
        assemble(args.output, args.phase)
    else:
        extract_and_test(args)
