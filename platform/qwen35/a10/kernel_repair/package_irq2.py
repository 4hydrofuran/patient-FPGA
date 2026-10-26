"""Build matched irq2 ZOCL, stage and audit modules, package exact-backup FIT.

PC only. Secrets remain in the private build directory; archives contain only
explicit modules, public boot artifacts and preserved original initramfs data.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
sys.dont_write_bytecode = True
from audit_full_zocl import audit as audit_zocl
from audit_module_stage import audit as audit_modules
from prepare_boot_candidate import build as pack_boot
from audit_boot_candidate import audit as audit_boot

ROOT = Path('/mnt/c/Patientqwen')
WORK = Path('/home/member-a/a10-kernel-irq2-20261021-v1')
OLD = Path('/home/member-a/a10-kernel-full-20261019-v1')
RELEASE = '6.8.12-a10irq2'
TOOLS = Path(__file__).parent


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def run(cmd, cwd=None):
    print(json.dumps(dict(argv=cmd, cwd=str(cwd) if cwd else None)), flush=True)
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    with (WORK / 'package-commands.jsonl').open('a') as f:
        f.write(json.dumps(dict(argv=cmd, cwd=str(cwd) if cwd else None,
                               exit_code=result.returncode, stdout=result.stdout,
                               stderr=result.stderr)) + '\n')
    if result.returncode:
        print(result.stdout[-5000:])
        print(result.stderr[-5000:])
        raise RuntimeError('PC packaging step failed; preserve outputs')
    return result


def save(name, value):
    with (WORK / name).open('x') as f:
        json.dump(value, f, indent=2)


def config_difference(old, new):
    a, b = set(old.splitlines()), set(new.splitlines())
    changed = (a - b) | (b - a)
    allowed = ('CONFIG_LOCALVERSION=', 'CONFIG_VERSION_SIGNATURE=')
    if not changed or any(not line.startswith(allowed) for line in changed):
        raise ValueError('Unexpected config difference')
    if 'CONFIG_LOCALVERSION="-a10irq2"' not in b:
        raise ValueError('Wrong independent release')
    return sorted(changed)


def validate_build_receipt(receipt, image_sha):
    expected = ['/mnt/c/Patientqwen/platform/qwen35/a10/kernel_repair/build_irq2.sh', 'resume1']
    if receipt.get('exit_code') != 0 or receipt.get('argv', [])[-2:] != expected:
        raise RuntimeError('successful irq2 resume build receipt required')
    output = receipt.get('stdout', '')
    if 'PC_FULL_KERNEL_ONLY_NOT_BOARD_NOT_DEPLOYED' not in output:
        raise RuntimeError('full kernel completion marker missing')
    image_line = image_sha + '  ' + str(WORK / 'build/arch/arm64/boot/Image')
    if image_line not in output.splitlines():
        raise RuntimeError('Image differs from completed build receipt')


def main():
    if os.uname().machine != 'x86_64':
        raise RuntimeError('PC only')
    receipt = ROOT / 'evidence/board_platform/A10_20261018_intake/irq2_build_20261021_03.json'
    validate_build_receipt(json.loads(receipt.read_text()), sha(WORK / 'build/arch/arm64/boot/Image'))
    config = WORK / 'build/.config'
    diff = config_difference((OLD / 'build/.config').read_text(), config.read_text())
    if (WORK / 'build/include/config/kernel.release').read_text().strip() != RELEASE:
        raise RuntimeError('Wrong built release')
    cfgsha = sha(config)
    save('package-inputs.json', dict(release=RELEASE, config_sha256=cfgsha, config_diff=diff,
         image_sha256=sha(WORK / 'build/arch/arm64/boot/Image'), board_access=False))
    package = ROOT / 'platform/local/a10-xrt-2.18-audit/xrt-dkms_2.18.0-0ubuntu1_arm64.deb'
    if sha(package) != '096cb3c25a2f6885bfc615746aba0cdcd74075b724207f0e02ba3dc05ba54297':
        raise RuntimeError('XRT package differs')
    zsrc = WORK / 'zocl-source-v1'
    zsrc.mkdir(mode=0o700)
    run(['dpkg-deb', '-x', str(package), str(zsrc)])
    driver = zsrc / 'usr/src/xrt-2.18.0/driver/zocl'
    run(['python3', str(TOOLS / 'apply_driver_candidate.py'), '--bundle',
         str(ROOT / 'platform/build/a10-driver-irq-repair-20261019-v1'), '--source', str(driver)])
    run(['make', '-j2', 'KERNEL_SRC=' + str(WORK / 'build'), 'ARCH=arm64',
         'CROSS_COMPILE=aarch64-amd-linux-', 'CC=aarch64-amd-linux-gcc', 'HOSTCC=/usr/bin/gcc',
         'PAHOLE=' + str(WORK / 'deps/root/usr/bin/pahole'), 'GIT_HASH=debian-xrt-2.18.0-0ubuntu1',
         'GIT_HASH_DATE=package-source', 'GIT_BRANCH=A10-irq2', 'GIT_MODIFIED_FILES=common/cu.c,zert/zocl_xgq_intc.c',
         'DATE_NOW=2026-10-21', 'modules'], driver)
    save('zocl-audit-v1.json', audit_zocl(driver / 'zocl.ko', WORK / 'build', RELEASE, cfgsha))
    stage = WORK / 'module-stage-v2'
    stage.mkdir(mode=0o700)
    deps = WORK / 'deps/root'
    args = ['make', '-C', str(WORK / 'source'), 'O=' + str(WORK / 'build'),
            'ARCH=arm64', 'CROSS_COMPILE=aarch64-amd-linux-', 'CC=aarch64-amd-linux-gcc',
            'HOSTCC=/usr/bin/gcc', 'HOSTCXX=/usr/bin/g++',
            'HOSTCFLAGS=-I' + str(deps / 'usr/include') + ' -I' + str(deps / 'usr/include/x86_64-linux-gnu'),
            'HOSTLDFLAGS=-L' + str(deps / 'usr/lib/x86_64-linux-gnu') + ' -Wl,-rpath,' + str(deps / 'usr/lib/x86_64-linux-gnu'),
            'HOSTPKG_CONFIG=env PKG_CONFIG_SYSROOT_DIR=' + str(deps) +
            ' PKG_CONFIG_LIBDIR=' + str(deps / 'usr/lib/x86_64-linux-gnu/pkgconfig') + ' /usr/bin/pkg-config',
            'PAHOLE=' + str(deps / 'usr/bin/pahole'),
            '-j4', 'INSTALL_MOD_PATH=' + str(stage),
            'INSTALL_MOD_STRIP=1', 'DEPMOD=/usr/sbin/depmod', 'modules_install']
    run(args)
    target = stage / 'lib/modules' / RELEASE / 'extra'
    target.mkdir()
    (target / 'zocl.ko').write_bytes((driver / 'zocl.ko').read_bytes())
    run(['aarch64-amd-linux-strip', '--strip-debug', str(target / 'zocl.ko')])
    # Do not log private key bytes or distribute key files.
    run([str(WORK / 'build/scripts/sign-file'), 'sha512',
         str(WORK / 'build/certs/signing_key.pem'), str(WORK / 'build/certs/signing_key.x509'),
         str(target / 'zocl.ko')])
    run(['/usr/sbin/depmod', '-b', str(stage), RELEASE])
    save('zocl-staged-audit-v2.json', audit_zocl(target / 'zocl.ko', WORK / 'build', RELEASE, cfgsha))
    save('module-stage-audit-v2.json',
         audit_modules(stage, WORK / 'build', WORK / 'source', RELEASE, cfgsha))
    (WORK / 'original-boot-v2').symlink_to(OLD / 'original-boot-v2', target_is_directory=True)
    image_sha = sha(WORK / 'build/arch/arm64/boot/Image')
    pack_boot(WORK, RELEASE, image_sha)
    result = audit_boot(WORK, RELEASE, image_sha)
    save('boot-readback-irq2.json', result)
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
