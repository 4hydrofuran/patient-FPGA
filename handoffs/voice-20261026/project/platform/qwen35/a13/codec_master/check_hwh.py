"""独立回读实际XSA中的HWH，核对无板接口、方向、DMA和DT编号。"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[4]
E = ROOT / 'evidence/a13_A/20261025-audio-codec-master-v1'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('attempt')
    parser.add_argument('--review-label')
    args = parser.parse_args()
    assert args.attempt in {'b03', 'b04', 'b05'}
    xsa = ROOT / 'local' / ('a13c_' + args.attempt) / 'codec_master.xsa'
    label = args.review_label or ('hwh-' + args.attempt)
    assert re.fullmatch(r'hwh-b0[345](?:-v[0-9]+)?', label)
    out = E / label
    out.mkdir(exist_ok=False)
    with zipfile.ZipFile(xsa) as archive:
        raw = archive.read('MPSoC_ext_platform.hwh')
    root = ET.fromstring(raw)
    modules = {m.get('INSTANCE'): m for m in root.findall('.//MODULE')}
    assert len(modules) == 13
    assert not any('i2s' in m.get('MODTYPE', '').lower() or 'audio_formatter' in m.get('MODTYPE', '').lower()
                   for m in modules.values())

    def port(instance, name):
        return next(p for p in modules[instance].findall('PORTS/PORT') if p.get('NAME') == name)

    def params(instance):
        return {p.get('NAME'): p.get('VALUE') for p in modules[instance].findall('PARAMETERS/PARAMETER')}

    def linked(a, ap, b, bp):
        assert port(a, ap).get('SIGNAME') == port(b, bp).get('SIGNAME'), (a, ap, b, bp)

    clocks = {'sampler': ['i_clk'], 'serial': ['i_clk'], 'csr': ['s_axi_aclk'],
              'dma': ['s_axi_lite_aclk', 'm_axi_mm2s_aclk', 'm_axi_s2mm_aclk', 'm_axi_sg_aclk'],
              'iic': ['s_axi_aclk'], 'ctrl': ['aclk'], 'mem': ['aclk']}
    for instance, names in clocks.items():
        for name in names:
            linked(instance, name, 'ps_e', 'pl_clk0')
    assert port('sampler', 'i_clk').get('CLKFREQUENCY') == '99999001'
    for output, target in [('o_rise', 'i_rise'), ('o_fall', 'i_fall'),
                           ('o_channel', 'i_channel'), ('o_sample', 'i_sample')]:
        linked('sampler', output, 'serial', target)
    for source, dest in [('m_axis_mm2s_tdata', 'i_s_axis_tdata'),
                         ('m_axis_mm2s_tvalid', 'i_s_axis_tvalid'),
                         ('m_axis_mm2s_tlast', 'i_s_axis_tlast'),
                         ('m_axis_mm2s_tready', 'o_s_axis_tready'),
                         ('s_axis_s2mm_tdata', 'o_m_axis_tdata'),
                         ('s_axis_s2mm_tvalid', 'o_m_axis_tvalid'),
                         ('s_axis_s2mm_tlast', 'o_m_axis_tlast'),
                         ('s_axis_s2mm_tready', 'i_m_axis_tready')]:
        linked('dma', source, 'serial', dest)
    if args.attempt == 'b05':
        for engine_name, dma_name in [('S_AXIS', 'M_AXIS_MM2S'), ('M_AXIS', 'S_AXIS_S2MM')]:
            engine_bus = next(b for b in modules['serial'].findall('BUSINTERFACES/BUSINTERFACE') if b.get('NAME') == engine_name)
            dma_bus = next(b for b in modules['dma'].findall('BUSINTERFACES/BUSINTERFACE') if b.get('NAME') == dma_name)
            assert engine_bus.get('BUSNAME') == dma_bus.get('BUSNAME') != '__NOC__'
            assert {p.get('LOGICAL') for p in engine_bus.findall('PORTMAPS/PORTMAP')} == {'TDATA', 'TVALID', 'TREADY', 'TLAST'}
            bus_params = {p.get('NAME'): p.get('VALUE') for p in engine_bus.findall('PARAMETER')}
            assert bus_params['HAS_TREADY'] == '1' and bus_params['HAS_TLAST'] == '1'
            assert bus_params['TDATA_NUM_BYTES'] == '4' and bus_params['FREQ_HZ'] == '99999001'
    linked('csr', 'gpio_io_o', 'serial', 'i_control')
    linked('csr', 'gpio2_io_i', 'serial', 'o_status')
    for instance in ['sampler', 'serial']:
        linked(instance, 'i_rstn', 'rst_axi', 'peripheral_aresetn')
    external = {p.get('NAME'): p for p in root.findall('EXTERNALPORTS/PORT')}
    for name, direction, instance, target in [('bclk', 'I', 'sampler', 'i_bclk'),
        ('lrclk', 'I', 'sampler', 'i_lrclk'), ('adcdat', 'I', 'sampler', 'i_adcdat'),
        ('dacdat', 'O', 'serial', 'o_dacdat')]:
        p = external['wm8960_' + name]
        assert p.get('DIR') == direction
        assert [c.attrib for c in p.findall('CONNECTIONS/CONNECTION')] == [{'INSTANCE': instance, 'PORT': target}]
    for bit, instance, target in [(0, 'dma', 'mm2s_introut'), (1, 'dma', 's2mm_introut'),
                                  (2, 'iic', 'iic2intc_irpt'), (3, 'serial', 'o_irq')]:
        linked('irq', 'In' + str(bit), instance, target)
    linked('irq', 'dout', 'ps_e', 'pl_ps_irq1')
    assert params('irq')['IN4_WIDTH'] == '4' and params('irq')['NUM_PORTS'] == '5'
    assert int(params('zero')['CONST_VAL'], 0) == 0
    addresses = {r.get('INSTANCE'): (int(r.get('BASEVALUE'), 16), int(r.get('HIGHVALUE'), 16))
                 for r in root.findall('.//MEMRANGE') if r.get('MEMTYPE') == 'REGISTER'}
    assert addresses == {'csr': (0xa1000000, 0xa100ffff), 'dma': (0xa1020000, 0xa102ffff),
                         'iic': (0xa1030000, 0xa103ffff)}
    dma = params('dma')
    for name, value in {'c_addr_width': '32', 'C_M_AXI_MM2S_ADDR_WIDTH': '32',
                        'C_M_AXI_S2MM_ADDR_WIDTH': '32', 'C_M_AXI_SG_ADDR_WIDTH': '32',
                        'C_INCLUDE_SG': '1', 'C_INCLUDE_MM2S': '1',
                        'C_INCLUDE_S2MM': '1', 'C_M_AXIS_MM2S_TDATA_WIDTH': '32',
                        'C_S_AXIS_S2MM_TDATA_WIDTH': '32', 'C_SG_LENGTH_WIDTH': '23'}.items():
        assert dma[name] == value, (name, dma.get(name))
    keep_output = port('keep', 'dout')
    assert keep_output.get('LEFT') == '3' and keep_output.get('RIGHT') == '0'
    assert [p.attrib for p in keep_output.findall('CONNECTIONS/CONNECTION')] == [{'INSTANCE': 'dma', 'PORT': 's_axis_s2mm_tkeep'}]
    assert int(params('keep')['CONST_VAL'], 0) == 15
    iic = params('iic')
    assert iic['C_IIC_FREQ'] == '100000' and iic['C_S_AXI_ACLK_FREQ_HZ'] == '99999001'
    assert iic['C_SCL_INERTIAL_DELAY'] == '0' and iic['C_SDA_INERTIAL_DELAY'] == '0'
    dt = json.loads((E / 'dt-verified/RESULT.json').read_text(encoding='utf-8'))
    assert dt['GIC_SPI'] == [104, 105, 106, 107] and dt['ALRCGPIO'] == 1
    (out / 'MPSoC_ext_platform.hwh').write_bytes(raw)
    generated = xsa.parent / 'e/my_project.gen/sources_1/bd/MPSoC_ext_platform/synth/MPSoC_ext_platform.v'
    (out / 'MPSoC_ext_platform.v').write_bytes(generated.read_bytes())
    result = {'status': 'PASS_EXPORTED_HWH_STATIC_CONNECTIVITY_AND_DT_MAPPING',
              'xsa_sha256': hashlib.sha256(xsa.read_bytes()).hexdigest(),
              'HWH_sha256': hashlib.sha256(raw).hexdigest(), 'clock_hz': 99999001,
              'register_ranges': addresses, 'GIC_SPI': [104, 105, 106, 107],
              'fixed_stream_bits': 32, 'fixed_period_bytes': 1024,
              'TKEEP': {'constant_value': 15, 'bits': 4, 'exported_constant_sink': 'dma/s_axis_s2mm_tkeep',
                        'generated_HDL_sha256': hashlib.sha256(generated.read_bytes()).hexdigest()},
              'IIC_hz_configured': 100000, 'physical_IIC_edges': 'NOT_TESTED',
              'DMA_full_system_cosimulation': 'NOT_TESTED', 'BOARD': 'NOT_TESTED',
              'deployment_allowed': False}
    (out / 'RESULT.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
