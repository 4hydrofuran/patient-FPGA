"""Offline digest checks for downloaded archive inputs; signature checks are separate."""
import argparse
import gzip
import hashlib
import json
import lzma
from pathlib import Path
import re


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_index(release, index, member):
    text = release.read_text()
    sha_section = text.split('\nSHA256:\n', 1)[1].split('\nSHA512:', 1)[0]
    match = re.search(r'^ ([0-9a-f]{64})\s+(\d+)\s+' + re.escape(member) + r'$', sha_section, re.M)
    if not match or digest(index) != match[1] or index.stat().st_size != int(match[2]):
        raise ValueError('Index hash/length does not match signed release content')


def check_package(index_text, package, version, path):
    candidates = []
    for stanza in index_text.split('\n\n'):
        fields = dict(line.split(': ', 1) for line in stanza.splitlines() if ': ' in line and not line.startswith(' '))
        if fields.get('Package') == package and fields.get('Version') == version:
            candidates.append(fields)
    if len(candidates) != 1:
        raise ValueError('Expected exactly one package/version')
    fields = candidates[0]
    if digest(path) != fields['SHA256'] or path.stat().st_size != int(fields['Size']):
        raise ValueError('Package hash/length mismatch')
    return {key: fields[key] for key in ('Package', 'Version', 'Architecture', 'Filename', 'Size', 'SHA256')}


def verify(cache):
    check_index(cache/'headers.InRelease', cache/'headers.Packages.xz', 'universe/binary-arm64/Packages.xz')
    check_index(cache/'sdk.InRelease', cache/'sdk.Packages.gz', 'main/binary-arm64/Packages.gz')
    headers = lzma.decompress((cache/'headers.Packages.xz').read_bytes()).decode()
    sdk = gzip.decompress((cache/'sdk.Packages.gz').read_bytes()).decode()
    entries = [check_package(headers, 'linux-headers-6.8.0-1015-xilinx', '6.8.0-1015.16', cache/'headers-arm64.deb'),
               check_package(headers, 'linux-xilinx-headers-6.8.0-1015', '6.8.0-1015.16', cache/'headers-all.deb'),
               check_package(sdk, 'xrt-dkms', '2.18.0-0ubuntu1', cache/'xrt-dkms_2.18.0-0ubuntu1_arm64.deb')]
    return {'domain': 'PC_ARTIFACT_INTEGRITY', 'digest_status': 'PASS', 'packages': entries,
            'signature_validation': 'See separate gpgv logs; this script only checks SHA256/size chains',
            'board_install': 'NOT_PERFORMED'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.cache)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps(result))
