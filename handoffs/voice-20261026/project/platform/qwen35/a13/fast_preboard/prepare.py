"""Generate the isolated fast candidate on the PC; never contact the board."""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[4]
SRC = Path(__file__).resolve().parent
E = ROOT / 'evidence/a13_A/20261026-fast-preboard-v1'
OLD_E = ROOT / 'evidence/a13_A/20261025-audio-muted-bringup-v1'
OUT = E / 'candidate-01'
BUILD = Path('/home/member-a/a13-fast-preboard-20261026-v1/build-01')
WINDOW = 'a13-fast-20261026-v1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def functions(source, selected):
    return '\n\n'.join(ast.get_source_segment(source, n) for n in ast.parse(source).body
                       if isinstance(n, ast.FunctionDef) and n.name in selected)


def main():
    OUT.mkdir(exist_ok=False)
    BUILD.mkdir(parents=True, exist_ok=False)
    bus = BUILD / 'bus'; bus.mkdir()
    shutil.copyfile(SRC / 'a13_audio_bus.c', bus / 'a13_audio_bus.c')
    (bus / 'Makefile').write_text('obj-m += a13_audio_bus.o\n')
    # Keep the sealed PCM program intact; shorten the derived stream accurately.
    pcm = (ROOT / 'platform/qwen35/a13/codec_board_muted/pcm_zero_test.c').read_text()
    pcm = pcm.replace('frames = drop ? 16384 : 49152;', 'frames = drop ? 4608 : 47872;')
    pcm = pcm.replace('snd_pcm_writei(pcm, zeros, 256)',
                      'snd_pcm_writei(pcm, zeros, frames - written < 256 ? frames - written : 256)')
    pcm = pcm.replace('elapsed = monotonic() - start;',
                      'elapsed = monotonic() - start;\n\tif (elapsed > 3.0) { fprintf(stderr, "PCM unexpectedly slow\\n"); snd_pcm_close(pcm); return 4; }')
    assert 'frames = drop ? 4608 : 47872;' in pcm
    (BUILD / 'pcm_zero_test.c').write_text(pcm)
    shutil.copyfile(BUILD / 'pcm_zero_test.c', OUT / 'pcm_zero_test.c')
    # Split PL/AFI setup from peripheral publication. Only pl-load contains firmware-name.
    original_dt = (OLD_E / 'dt-03/audio-muted.dtso').read_text()
    tree = re.sub(r'xilinx/a13-muted-20261025-v[0-9]+/', 'xilinx/' + WINDOW + '/', original_dt)
    start = tree.index('    fragment@0 {')
    stop = tree.index('    fragment@10 {')
    program = tree[start:stop]
    afi_start = tree.index('            a13muted_afi:')
    afi_stop = tree.index('\n            };', afi_start) + len('\n            };')
    afi = tree[afi_start:afi_stop]
    peripherals = tree[:afi_start] + tree[afi_stop:]
    peripherals = peripherals.replace(program, '')
    peripherals = peripherals.replace('compatible = "simple-pm-bus";',
                                        'compatible = "patientqwen,a13-audio-bus";')
    assert 'firmware-name' not in peripherals and 'simple-pm-bus' not in peripherals
    pl = '/dts-v1/;\n/plugin/;\n/ {\n' + program + '\n    fragment@1 {\n        target-path = "/";\n        __overlay__ {\n' + afi + '\n        };\n    };\n};\n'
    (OUT / 'pl-load.dtso').write_text(pl)
    (OUT / 'audio-muted.dtso').write_text(peripherals)
    # Derive only useful stages; the dangerous cleanup/restore functions are absent.
    path = ROOT / 'platform/qwen35/a13/muted_control/derive.py'
    spec = importlib.util.spec_from_file_location('old_derive', path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    raw = (ROOT / 'platform/qwen35/a13/codec_board_muted/board_manager.py').read_bytes()
    derived = mod.derive(raw)
    cut = derived.index('def candidate_prepare():')
    core = derived[:cut] + functions(derived, {'candidate_prepare', 'candidate_install', 'candidate_bind'}) + '\n'
    core = core.replace("BOOT = '415c0647-4061-40c2-bf13-36d5c55ba80c'", 'BOOT = None')
    core = core.replace("BASELINE = '07bdb3b2a7e49a59f848b9c78b728956a06d21989eedd9f2c54c200c3741542f'", 'BASELINE = None')
    core = core.replace("'6.8.12-a10irq2'", "'6.8.0-1036-xilinx'")
    for assignment in ['OUT', 'FW', 'MUTED']:
        lines = core.splitlines()
        lines = [assignment + ' = None' if line.startswith(assignment + ' = ') else line for line in lines]
        core = '\n'.join(lines) + '\n'
    # One combined scan/resource/baseline check, now AFTER acquiring actual flocks.
    begin = core.index('    raw = kernel_raw(); assert')
    end = core.index('    for path in (CENTRAL /', begin)
    checks = core[begin:end]
    core = core[:begin] + core[end:]
    core = core.replace('    OUT.mkdir(mode=0o700)', checks + '    OUT.mkdir(mode=0o700)')
    core = core.replace("'pcm_zero_test', 'audio-muted.dtbo', 'codec_master.bit.bin'}",
                         "'pcm_zero_test', 'audio-muted.dtbo', 'pl-load.dtbo', 'a13_audio_bus.ko', 'codec_master.bit.bin'}")
    core = core.replace("data = base64.b64decode(item['base64'], validate=True)",
                         "data = (BUNDLE / name).read_bytes()")
    core = core.replace("('a13_muted_dma', 'a13_muted_serial', 'a13_muted_codec', 'a13_muted_card')",
                         "('a13_audio_bus', 'a13_muted_dma', 'a13_muted_serial', 'a13_muted_codec', 'a13_muted_card')")
    core = core.replace("('a13_muted_dma', 'a13_muted_serial', 'a13_muted_codec', 'a13_muted_card')}",
                         "('a13_audio_bus', 'a13_muted_dma', 'a13_muted_serial', 'a13_muted_codec', 'a13_muted_card')}")
    core = core.replace("'a13_muted_dma: loading out-of-tree module taints kernel.'", "'a13_audio_bus: loading out-of-tree module taints kernel.'")
    # Running observation remains physical sysfs + actual IRQs; no extra /proc scans.
    # With a 100ms first stream, poll every millisecond instead of 5ms.
    core = core.replace('time.sleep(.005)', 'time.sleep(.001)')
    assert 'candidate_cleanup' not in core and 'candidate_restore_default' not in core
    ast.parse(core)
    (OUT / 'candidate_core.py').write_text(core)
    for name in ['runtime.py', 'runner.py']:
        shutil.copyfile(SRC / name, OUT / name)
    for module, source in {
        'control.py': ROOT / 'platform/qwen35/a13/muted_control/control.py',
        'accelerator_release_gate_v2.py': ROOT / 'platform/qwen35/a10/accelerator_release_gate_v2.py',
        'kernel_log_gate.py': ROOT / 'platform/qwen35/a10/kernel_log_gate.py',
    }.items(): shutil.copyfile(source, OUT / module)
    request = {'schema': 'A13_FAST_MUTED_REQUEST_V1', 'authorized': False,
               'window': WINDOW, 'boot_id': None, 'kernel_log_sha256': None,
               'machine_sha256': 'ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec',
               'kernel': '6.8.0-1036-xilinx', 'audible_output': False, 'recording': False,
               'recovery_exit_confirmed': False, 'physical_supply_confirmed': False,
               'other_PL_users_released': False, 'no_hot_restore': True,
               'PCM': {'sample_rate': 48000, 'channels': 2, 'word_bits': 16,
                       'period_bytes': 1024, 'buffer_bytes': 8192,
                       'short_drop_frames': 4608, 'full_drain_frames': 47872}}
    (OUT / 'REQUEST.template.json').write_text(json.dumps(request, indent=2))
    (OUT / 'DERIVATION.json').write_text(json.dumps({
        'old_manager_sha256': hashlib.sha256(raw).hexdigest(),
        'sealed_four_module_sources_changed': False, 'sealed_PL_changed': False,
        'new_bus_driver': sha(SRC / 'a13_audio_bus.c'),
        'old_DT_SHA256': sha(OLD_E / 'dt-03/audio-muted.dtso'),
        'old_dt_runtime_kernel': '6.8.12-a10irq2', 'target_kernel': '6.8.0-1036-xilinx',
        'board_execution': False, 'compile_and_merge_pending': True,
    }, indent=2))
    print(json.dumps({'status': 'ISOLATED_CANDIDATE_PREPARED_NOT_EXECUTED',
                      'output': str(OUT), 'build': str(BUILD), 'board_actions': 0}))


if __name__ == '__main__': main()
