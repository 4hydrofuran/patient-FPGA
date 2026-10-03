"""Export small, host-friendly A adapter cases from hash-checked original RTL.

Independent expected bytes are copied from B03 dense golden evidence. This tool
never calls the kernel or B04 checker to generate an expectation.
"""
import argparse
from pathlib import Path
import struct

from b04_common import ROOT, META_GROUPS, digest, now, read_json, safe_path, text_tv, write_json


def export(output, receipt):
    output = safe_path(ROOT, output)
    if output.exists():
        raise FileExistsError('Preserve exported cases; use a fresh directory')
    sources = {}
    cases = []
    for group in META_GROUPS:
        original = ROOT / 'evidence/b03/batches/double' / group
        original_manifest = read_json(original / 'manifest.json')
        parameters = ('gmem_meta', 'meta', 'meta_bytes', 'job_id', 't', 'n', 'k')
        names = ['tv/cdatafile/c.w4a8_linear_v1.autotvin_' + name + '.dat' for name in parameters]
        names.append('tv/rtldatafile/rtl.w4a8_linear_v1.autotvout_gmem_meta.dat')
        records = {}
        for name in names:
            path = original / name
            entry = original_manifest['files'][name]
            if digest(path) != entry['sha256'] or path.stat().st_size != entry['bytes']:
                raise ValueError('Original RTL digest differs: ' + str(path))
            sources[path.relative_to(ROOT).as_posix()] = entry
            records[name] = text_tv(path)
        ids = set(map(int, original_manifest['cases']))
        if any(set(rows) != ids for rows in records.values()):
            raise ValueError('Original scalar/meta call set differs')
        scalar = {name: records['tv/cdatafile/c.w4a8_linear_v1.autotvin_' + name + '.dat'] for name in parameters}
        actual = records[names[-1]]
        for transaction in sorted(ids):
            offset = scalar['meta'][transaction]
            if offset > 24:
                raise ValueError('Private record exceeds actual bus word')
            before = scalar['gmem_meta'][transaction].to_bytes(64, 'little')[offset:offset + 40]
            wire = actual[transaction].to_bytes(64, 'little')[offset:offset + 40]
            expected_path = ROOT / 'evidence/b03/supplement/rtl_expected' / group / str(transaction) / 'expected_meta.bin'
            expected = expected_path.read_bytes()
            if wire != expected or len(expected) != 40:
                raise ValueError('Observed RTL meta differs from independent B03 expected')
            sources[expected_path.relative_to(ROOT).as_posix()] = {'bytes': 40, 'sha256': digest(expected_path)}
            target = output / group / str(transaction)
            target.mkdir(parents=True, exist_ok=False)
            files = {}
            for name, data in (('before.bin', before), ('actual.bin', wire), ('expected.bin', expected)):
                path = target / name
                path.write_bytes(data)
                files[name] = {'path': path.relative_to(output).as_posix(), 'bytes': len(data), 'sha256': digest(path)}
            t, n, k = (scalar[name][transaction] for name in ('t', 'n', 'k'))
            weight = ((n + 31) // 32 * 32) * ((k + 127) // 128 * 128) // 2 if 1 <= n <= 4864 and 1 <= k <= 4864 else 0
            cases.append({'id': group + '/' + str(transaction), 'case': original_manifest['cases'][str(transaction)]['case'],
                          'T': t, 'N': n, 'K': k, 'job_id': scalar['job_id'][transaction],
                          'meta_bytes_argument': scalar['meta_bytes'][transaction],
                          'completion_bytes_to_inspect': min(40, scalar['meta_bytes'][transaction]),
                          'previous_count': struct.unpack_from('<Q', before, 24)[0],
                          'dimension_weight_bytes': weight, 'original_meta_bus_offset': offset,
                          'expected_private_status': struct.unpack_from('<I', expected, 16)[0], 'files': files})
    manifest = {'schema_version': 1, 'kernel_build_id': '0xB3030002', 'record_bytes': 40,
                'endianness': 'little', 'transactions': len(cases), 'cases': cases, 'original_sources': sources,
                'scope': 'Actual archived RTL bytes and independently generated B03 expected bytes; no new RTL/BOARD/runtime test.'}
    write_json(output / 'manifest.json', manifest)
    write_json(receipt, {'status': 'PASS', 'finished_at': now(), 'transactions': len(cases),
                         'manifest_sha256': digest(output / 'manifest.json'),
                         'input_sha256': {name: digest(ROOT / name) for name in ('tools/b04_export_meta.py', 'tools/b04_common.py')},
                         'scope': manifest['scope']})
    print('PASS B04 host-friendly meta cases exported=' + str(len(cases)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='vectors/b04_meta')
    parser.add_argument('--receipt', default='reports/b04/export_meta.receipt.json')
    args = parser.parse_args()
    export(args.output, ROOT / args.receipt)
