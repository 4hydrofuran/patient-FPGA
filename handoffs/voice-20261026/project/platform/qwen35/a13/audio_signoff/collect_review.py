"""Collect actual offline receipts, vendor/source audits and arithmetic evidence."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[4]
E = ROOT / 'evidence/a13_A/20261024-audio-offline-signoff-v1'
sys.path.insert(0, str(Path(__file__).resolve().parent))
from calculations import mixed_values, pll_factors, pullup_budget, xiic_registers


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        assert sha(source) == sha(target), ('existing evidence differs', str(target))
        return
    with source.open('rb') as src, target.open('xb') as dst:
        shutil.copyfileobj(src, dst)
    assert sha(source) == sha(target)


def main():
    assert sys.platform == 'linux', 'collect via local WSL filesystem, no board access'
    for receipt in ['contracts-before', 'config-before', 'freeze-command', 'pc-tests',
                    'inspect-queue', 'inspect-controller', 'inspect2-queue',
                    'inspect2-controller', 'locked-modules-build', 'render-reference']:
        assert load(E / (receipt + '.json'))['exit_code'] == 0, receipt
    for attempt in ['s01', 's02']:
        work = ROOT / ('local/a13s_' + attempt)
        assert load(work / 'COMPLETION.json')['exit_code'] == 0
        assert sha(work / 'a06_routed.dcp') == sha(ROOT / 'local/a13w_a06/wm8960_routed.dcp')
        for p in sorted(work.rglob('*')):
            if p.is_file() and p.suffix not in {'.dcp', '.zip'} and '.Xil' not in p.parts:
                copy(p, E / 'routed-inspection' / attempt / p.relative_to(work))
    request = json.loads(load(E / 'locked-modules-build.json')['stdout'])
    assert request['exit_code'] == 0 and request['status'] == 'COMPLETED'
    work = Path(request['cwd'])
    for p in work.iterdir():
        if p.is_file():
            copy(p, E / 'locked-build' / p.name)
    for p in (work / 'modules').iterdir():
        if p.is_file() and (p.suffix in ['.ko', '.c', '.h'] or p.name in ['Makefile', 'SOURCE_MANIFEST.json']):
            copy(p, E / 'locked-build/modules' / p.name)
    # Known kernel/vendor sources are read-only. Record identities, not a vendor
    # HDL redistribution or any attempt to inspect protected I2S implementation.
    kernel = Path('/home/member-a/a10-kernel-irq2-20261021-v1/source')
    vendor = Path('/mnt/d/AMDDesignTools/2026.1/Vivado/data/ip/xilinx')
    paths = [kernel / s for s in ['sound/soc/codecs/wm8960.c', 'sound/soc/xilinx/xlnx_i2s.c',
                                  'sound/soc/xilinx/xlnx_formatter_pcm.c', 'drivers/i2c/busses/i2c-xiic.c']]
    paths += [vendor / s for s in ['audio_formatter_v1_0/hdl/audio_formatter_v1_0_rfs.v',
                                   'axi_iic_v2_1/hdl/axi_iic_v2_1_rfs.vhd',
                                   'i2s_transmitter_v1_0/hdl/i2s_transmitter_v1_0_rfs.sv',
                                   'i2s_receiver_v1_0/hdl/i2s_receiver_v1_0_rfs.sv']]
    sources = {str(p): {'bytes': p.stat().st_size, 'sha256': sha(p)} for p in paths}
    codec, i2s, formatter, iic_driver, fmt_rtl, iic_rtl, tx, rx = [p.read_text(errors='replace') for p in paths]
    assert re.search(r"fs_multiplier_value\s*<=\s*'h180;", fmt_rtl)
    assert re.search(r'\.WIDTH\s*\(\s*16\s*\)', fmt_rtl) and 'xpm_cdc_array_multiplier' in fmt_rtl
    assert 'if (C_IIC_FREQ <= 100000)' in iic_rtl
    assert '{ 5700, 5000, 4300, 550, 5000 }' in iic_driver
    assert 'chan_id = params_channels(params) / 2;' in i2s
    assert 'writel(chan_id, drv_data->base + reg_off);' in i2s
    assert 'if (pll_id == WM8960_SYSCLK_AUTO)\n\t\treturn 0;' in codec
    assert 'wm8960->bclk = snd_soc_params_to_bclk(params);' in codec
    assert 'pragma protect' in tx and 'pragma protect' in rx
    hwh = ROOT / 'local/a13w_a06/e/my_project.gen/sources_1/bd/MPSoC_ext_platform/hw_handoff/MPSoC_ext_platform.hwh'
    module = [n for n in ET.parse(hwh).findall('.//MODULE') if n.get('INSTANCE') == 'iic']
    assert len(module) == 1
    pars = {n.get('NAME'): n.get('VALUE') for n in module[0].findall('./PARAMETERS/PARAMETER')}
    expected = {'C_IIC_FREQ': '100000', 'C_S_AXI_ACLK_FREQ_HZ': '99999001',
                'C_SCL_INERTIAL_DELAY': '0', 'C_SDA_INERTIAL_DELAY': '0', 'C_SDA_LEVEL': '1'}
    assert all(pars[key] == val for key, val in expected.items())
    a = E / 'routed-inspection/s01/reports'
    cdc = (a / 'cdc.rpt').read_text()
    assert re.search(r'CDC-6\s+Warning\s+3', cdc)
    cells = (a / 'cdc_cells.txt').read_text()
    assert cells.count(' REF FDRE') == 50
    assert cells.count('ASYNC_REG 1') == 44
    src = (E / 'routed-inspection/s02/reports/config_source_cells.txt').read_text()
    for direction in ['rx', 'tx']:
        selected = [line for line in src.splitlines() if line.startswith('CELL ') and f'/{direction}/' in line]
        assert len(selected) == 3
        assert sum("REF FDSE INIT 1'b1" in line for line in selected) == 1
        assert sum("REF FDRE INIT 1'b0" in line for line in selected) == 2
    bus = (E / 'routed-inspection/s02/reports/bus_skew.rpt').read_text()
    slacks = [float(x) for x in re.findall(r'Slack \(MET\)\s*:\s*([\d.]+)ns', bus)]
    assert len(slacks) == 5 and min(slacks) >= 0 and 'Slack (VIOLATED)' not in bus
    delays = {}
    for signal in ['sda', 'scl']:
        for direction in ['input', 'output']:
            text = (a / f'wm8960_iic_{signal}_io_{direction}.rpt').read_text()
            assert text.count('Slack:                    inf') == 2
            values = [float(v) for v in re.findall(r'Data Path Delay:\s*([\d.]+)ns', text)]
            assert len(values) == 2
            delays[signal + '_' + direction] = {'max_path_ns': values[0], 'min_path_ns': values[1],
                                               'external_timing_status': 'UNCONSTRAINED_NOT_PASS'}
    result = {
        'status': 'OFFLINE_REVIEW_COMPLETE_WITH_EXPLICIT_OPEN_SIGNOFF_GATES',
        'part': 'xck26-sfvc784-2LV-c', 'tool_release': '2026.1',
        'level': 'SOURCE_AUDIT_PC_ARITHMETIC_POST_ROUTE_STA_AND_AARCH64_CROSS_BUILD',
        'routed_dcp_sha256': sha(ROOT / 'local/a13w_a06/wm8960_routed.dcp'),
        'cdc': {'warnings_6_remaining': 3, 'waivers_added': 0, 'new_timing_exceptions': 0,
                'source_sync_flops': 6, 'destination_sync_flops': 44,
                'chmux_source_powerup_value_each': 1,
                'fixed_profile_chmux_driver_write': 1,
                'multiplier_reset_value': 384, 'required_fixed_profile_multiplier': 256,
                'cold_sync_possible_words_PC_model': sorted(mixed_values(0, 384, 16)),
                'program_384_to_256_words_PC_model': sorted(mixed_values(384, 256, 16)),
                'bind_only_safety': 'OPEN_PARAMS_TRIGGER_ALWAYS_EPERM_CROSS_BUILT_NOT_LOADED',
                'streaming_configuration_protocol': 'NOT_IMPLEMENTED_OR_VERIFIED',
                'analog_metastability_or_MTBF': 'NOT_PROVEN'},
        'bus_skew': {'constraints': len(slacks), 'worst_slack_ns': min(slacks), 'status': 'MET_FOR_EXISTING_FIFO_GRAY_POINTER_CONSTRAINTS_NOT_CONFIG_ATOMICITY'},
        'iic': {'generated_parameters': expected, 'Linux_timer_registers_at_HWH_clock': xiic_registers(99999001),
                'pad_paths': delays, 'inertial_filter_config_cycles': 0,
                'input_synchronizer_stages_each': 4,
                'rise_limit_ns': 300, 'fall_limit_ns': 300,
                'rise_limit_basis': 'codec datasheet p16 stricter than Standard-mode 1000ns',
                'report_2k_pullup_model_100pf': pullup_budget(2000, 100),
                'electrical_timing': 'NOT_TESTED'},
        'clock': {'PL_nominal_mclk_hz': 12288000, 'PL_nominal_bclk_hz': 3072000,
                  'PL_nominal_lrclk_hz': 48000, 'module_reported_oscillator_hz': 24000000,
                  'common_reference_proven': False, 'independent_PLL_lock_not_proof_of_sync': True,
                  'old_AUTO_PLL_call_programs_requested_output_immediately': False,
                  'pll_calculation_only': {k: str(v) for k, v in pll_factors(24000000, 24576000).items()},
                  'unreachable_old_clock_calls_removed_in_new_locked_candidate': True,
                  'physical_clock_direction_wiring_changes': 0,
                  'future_streaming_clock_topology': 'USER_HARDWARE_CHOICE_AND_VENDOR_BOARD_DETAILS_REQUIRED'},
        'PC_tests': 19, 'RTL_SIMULATION': 'NOT_TESTED', 'CSIM': 'NOT_APPLICABLE', 'COSIM': 'NOT_TESTED',
        'new_synthesis_implementation': 'NOT_RERUN_READ_ONLY_A06_DCP', 'AARCH64_MODULE_CROSS_BUILD': 'PASS',
        'BOARD': 'NOT_TESTED', 'supply_V': 3.3, 'total_limit_mA': 100,
        'measured_current_mA': None, 'deployment_allowed': False, 'audio_allowed': False,
        'sources': sources}
    save(E / 'OFFLINE_REVIEW.json', result)
    print(json.dumps({key: result[key] for key in ['status', 'PC_tests', 'AARCH64_MODULE_CROSS_BUILD', 'BOARD', 'deployment_allowed']}))


if __name__ == '__main__':
    main()
