"""One PC audit/build pass for ELF ABI, native FIT FDT and the staged bundle."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[4]
SRC = Path(__file__).resolve().parent
E = ROOT / 'evidence/a13_A/20261026-fast-preboard-v1'
OUT = E / 'candidate-01'
BUILD = Path('/home/member-a/a13-fast-preboard-20261026-v1/build-01')
HEADERS = Path('/home/member-a/a13-muted-headers1036-20261025-v1/build-01/headers/linux-headers-6.8.0-1036-xilinx')
MODS = Path('/home/member-a/a13-muted-headers1036-20261025-v1/build-01/modules')
NAMES = ['a13_muted_dma', 'a13_muted_serial', 'a13_muted_codec', 'a13_muted_card']
DTC = Path('/home/member-a/a10-kernel-irq2-20261021-v1/build/scripts/dtc')
GET = '/home/member-a/AMDDesignTools/2026.1/gnu/armr5/lin/gcc-arm-none-eabi/x86_64-oesdk-linux/usr/bin/fdtget'


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def save(name, obj):
    with (E / name).open('x') as f: json.dump(obj, f, indent=2)


def elf(path):
    raw = path.read_bytes()
    assert raw[:6] == b'\x7fELF\x02\x01' and struct.unpack_from('<H', raw, 18)[0] == 183
    shoff = struct.unpack_from('<Q', raw, 40)[0]
    entsize, count, strings = struct.unpack_from('<HHH', raw, 58)
    assert entsize == 64 and count > 0
    headers = [struct.unpack_from('<IIQQQQIIQQ', raw, shoff + i * entsize) for i in range(count)]
    h = headers[strings]; names = raw[h[4]:h[4]+h[5]]
    def cstring(data, start): return data[start:data.index(b'\0', start)].decode()
    sections = {cstring(names, h[0]): (h, raw[h[4]:h[4]+h[5]]) for h in headers}
    versions = {}; data = sections['__versions'][1]; offset = 0
    # Ubuntu's matching module.h/modpost uses variable next/u32 CRC/name,
    # not upstream's old 64-byte entries. Host kmod cannot decode this layout.
    while offset + 8 <= len(data):
        nxt, crc = struct.unpack_from('<II', data, offset)
        if nxt == 0:
            assert crc == 0 and not any(data[offset+8:]); break
        assert nxt >= 12 and nxt % 4 == 0 and offset+nxt <= len(data)
        name = cstring(data, offset+8)
        assert name not in versions
        versions[name] = crc; offset += nxt
    else: raise AssertionError('Missing Ubuntu version terminator')
    h, table = sections['.symtab']; strh = headers[h[6]]
    strs = raw[strh[4]:strh[4]+strh[5]]
    undefined = []
    for i in range(0, len(table), h[9]):
        name, info, _, section, _, _ = struct.unpack_from('<IBBHQQ', table, i)
        if name and section == 0 and info >> 4 in (1, 2): undefined.append(cstring(strs, name))
    info = {}
    for item in sections['.modinfo'][1].split(b'\0'):
        if b'=' in item:
            k, v = item.decode().split('=', 1); info[k] = v
    return versions, undefined, info


def abi():
    assert sha(HEADERS / '.config') == 'd0937ab5ab55818252854b3b91d291148c89011e4e5d9f4e2cc134e4c3d9610f'
    assert sha(HEADERS / 'Module.symvers') == '860c5609e229079a4836ec694447b89c9aa8ac42c26c0f1f5672d859f8cd1de1'
    assert 'u32 next;\n\tu32 crc;\n\tchar name[];' in (HEADERS / 'include/linux/module.h').read_text()
    symbols = {s[1]: (int(s[0], 16), s[2]) for line in (HEADERS / 'Module.symvers').read_text().splitlines() if (s := line.split())}
    old = json.loads((ROOT / 'evidence/a13_A/20261025-coldboot-postcheck-v1/full-uart.json').read_text(encoding='utf-8-sig'))['result']
    loaded = {x.split()[0] for x in old['read_files']['/proc/modules']['text'].splitlines()}
    records = []
    for name in NAMES + ['a13_audio_bus']:
        p = MODS / (name + '.ko') if name in NAMES else BUILD / 'bus' / (name + '.ko')
        versions, undefined, info = elf(p)
        assert info['vermagic'] == '6.8.0-1036-xilinx SMP preempt mod_unload modversions aarch64'
        assert info['license'] in ('GPL', 'GPL v2')
        assert 'module_layout' in versions
        assert set(undefined) <= set(versions), set(undefined)-set(versions)
        for symbol, crc in versions.items(): assert symbols[symbol][0] == crc, (name, symbol)
        deps = {x for x in info.get('depends', '').split(',') if x}
        records.append({'module': name, 'sha256': sha(p), 'bytes': p.stat().st_size,
                        'vermagic': info['vermagic'], 'undefined_symbols': undefined,
                        'versioned_symbols': {n: hex(c) for n, c in versions.items()},
                        'all_import_CRCs_match': True, 'dependencies': sorted(deps),
                        'dependencies_missing_in_last_native_boot_snapshot': sorted(deps-loaded),
                        'providers': sorted({symbols[s][1] for s in versions})})
        shutil.copyfile(p, OUT / p.name)
    shutil.copyfile(BUILD / 'pcm_zero_test', OUT / 'pcm_zero_test')
    shutil.copyfile(ROOT / 'evidence/a13_A/20261025-audio-muted-bringup-v1/bit-01/codec_master.bit.bin', OUT / 'codec_master.bit.bin')
    save('ABI.json', {'status': 'PASS_PC_EXACT_HEADERS_ELF_AND_ALL_IMPORT_CRCS', 'modules': records,
                      'config_sha256': sha(HEADERS / '.config'), 'symvers_sha256': sha(HEADERS / 'Module.symvers'),
                      'module_signature_FORCE': False, 'runtime_signature_policy': 'CHECK_AT_NEXT_PREFLIGHT',
                      'ABI_layout': 'Ubuntu variable next/u32 CRC/name', 'BOARD': 'NOT_TESTED'})
    print(json.dumps({'ABI': 'PASS', 'modules': len(records), 'CRCs': sum(len(x['versioned_symbols']) for x in records),
                      'historical_missing_dependencies': {x['module']: x['dependencies_missing_in_last_native_boot_snapshot'] for x in records}}))


def dt():
    commands = []
    command_log = E / ('DT_COMMANDS-' + str(len(list(E.glob('DT_COMMANDS*.json')))+1) + '.json')
    def run(argv):
        p = subprocess.run(list(map(str, argv)), capture_output=True, text=True)
        commands.append({'argv': list(map(str, argv)), 'exit_code': p.returncode, 'stdout': p.stdout, 'stderr': p.stderr})
        command_log.write_text(json.dumps(commands, indent=2))
        assert p.returncode == 0, commands[-1]
        return p.stdout.strip()
    def get(file, node, prop, typ=None):
        return run([GET] + (['-t', typ] if typ else []) + [file, node, prop])
    fit = ROOT / 'evidence/model_pl_A/20261024-ttft10-01-v1/recovery-authorized-20261025-v1/boot-backup-01/image.fit'
    assert sha(fit) == '23a0ad7516d6f67f248f952653324c18a9c7d1db31fdf27a003f021adf0ca61e'
    config = get(fit, '/configurations', 'default')
    fdt = get(fit, '/configurations/' + config, 'fdt')
    raw = bytes(int(x, 16) for x in get(fit, '/images/' + fdt, 'data', 'bx').split())
    assert raw[:4] == b'\xd0\x0d\xfe\xed'
    base = OUT / 'native-1036-base.dtb'; base.write_bytes(raw)
    for name in ['pl-load', 'audio-muted']:
        run([DTC / 'dtc', '-@', '-I', 'dts', '-O', 'dtb', '-o', OUT / (name+'.dtbo'), OUT / (name+'.dtso')])
    merged = OUT / 'native-1036-merged.dtb'
    run([DTC / 'fdtoverlay', '-i', base, '-o', merged, OUT / 'pl-load.dtbo', OUT / 'audio-muted.dtbo'])
    bus = '/a13-muted-audio@a1000000'
    assert get(merged, bus, 'compatible') == 'patientqwen,a13-audio-bus'
    assert get(merged, bus, 'status') == 'okay'
    paths = {'serial': bus+'/audio-serial@a1000000', 'dma': bus+'/dma@a1020000', 'iic': bus+'/i2c@a1030000'}
    for node in paths.values(): assert get(merged, node, 'status') == 'okay'
    assert get(merged, paths['iic']+'/codec@1a', 'compatible') == 'patientqwen,wm8960-muted-diagnostic'
    assert get(merged, paths['iic']+'/codec@1a', 'reg', 'x') == '1a'
    assert get(merged, '/a13muted-module-oscillator', 'clock-frequency', 'i') == '24000000'
    fpga = get(merged, '/__symbols__', 'fpga_full')
    assert get(merged, fpga, 'firmware-name') == 'xilinx/a13-fast-20261026-v1/codec_master.bit.bin'
    clk = get(merged, '/__symbols__', 'zynqmp_clk'); clkid = get(merged, clk, 'phandle', 'x')
    for name in ['serial', 'iic']: assert get(merged, paths[name], 'clocks', 'x') == clkid+' 47'
    for node, irq in [(paths['serial'], '6b'), (paths['iic'], '6a'),
                      (paths['dma']+'/dma-channel-mm2s', '68'), (paths['dma']+'/dma-channel-s2mm', '69')]:
        assert get(merged, node, 'interrupts', 'x') == '0 '+irq+' 4'
    for node, prop in [('/', 'model'), ('/memory@0', 'reg'), ('/chosen', 'bootargs')]:
        assert get(base, node, prop, 'bx') == get(merged, node, prop, 'bx')
    assert 'firmware-name' not in (OUT / 'audio-muted.dtso').read_text()
    save('DT.json', {'status': 'PASS_PC_NATIVE_BOOT_FIT_FDT_MERGE', 'FIT_sha256': sha(fit),
                     'FIT_config': config, 'FIT_FDT_node': fdt, 'base_FDT_sha256': sha(base),
                     'merged_FDT_sha256': sha(merged), 'private_bus_explicit_population': True,
                     'PL_programming_overlay_count': 1, 'BOARD': 'NOT_TESTED',
                     'fresh_running_FDT_identity': 'TO_CHECK_AT_NEXT_SINGLE_PREFLIGHT'})
    print(json.dumps({'DT': 'PASS', 'base': 'default-native-1036-boot-FIT'}))


def seal():
    assets = NAMES + ['a13_audio_bus']
    assets = [x+'.ko' for x in assets] + ['pcm_zero_test', 'codec_master.bit.bin', 'pl-load.dtbo', 'audio-muted.dtbo']
    abi_result = json.loads((E/'ABI.json').read_text())
    for item in abi_result['modules']:
        assert sha(OUT/(item['module']+'.ko')) == item['sha256']
    shutil.copyfile(BUILD/'pcm_zero_test', OUT/'pcm_zero_test')
    # Refresh only the unsealed new candidate's reviewed local implementation.
    for n in ['runtime.py', 'runner.py', 'README.md', 'a13_audio_bus.c']:
        shutil.copyfile(SRC/n, OUT/n)
    derivation = json.loads((OUT/'DERIVATION.json').read_text())
    derivation['compile_and_merge_pending'] = False
    derivation['offline_results'] = {'ABI': 'ABI.json', 'DT': 'DT.json', 'targeted_PC_tests': 'lifecycle-pc-02.json'}
    derivation['preparer_sha256'] = sha(SRC/'prepare.py')
    (OUT/'DERIVATION.json').write_text(json.dumps(derivation, indent=2))
    files = {}
    for p in sorted(OUT.iterdir()):
        if p.is_file() and p.name != 'MANIFEST.json': files[p.name] = {'bytes': p.stat().st_size, 'sha256': sha(p)}
    manifest = {'schema': 'A13_FAST_PREBOARD_BUNDLE_V1', 'status': 'PC_PREPARED_BOARD_NOT_TESTED',
                'files': files, 'assets': {n: files[n] for n in assets},
                'authorized': False, 'runtime_hot_restore': False, 'board_actions': 0}
    with (OUT / 'MANIFEST.json').open('x') as f: json.dump(manifest, f, indent=2)
    print(json.dumps({'status': 'PREBOARD_BUNDLE_SEALED_NOT_DEPLOYED', 'files': len(files),
                      'assets': len(assets), 'manifest_sha256': sha(OUT/'MANIFEST.json')}))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('mode', choices=['abi', 'dt', 'seal']); a = ap.parse_args()
    {'abi': abi, 'dt': dt, 'seal': seal}[a.mode]()
