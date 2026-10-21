"""Reject corrupted, incomplete or falsely promoted complete candidate packages."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import stat
import sys
import tempfile
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from b04_candidate import A_ROOT, RECEIPTS, validate_manifest, verify_archive
from b04_common import ROOT, now, write_json
from b04_stage import member_name


def main(args):
    checks = []

    def reject(name, operation):
        try:
            operation()
        except (ValueError, KeyError, FileNotFoundError):
            checks.append({'case': name, 'status': 'REJECTED_AS_EXPECTED'})
        else:
            raise AssertionError('Invalid candidate accepted: ' + name)

    for name in ('../escape', '/absolute', 'C:/outside', 'a\\..\\b', 'a/../b',
                 'a//b', './b', 'a/NUL.txt', 'a/trailing.', 'a/trailing ', ''):
        reject('unsafe path ' + repr(name), lambda name=name: member_name(name))
    manifest = verify_archive(args.archive, None)
    checks.append({'case': 'actual complete candidate inventory and receipts', 'status': 'PASS'})
    reject('wrong externally supplied archive hash', lambda: verify_archive(args.archive, '0' * 64))
    with zipfile.ZipFile(args.archive) as archive:
        original = {name: archive.read(name) for name in archive.namelist() if name != 'manifest.json'}

    def altered(label, change):
        changed = copy.deepcopy(manifest)
        payload = dict(original)

        def reseal(name, value):
            raw = json.dumps(value).encode('utf-8')
            payload[name] = raw
            changed['files'][name] = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}

        change(changed, payload, reseal)
        reject(label, lambda: validate_manifest(changed, payload.__getitem__, [*payload, 'manifest.json']))

    altered('fabricated BOARD pass', lambda m, p, s: m.update(BOARD='PASS'))
    altered('corrupted xclbin bytes', lambda m, p, s: p.update({A_ROOT + 'artifacts/w4a8.xclbin': b'corrupt'}))
    altered('missing required shared library', lambda m, p, s: p.pop(A_ROOT + 'artifacts/libsp_linear_xrt_candidate.so'))
    altered('incomplete A source closure', lambda m, p, s: (p.pop(A_ROOT + 'source_manifest.json'), m['files'].pop(A_ROOT + 'source_manifest.json')))

    def fake_coverage(m, p, seal):
        receipt = json.loads(p[RECEIPTS + 'pc.json'])
        receipt['outputs']['control']['checks'] = 0
        seal(RECEIPTS + 'pc.json', receipt)
    altered('PASS label with zero control coverage', fake_coverage)

    def stale_source(m, p, seal):
        name = 'tests/b04/native/sys/file.h'
        raw = p[name] + b'\n// changed after validation\n'
        p[name] = raw
        m['files'][name] = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
    altered('source changed after PC receipt', stale_source)

    def fake_profile(m, p, seal):
        profile = json.loads(p['config/b04/kernel_profile.json'])
        profile['build_id'] = 1
        seal('config/b04/kernel_profile.json', profile)
    altered('wrong kernel identity with resealed file hash', fake_profile)

    def fake_private(m, p, seal):
        receipt = json.loads(p[RECEIPTS + 'private.json'])
        receipt['archived_rtl_meta_transactions'] = 0
        seal(RECEIPTS + 'private.json', receipt)
    altered('missing archived RTL probe coverage', fake_private)

    def premature_final(m, p, seal):
        m['phase'] = 'final'
        name = RECEIPTS + 'trial_extraction.json'
        p.pop(name, None)
        m['files'].pop(name, None)
    altered('formal promotion without fresh rebuild receipt', premature_final)

    temporary = ROOT / 'build/b04/candidate_negative'
    temporary.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='archive_', dir=temporary) as value:
        folder = Path(value).resolve()
        if folder.parent != temporary.resolve():
            raise ValueError('Temporary test path escaped workspace')
        path = folder / 'symlink.zip'
        info = zipfile.ZipInfo('manifest.json')
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr(info, '{}')
        reject('symlink ZIP member', lambda: verify_archive(path, None))
        path = folder / 'collision.zip'
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('manifest.json', '{}')
            archive.writestr('MANIFEST.json', '{}')
        reject('case-colliding ZIP names', lambda: verify_archive(path, None))
    report = {'status': 'PASS', 'finished_at': now(), 'checks': checks,
              'count': len(checks), 'scope': 'Candidate corruption/incomplete/false acceptance rejection; no device execution.'}
    write_json(args.receipt, report)
    print('PASS complete candidate rejection checks:', len(checks))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', required=True)
    parser.add_argument('--receipt', required=True)
    main(parser.parse_args())
