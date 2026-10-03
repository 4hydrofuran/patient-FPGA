"""Check A's future delivery inventory and ARM64 public exports, without signing gates.

The receipt means files are available for integration review. It is not an XRT,
timing, ARM runtime or BOARD acceptance. No A delivery is fabricated by this tool.
"""
import argparse
from pathlib import Path
import re
import struct
import subprocess

from b04_common import ROOT, PUBLIC_SYMBOLS, digest, now, read_json, safe_path, write_json

REQUIRED_ROLES = ('public_header', 'runtime_source', 'build_entry', 'dependency_notes',
                  'xclbin', 'arm64_library', 'arm64_host', 'link_config', 'platform_profile',
                  'implementation_report', 'link_log', 'arm_build_log', 'control_test_receipt')


def elf_header(path, library=False):
    with Path(path).open('rb') as stream:
        header = stream.read(64)
    if len(header) != 64 or header[:7] != b'\x7fELF\x02\x01\x01':
        raise ValueError('Expected ELF64 little-endian version-1 artifact: ' + str(path))
    kind, machine, version = struct.unpack_from('<HHI', header, 16)
    if machine != 183 or version != 1 or kind not in ((3,) if library else (2, 3)):
        raise ValueError('Expected AArch64 dynamic library or executable: ' + str(path))
    # e_ehsize guards a truncated/inconsistent header; body/dependencies need real readelf.
    if struct.unpack_from('<H', header, 52)[0] != 64:
        raise ValueError('ELF header size differs')
    return {'elf_class': 64, 'endianness': 'little', 'machine': machine, 'elf_type': kind}


def public_exports(text):
    found = set()
    for line in text.splitlines():
        fields = line.split()
        if len(fields) >= 8 and fields[0].endswith(':') and fields[3] == 'FUNC' and fields[4] == 'GLOBAL' and fields[5] in ('DEFAULT', 'PROTECTED') and fields[6] != 'UND':
            found.add(fields[7].split('@')[0])
    missing = sorted(set(PUBLIC_SYMBOLS) - found)
    if missing:
        raise ValueError('Missing defined public dynamic functions: ' + ', '.join(missing))
    return PUBLIC_SYMBOLS


def inventory(folder):
    folder = Path(folder).resolve()
    document = folder / 'a_delivery.json'
    if not document.is_file():
        raise ValueError('WAITING_A: a_delivery.json has not been supplied')
    delivery = read_json(document)
    profile = read_json(ROOT / 'config/b04/kernel_profile.json')
    for name, expected in {'public_contract_sha256': profile['public_contract_sha256'],
                           'kernel_build_id': '0xB3030002', 'xo_sha256': profile['xo_sha256']}.items():
        if delivery.get(name) != expected:
            raise ValueError('A delivery identity differs: ' + name)
    if not isinstance(delivery.get('source_revision'), str) or not delivery['source_revision'].strip():
        raise ValueError('A source revision/provenance missing')
    roles = delivery.get('artifacts', {})
    paths = {}
    for role in REQUIRED_ROLES:
        entry = roles.get(role)
        if not isinstance(entry, dict):
            raise ValueError('A delivery role missing: ' + role)
        path = safe_path(folder, entry['path'])
        if not path.is_file() or path.stat().st_size == 0 or digest(path) != entry['sha256'].lower():
            raise ValueError('A artifact absent/empty/hash differs: ' + role)
        paths[role] = path
    if digest(paths['public_header']) != digest(ROOT / 'contracts/sp_linear_v1.h'):
        raise ValueError('A public header differs from frozen B contract')
    return delivery, paths


def inspect(folder, readelf, receipt):
    delivery, paths = inventory(folder)
    checked = {'library': elf_header(paths['arm64_library'], True), 'host': elf_header(paths['arm64_host'])}
    steps = {}
    for role in ('arm64_library', 'arm64_host'):
        # Run against actual file; copied human text is not accepted as readelf evidence.
        results = {}
        for option in ('--file-header', '--dynamic', '--dyn-syms'):
            result = subprocess.run([readelf, option, '--wide', str(paths[role])], capture_output=True,
                                    text=True, timeout=30)
            if result.returncode:
                raise ValueError('Actual readelf rejected artifact: ' + role)
            results[option] = result.stdout
        if role == 'arm64_library':
            checked['public_exports'] = public_exports(results['--dyn-syms'])
        checked[role + '_needed'] = re.findall(r'Shared library: \[(.*?)\]', results['--dynamic'])
        steps[role] = {'tool': readelf, 'actual_file_sha256': digest(paths[role]), 'readelf_outputs': results}
    report = {'status': 'AVAILABLE_FOR_INTEGRATION_REVIEW', 'finished_at': now(),
              'source_revision': delivery['source_revision'], 'a_manifest_sha256': digest(Path(folder) / 'a_delivery.json'),
              'identity': {key: delivery[key] for key in ('public_contract_sha256', 'kernel_build_id', 'xo_sha256')},
              'artifacts': delivery['artifacts'], 'binary_checks': checked, 'steps': steps,
              'scope': 'Inventory/hash/real ELF and exported functions only. xclbin metadata, timing, runtime behavior and original logs still require joint review.',
              'joint_G1_G6': 'NOT_ACCEPTED_BY_PREFLIGHT', 'BOARD': 'NOT_TESTED'}
    write_json(receipt, report)
    print('A artifacts available for integration review; full B04 gates remain unsigned')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder')
    parser.add_argument('--readelf', default='aarch64-linux-gnu-readelf')
    parser.add_argument('--receipt', required=True)
    args = parser.parse_args()
    inspect(args.folder, args.readelf, args.receipt)
