"""PC-only staged-module integrity/signature audit. No loading or installation."""
import argparse
import hashlib
import json
from pathlib import Path
import stat
import struct
import subprocess
import tempfile

from audit_full_zocl import CONFIG_SHA, RELEASE, sections, compare_versions

MARKER = b'~Module signature appended~\n'
MAGIC = 'vermagic=' + RELEASE + ' SMP preempt mod_unload modversions aarch64'


def split_signature(raw):
    if not raw.endswith(MARKER):
        return raw, None
    end = len(raw) - len(MARKER)
    if end < 12:
        raise ValueError('Truncated signature descriptor')
    descriptor = raw[end-12:end]
    if descriptor[:8] != bytes([0, 0, 2, 0, 0, 0, 0, 0]):
        raise ValueError('Unsupported signature descriptor')
    size = struct.unpack('>I', descriptor[8:])[0]
    if not 0 < size < end - 12:
        raise ValueError('Invalid signature size')
    return raw[:end-12-size], raw[end-12-size:end-12]


def required_signature(relative, inclusion):
    return '/drivers/staging/' not in '/' + relative or Path(relative).name in inclusion


def module_paths(root):
    # Do not follow Kbuild's build/source links into the source or private keys.
    paths, excluded = [], []
    def walk(directory):
        for p in sorted(directory.iterdir()):
            rel = p.relative_to(root).as_posix()
            mode = p.lstat().st_mode
            if stat.S_ISLNK(mode):
                if rel not in ('build', 'source'):
                    raise ValueError('Unexpected module-tree symlink: ' + rel)
                excluded.append(rel)
            elif stat.S_ISDIR(mode):
                walk(p)
            elif stat.S_ISREG(mode):
                if p.suffix == '.ko':
                    paths.append(p)
                elif '/' in rel or not rel.startswith('modules.'):
                    raise ValueError('Unexpected staged file: ' + rel)
            else:
                raise ValueError('Special staged file: ' + rel)
    if root.is_symlink() or not root.is_dir():
        raise ValueError('Expected real module directory')
    walk(root)
    if not paths:
        raise ValueError('Empty module stage')
    return paths, excluded


def audit(stage, kernel, source, release=RELEASE, config_sha=CONFIG_SHA):
    magic = 'vermagic=' + release + ' SMP preempt mod_unload modversions aarch64'
    if hashlib.sha256((kernel / '.config').read_bytes()).hexdigest() != config_sha:
        raise ValueError('Kernel config changed')
    root = stage / 'lib/modules' / release
    if sorted(p.name for p in root.parent.iterdir()) != [release]:
        raise ValueError('Unexpected module release')
    paths, excluded = module_paths(root)
    inclusion = set()
    for folder in ('debian', 'debian.xilinx'):
        p = source / folder / 'signature-inclusion'
        if p.exists():
            inclusion.update(p.read_text().splitlines())
    symvers = (kernel / 'Module.symvers').read_text()
    rows = []
    with tempfile.TemporaryDirectory(prefix='a10-signature-audit-') as tmp:
        tmp = Path(tmp)
        cert = tmp / 'public.pem'
        subprocess.run(['openssl', 'x509', '-inform', 'DER', '-in', str(kernel / 'certs/signing_key.x509'),
                        '-out', str(cert)], check=True, capture_output=True)
        for p in paths:
            rel = p.relative_to(root).as_posix()
            raw = p.read_bytes()
            content, signature = split_signature(raw)
            if required_signature(rel, inclusion) and signature is None:
                raise ValueError('Required signature absent: ' + rel)
            sec = sections(content)
            if [x for x in sec['.modinfo'].decode().split('\0') if x.startswith('vermagic=')] != [magic]:
                raise ValueError('Wrong module vermagic: ' + rel)
            crcs = compare_versions(sec['__versions'], symvers)
            if signature is not None:
                (tmp / 'module').write_bytes(content)
                (tmp / 'signature').write_bytes(signature)
                result = subprocess.run(['openssl', 'cms', '-verify', '-binary', '-inform', 'DER',
                    '-in', str(tmp/'signature'), '-content', str(tmp/'module'), '-certfile', str(cert),
                    '-nointern', '-noverify', '-out', '/dev/null'], capture_output=True)
                if result.returncode:
                    raise ValueError('Cryptographic signature verification failed: ' + rel)
            rows.append({'path': rel, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(),
                         'symbol_crc_count': len(crcs), 'signature_verified_with_candidate_cert': signature is not None})
    return {'status': 'PASS_PC_STAGED_MODULES_NOT_BOARD', 'release': release,
            'modules': len(rows), 'signed_verified': sum(r['signature_verified_with_candidate_cert'] for r in rows),
            'excluded_links': excluded, 'files': rows, 'BOARD': 'NOT_TESTED',
            'certificate_trust_on_board': 'NOT_VERIFIED', 'deployment_authorized': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('stage', 'kernel', 'source', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    with args.output.open('x') as stream:
        json.dump({'status': 'RESERVED_NOT_COMPLETED'}, stream)
        stream.flush()
        result = audit(args.stage, args.kernel, args.source)
        stream.seek(0)
        json.dump(result, stream, indent=2)
        stream.truncate()
    print(json.dumps({k: v for k, v in result.items() if k != 'files'}))
