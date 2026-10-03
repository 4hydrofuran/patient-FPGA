"""Negative delivery checks: no fake A completion, unsafe extraction or wrong ABI accepted."""
import json
import argparse
import hashlib
from pathlib import Path
import struct
import sys
import tempfile
import zipfile
import warnings

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from b04_a_preflight import elf_header, inventory, public_exports
from b04_common import PUBLIC_SYMBOLS, digest, now, write_json
from b04_stage import member_name, verify_archive


def main(receipt, real_archive=None):
    checks = []
    def reject(label, operation):
        try:
            operation()
        except (ValueError, KeyError, FileNotFoundError):
            checks.append({'case': label, 'status': 'REJECTED_AS_EXPECTED'})
        else:
            raise AssertionError('Accepted forbidden case: ' + label)
    for name in ('../escape', '/absolute', 'C:/outside', 'a\\..\\outside', 'a/../outside',
                 'a//b', './b', 'a/NUL.txt', 'a/trailing.', 'a/trailing ', ''):
        reject('unsafe ZIP name ' + repr(name), lambda name=name: member_name(name))
    member_name('docs/b04/KERNEL_ADAPTER.md')
    checks.append({'case': 'valid portable relative name', 'status': 'PASS'})
    temporary_root = Path(__file__).resolve().parents[2] / 'build/b04/negative_temporary'
    temporary_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='b04_negative_', dir=temporary_root) as temporary:
        folder = Path(temporary)
        if folder.resolve().parent != temporary_root.resolve():
            raise ValueError('Temporary cleanup target escaped intended test directory')
        reject('no A delivery', lambda: inventory(folder))
        (folder / 'a_delivery.json').write_text('{}', encoding='utf-8')
        reject('empty A identity', lambda: inventory(folder))
        data = bytearray(64)
        data[:7] = b'\x7fELF\x02\x01\x01'
        struct.pack_into('<HHI', data, 16, 3, 183, 1)
        struct.pack_into('<H', data, 52, 64)
        binary = folder / 'synthetic_header.bin'
        binary.write_bytes(data)
        elf_header(binary, True)
        checks.append({'case': 'synthetic ARM64 header only; never a runtime result', 'status': 'PASS'})
        changed = bytearray(data)
        struct.pack_into('<H', changed, 18, 62)
        binary.write_bytes(changed)
        reject('x86 library instead of ARM64', lambda: elf_header(binary, True))
        binary.write_bytes(data[:30])
        reject('truncated ELF header', lambda: elf_header(binary, True))
        changed = bytearray(data)
        changed[5] = 2
        binary.write_bytes(changed)
        reject('big-endian ELF', lambda: elf_header(binary, True))
        for title, names in (('duplicate names', ('manifest.json', 'manifest.json')),
                             ('case collision', ('manifest.json', 'MANIFEST.json')),
                             ('escaping member', ('manifest.json', '../outside'))):
            archive = folder / (title.replace(' ', '_') + '.zip')
            with warnings.catch_warnings():
                warnings.filterwarnings('ignore', message="Duplicate name: 'manifest.json'", category=UserWarning)
                with zipfile.ZipFile(archive, 'w') as output:
                    for name in names:
                        output.writestr(name, '{}')
            reject(title, lambda archive=archive: verify_archive(archive))
        archive = folder / 'false_complete.zip'
        with zipfile.ZipFile(archive, 'w') as output:
            output.writestr('manifest.json', json.dumps({'package_kind': 'B04_B_STAGE_PARTIAL', 'full_B04_accepted': True}))
        reject('false full acceptance', lambda: verify_archive(archive))
        if real_archive:
            verify_archive(real_archive)
            with zipfile.ZipFile(real_archive) as source:
                payload = {name: source.read(name) for name in source.namelist()}
            reject('wrong outer trusted ZIP SHA', lambda: verify_archive(real_archive, '0' * 64))
            for label in ('changed payload', 'deleted required header', 'deleted original scalar', 'changed frozen XO'):
                altered = dict(payload)
                manifest = json.loads(altered['manifest.json'])
                if label == 'changed payload':
                    altered['fixtures/expected_y.bin'] += b'wrong'
                elif label.startswith('deleted'):
                    name = ('contracts/sp_linear_v1.h' if label == 'deleted required header' else
                            'evidence/b03/batches/double/smoke/tv/cdatafile/c.w4a8_linear_v1.autotvin_job_id.dat')
                    del altered[name]
                    del manifest['files'][name]
                else:
                    name = 'artifact/b03_candidate/w4a8_linear_v1.xo'
                    altered[name] += b'changed'
                    manifest['files'][name] = {'bytes': len(altered[name]), 'sha256': hashlib.sha256(altered[name]).hexdigest()}
                altered['manifest.json'] = json.dumps(manifest).encode('utf-8')
                archive = folder / (label.replace(' ', '_') + '.zip')
                with zipfile.ZipFile(archive, 'w') as output:
                    for name, data in altered.items():
                        output.writestr(name, data)
                reject(label, lambda archive=archive: verify_archive(archive))
    symbols = '\n'.join('1: 0001 12 FUNC GLOBAL DEFAULT 12 ' + name for name in PUBLIC_SYMBOLS)
    public_exports(symbols)
    checks.append({'case': 'synthetic six defined exports; no A runtime claim', 'status': 'PASS'})
    reject('undefined public exports', lambda: public_exports(symbols.replace('DEFAULT 12', 'DEFAULT UND')))
    reject('missing close', lambda: public_exports('\n'.join(symbols.splitlines()[:-1])))
    reject('hidden public exports', lambda: public_exports(symbols.replace('DEFAULT', 'HIDDEN')))
    write_json(receipt, {'status': 'PASS', 'finished_at': now(), 'checks': len(checks), 'cases': checks,
                         'input_sha256': {name: digest(Path(__file__).resolve().parents[2] / name)
                                          for name in ('tests/b04/packaging_checks.py', 'tools/b04_stage.py', 'tools/b04_a_preflight.py')},
                         'actual_archive_sha256': digest(real_archive) if real_archive else None,
                         'scope': 'Synthetic malformed inputs and inventory rejection; not a public runtime, ARM build or BOARD test.'})
    print('PASS B04 delivery rejection checks=' + str(len(checks)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('receipt')
    parser.add_argument('--archive', help='Add malformed copies of an actual stage package')
    args = parser.parse_args()
    main(Path(args.receipt), args.archive)
