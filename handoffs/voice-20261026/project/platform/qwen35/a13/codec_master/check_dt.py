"""编译和合并新disabled DT的本地副本，核对真实irq2备份与关键保护字段。"""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[4]
E = ROOT / 'evidence/a13_A/20261025-audio-codec-master-v1'
K = Path('/home/member-a/a10-kernel-irq2-20261021-v1')
GET = '/home/member-a/AMDDesignTools/2026.1/gnu/armr5/lin/gcc-arm-none-eabi/x86_64-oesdk-linux/usr/bin/fdtget'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    out = E / 'dt-verified'
    out.mkdir(exist_ok=False)
    commands = []

    def run(argv):
        result = subprocess.run(list(map(str, argv)), capture_output=True, text=True)
        commands.append({'argv': list(map(str, argv)), 'exit_code': result.returncode,
                         'stdout': result.stdout, 'stderr': result.stderr})
        (out / 'commands.json').write_text(json.dumps(commands, indent=2) + '\n')
        assert result.returncode == 0 and not result.stderr.strip(), commands[-1]
        return result.stdout.strip()

    base = out / 'base-original-irq2.dtb'
    original = K / 'original-boot-v2/kv260-revB.dtb'
    old_base = E.parent / '20261024-audio-pl-build-v2/dt-v2/base-irq2-boot.dtb'
    assert sha(original) == sha(old_base)
    shutil.copyfile(original, base)
    source = Path(__file__).resolve().parent / 'wm8960-master-disabled.dtso'
    overlay = out / 'wm8960-master-disabled.dtbo'
    merged = out / 'merged-disabled.dtb'
    run([K / 'build/scripts/dtc/dtc', '-@', '-I', 'dts', '-O', 'dtb', '-o', overlay, source])
    run([K / 'build/scripts/dtc/fdtoverlay', '-i', base, '-o', merged, overlay])
    bus = '/a13-audio-master@a1000000'
    serial = bus + '/audio-serial@a1000000'
    dma = bus + '/dma@a1020000'
    iic = bus + '/i2c@a1030000'
    nodes = ['/a13cm-fabric-clock', '/a13cm-module-oscillator', '/a13cm-sound', '/a13cm-afi',
             bus, serial, dma, dma + '/dma-channel-mm2s', dma + '/dma-channel-s2mm', iic, iic + '/codec@1a']
    for node in nodes:
        assert run([GET, merged, node, 'status']) == 'disabled'
    for node, irq in [(serial, '6b'), (dma + '/dma-channel-mm2s', '68'),
                      (dma + '/dma-channel-s2mm', '69'), (iic, '6a')]:
        assert run([GET, '-t', 'x', merged, node, 'interrupts']) == '0 ' + irq + ' 4'
    assert run([GET, '-t', 'x', merged, iic + '/codec@1a', 'wlf,gpio-cfg']) == '1 0'
    for node, prop in [('/chosen', 'bootargs'), ('/', 'model'), ('/memory@0', 'reg')]:
        assert run([GET, '-t', 'bx', base, node, prop]) == run([GET, '-t', 'bx', merged, node, prop])
    value = {'status': 'PASS_LOCAL_DISABLED_DT_COMPILE_MERGE', 'disabled_nodes': nodes,
             'GIC_SPI': [104, 105, 106, 107], 'GIC_ID': [136, 137, 138, 139],
             'ALRCGPIO': 1, 'shared_lrclk': True, 'BOARD': 'NOT_TESTED',
             'base_is_fresh_live_readback': False, 'hardware_connectivity': 'REQUIRES_NEW_HWH_CHECK',
             'source_sha256': sha(source), 'base_sha256': sha(base), 'merged_sha256': sha(merged)}
    (out / 'RESULT.json').write_text(json.dumps(value, indent=2) + '\n')
    print(json.dumps(value))


if __name__ == '__main__':
    main()
