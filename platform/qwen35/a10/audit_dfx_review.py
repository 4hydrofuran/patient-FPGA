"""PC source/archive correspondence only; does not establish deployed compatibility."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tarfile


def sha(data):
    return hashlib.sha256(data).hexdigest()


def audit(root):
    cache = root / 'platform/local/a10-dfx-review-20261019'
    evidence = root / 'evidence/board_platform/A10_20261018_intake'
    archives, repositories = [], []
    for dsc in sorted(cache.glob('*.dsc')):
        data = dsc.read_bytes()
        text = data.decode()
        part = text.split('Checksums-Sha256:\n', 1)[1].split('\nFiles:', 1)[0]
        members = []
        for line in part.splitlines():
            match = re.fullmatch(r' ([0-9a-f]{64}) +(\d+) +([^/\\ ]+)', line)
            if not match:
                continue
            h, size, name = match.groups()
            payload = (cache / name).read_bytes()
            if sha(payload) != h or len(payload) != int(size):
                raise ValueError('DSC member differs: ' + name)
            members.append(dict(name=name, sha256=h, bytes=int(size)))
        if len(members) != 2:
            raise ValueError('Expected orig and Debian patch archives')
        archives.append(dict(dsc=dsc.name, sha256=sha(data), members=members,
                             signature_verified=False, usage='READONLY_REVIEW_NOT_INSTALL'))
    for repo, commit in [('dfx-mgr', '839e8e646c54a63326e36c48a7bd879f5e8efa31'),
                         ('libdfx', 'af8d735fae286e7bc94c830a86c960598a4ac014')]:
        actual = subprocess.check_output(['git', '-C', str(cache / repo), 'rev-parse', 'HEAD'], text=True).strip()
        if actual != commit:
            raise ValueError('Unexpected upstream commit')
        repositories.append(dict(repository='https://github.com/Xilinx/' + repo, commit=actual))
    actual_lib = (cache / 'board-libdfx.so.1.0').read_bytes()
    inv = json.loads((evidence / 'ssh_dfx_recovery_inventory_01.json').read_text(encoding='utf-8-sig'))
    if sha(actual_lib) != inv['files']['/usr/lib/aarch64-linux-gnu/libdfx.so.1.0']['sha256']:
        raise ValueError('Board library copy hash mismatch')
    with tarfile.open(cache / 'libdfx_2024.2.0.orig.tar.gz') as archive:
        names = [n for n in archive.getnames() if n.endswith('/src/libdfx.c')]
        if len(names) != 1:
            raise ValueError('Ambiguous source member')
        original = archive.extractfile(names[0]).read()
    upstream = (cache / 'libdfx/src/libdfx.c').read_bytes().replace(b'\r\n', b'\n')
    disassembly = evidence / 'libdfx_actual_remove_disassembly_v1.json'
    result = json.loads(disassembly.read_text(encoding='utf-8'))
    if result['exit_code'] != 0 or '<dfx_cfg_remove@@libdfx.so.1.0>:' not in result['stdout']:
        raise ValueError('Actual symbol disassembly missing')
    return dict(domain='PC_SOURCE_REVIEW', archives=archives, repositories=repositories,
                libdfx_orig_matches_upstream_source=original.replace(b'\r\n', b'\n') == upstream,
                deployed_library_sha256=sha(actual_lib), deployed_library_bytes=len(actual_lib),
                deployed_libdfx_package='2024.2.0-0ubuntu1~xlnx1',
                downloaded_libdfx_source_version='2024.2.0-0ubuntu1~24.04.1~xlnx1',
                exact_deployed_libdfx_source_package_verified=False,
                disassembly_evidence_sha256=sha(disassembly.read_bytes()),
                remove_implementation_review='actual library ignores system() return before setting w0=0; see manual addresses in report',
                gate='EXIT_CODE_ALONE_FORBIDDEN_REQUIRE_INDEPENDENT_READBACK',
                PL='NOT_TESTED', authorization=False)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    result = audit(a.root.resolve())
    with a.output.open('x', encoding='utf-8') as f:
        json.dump(result, f, indent=2)
        f.write('\n')
    print('PASS_PC_DIGEST_REVIEW_ONLY_NO_BOARD_EXECUTION')
