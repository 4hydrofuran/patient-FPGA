"""Independent no-board package/WAV/source review, preserving private payload."""
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import shutil
import sys
import wave
import xml.etree.ElementTree as ET

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
E = ROOT / 'evidence/a13_A/20261024-audio-nowire-tts-v1'
sys.path.insert(0, str(ROOT))
from modules.voice_A.file_tts.pcm import convert, read_mono
from clock_model import codec_plan, oversampling_budget


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def copy(source, target):
    with source.open('rb') as src, target.open('xb') as dst:
        shutil.copyfileobj(src, dst)
    assert sha(source) == sha(target)


def main():
    for name in ['contracts-before', 'config-before', 'freeze-before', 'tests-offline',
                 'tts-pc-files', 'tts-pc-files-v2', 'prepare-arm64-package']:
        assert load(E / (name + '.json'))['exit_code'] == 0, name
    rejected = load(E / 'tts-arm-launch-refusal.json')
    assert rejected['exit_code'] == 2 and 'ARM64 target required' in rejected['stderr']
    assert not (E / 'not-created-arm-test').exists()
    package = E / 'package-arm64-file-only'
    manifest = load(package / 'MANIFEST.json')
    for name, entry in manifest['files'].items():
        path = package / name
        assert not path.is_symlink() and sha(path) == entry['sha256'] and path.stat().st_size == entry['bytes'], name
    actual = {p.relative_to(package).as_posix() for p in package.rglob('*') if p.is_file() and p.name != 'MANIFEST.json'}
    assert actual == set(manifest['files'])
    for path in (ROOT / 'modules/voice_A/file_tts').glob('*.py'):
        assert sha(path) == sha(package / 'code/modules/voice_A/file_tts' / path.name), path.name
    assert sha(ROOT / 'platform/qwen35/a13/nowire_tts/run-file-tts.sh') == sha(package / 'run-file-tts.sh')
    details = load(package / 'PACKAGE.json')
    assert len(details['wheels']) == 4 and details['elf_count'] == 144 and details['TTS_assets'] == 19
    assert not details['installed'] and details['BOARD'] == 'NOT_TESTED'
    copy(package / 'PACKAGE.json', E / 'TTS_PACKAGE.json')
    copy(package / 'MANIFEST.json', E / 'TTS_PACKAGE_MANIFEST.json')
    generated = E / 'tts-pc-files-v2'
    tts = load(generated / 'RESULT.json')
    assert tts['domain'] == 'PC_x86_64' and not tts['playback'] and not tts['capture']
    assert tts['conversion']['source'] == 'exact_saved_22050_mono_PCM16_WAV'
    for name, digest in tts['file_sha256'].items():
        assert sha(generated / name) == digest
    converted, conversion = convert(read_mono(generated / 'tts-22050-mono.wav'))
    with wave.open(str(generated / 'tts-48000-stereo.wav'), 'rb') as wav:
        assert (wav.getframerate(), wav.getnchannels(), wav.getsampwidth(), wav.getnframes()) == (48000, 2, 2, len(converted))
        raw = wav.readframes(wav.getnframes())
        assert raw == converted.tobytes(), 'output must reproduce exactly from the saved source WAV'
    assert abs(tts['output_duration_s'] - tts['source_duration_s']) < 1 / 48000
    budgets = [dict(slot_bits=bits, duty_min=str(duty), **oversampling_budget(bits, hz, ppm, duty))
               for bits in [16, 32] for hz in [99000000, 99999001, 101000000]
               for ppm in [-500, 0, 500] for duty in [Fraction(2, 5), Fraction(1, 2)]]
    assert len(budgets) == 36 and all(row['positive_budget'] for row in budgets)
    hwh = ROOT / 'local/a13w_a06/e/my_project.gen/sources_1/bd/MPSoC_ext_platform/hw_handoff/MPSoC_ext_platform.hwh'
    ports = {n.get('NAME'): n.get('DIR') for n in ET.parse(hwh).findall('./EXTERNALPORTS/PORT')}
    assert ports['wm8960_bclk'] == ports['wm8960_lrclk'] == 'O'
    vendor = Path('/mnt/d/AMDDesignTools/2026.1/Vivado/data/ip/xilinx')
    gui = vendor / 'i2s_transmitter_v1_0/xgui/i2s_transmitter_v1_0.tcl'
    stub = ROOT / 'local/a13w_a06/e/my_project.gen/sources_1/bd/MPSoC_ext_platform/ip/MPSoC_ext_platform_tx_0/MPSoC_ext_platform_tx_0_stub.v'
    assert 'visible false $IS_MASTER' in gui.read_text()
    assert 'C_IS_MASTER=0' in stub.read_text() and 'input sclk_in;' in stub.read_text()
    base = load(E / 'BASELINE.json')
    for name in ['modules/voice_A/engine.py', 'modules/voice_A/worker.py', 'modules/voice_A/manifest.json',
                 'modules/voice_A/resources.lock.json', 'contracts/qwen35/voice_v1.json', 'contracts/qwen35/contracts.lock']:
        assert sha(ROOT / name) == base['files'][name], ('protected input changed', name)
    result = {'status': 'PASS_OFFLINE_TTS_PREPARATION_CLOCK_ARCHITECTURE_FEASIBLE_NOT_IMPLEMENTED',
              'recommended': 'WM8960_MASTER_24MHz_PLL_NEW_OVERSAMPLED_PL_SLAVE_DEVICE_PACED_DMA',
              'signal_rewiring_required_for_recommendation': False, 'crystal_removal_required': False,
              'new_PL_and_driver_implementation_required': True,
              'existing_a06_direct_reuse': 'REJECTED_OUTPUT_CONTENTION_UNSUPPORTED_SLAVE_AND_INDEPENDENT_CADENCE',
              'a06_hwh_clock_pin_directions': {key: ports[key] for key in ['wm8960_bclk', 'wm8960_lrclk']},
              'recommended_16bit_slot_plan': codec_plan(), 'optional_32bit_slot_plan': codec_plan(32),
              'oversampling_arithmetic_cases': len(budgets),
              'worst_budget_ns_by_slots': {str(bits): min(row['remaining_TX_pad_wire_jitter_budget_ns'] for row in budgets if row['slot_bits'] == bits) for bits in [16, 32]},
              'oversampling_assumptions_not_physical_proof': budgets,
              'vendor_support': {'PG308_Unsupported_Features_lists_slave_unsupported': True,
                                 'installed_interface_exposes_hidden_slave': True,
                                 'reconciliation_or_vendor_slave_qualification': 'NOT_AVAILABLE_DO_NOT_ASSUME_SUPPORT',
                                 'references': ['https://docs.amd.com/r/en-US/pg308-i2s/Unsupported-Features',
                                    'https://docs.amd.com/r/en-US/pg330-audio-formatter/Clocking',
                                    'https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/307/WM8960.pdf']},
              'protected_source_identities': {str(p): sha(p) for p in [gui, stub, hwh]},
              'new_tests': 21, 'converter': 'POLYPHASE_FIR_320_OVER_147_NOT_ASRC_OR_CLOCK_SYNC',
              'package_files': len(manifest['files']), 'package_bytes': manifest['total_bytes'],
              'ARM64_ELFs': details['elf_count'], 'selected_wheels': 4, 'TTS_assets': 19,
              'PACKAGE_MANIFEST_sha256': sha(package / 'MANIFEST.json'),
              'TTS_PC': {'frames_22050': tts['conversion']['input_frames'], 'frames_48000': len(converted),
                         'load_ms': tts['load_ms'], 'synthesis_ms': tts['synthesis_ms'],
                         'duration_s': tts['source_duration_s'], 'max_RSS_KiB': tts['max_rss_KiB_linux'],
                         'exceeds_256MiB_design_budget_on_PC': tts['max_rss_KiB_linux'] > 256 * 1024,
                         'ARM_memory_inference': 'NOT_PERMITTED_TARGET_MUST_BE_MEASURED',
                         'file_reproduction_bit_exact': True, 'listening_quality': 'NOT_TESTED'},
              'target_import_symbol_resolution_ISA': 'NOT_TESTED', 'RTL_SIMULATION': 'NOT_TESTED',
              'new_synthesis_implementation': 'NOT_RUN_NO_NEW_HARDWARE_IMPLEMENTED',
              'BOARD': 'NOT_TESTED', 'old_CDC_warnings': 3, 'old_IIC_external_timing': 'NOT_TESTED',
              'playback': False, 'capture': False, 'board_writes': 0, 'current_mA': None,
              'supply_V': 3.3, 'total_limit_mA': 100, 'redistribution_allowed': False,
              'previous_sealed_files_preserved_at_start': base['previous_files_unchanged']}
    save(E / 'REVIEW.json', result)
    print(json.dumps({key: result[key] for key in ['status', 'new_tests', 'package_files', 'package_bytes', 'ARM64_ELFs', 'BOARD', 'playback']}))


if __name__ == '__main__':
    main()
