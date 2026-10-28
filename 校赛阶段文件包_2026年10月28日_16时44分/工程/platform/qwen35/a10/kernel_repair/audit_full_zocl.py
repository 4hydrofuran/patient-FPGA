"""PC ELF/CRC audit for the new release; not a hardware acceptance test."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from audit_zocl_module import sections, compare_versions

RELEASE = '6.8.12-a10irq1'
CONFIG_SHA = '97a9a28a66ae1466f07667b2c75ab2d3dce0c1451cd51923a3c2bc54ccf2aa8b'


def check_info(raw, release=RELEASE):
    rows = raw.decode('ascii').split('\0')
    expected = 'vermagic=' + release + ' SMP preempt mod_unload modversions aarch64'
    if [s for s in rows if s.startswith('vermagic=')] != [expected]:
        raise ValueError('Wrong or duplicate candidate vermagic')
    if [s for s in rows if s.startswith('version=')] != ['version=2.18.0']:
        raise ValueError('Wrong or duplicate XRT version')
    return expected


def audit(module, kernel, release=RELEASE, config_sha=CONFIG_SHA):
    if hashlib.sha256((kernel / '.config').read_bytes()).hexdigest() != config_sha:
        raise ValueError('Candidate config changed')
    if (kernel / 'include/config/kernel.release').read_text().strip() != release:
        raise ValueError('Candidate kernel release changed')
    raw = module.read_bytes()
    sec = sections(raw)
    magic = check_info(sec['.modinfo'], release)
    checks = compare_versions(sec['__versions'], (kernel / 'Module.symvers').read_text())
    return {
        'status': 'PASS_PC_ARM64_ELF_CRC_NOT_BOARD',
        'kernel_release': release, 'vermagic': magic,
        'module_sha256': hashlib.sha256(raw).hexdigest(), 'module_bytes': len(raw),
        'config_sha256': config_sha,
        'symvers_sha256': hashlib.sha256((kernel / 'Module.symvers').read_bytes()).hexdigest(),
        'symbol_crc_count': len(checks), 'symbol_crc_checks': checks,
        'BOARD': 'NOT_TESTED', 'load_authorized': False,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('module', type=Path)
    parser.add_argument('kernel', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.module, args.kernel)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps({k: v for k, v in result.items() if k != 'symbol_crc_checks'}))
