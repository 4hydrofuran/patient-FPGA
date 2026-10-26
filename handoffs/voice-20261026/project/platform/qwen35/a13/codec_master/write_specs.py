"""从已确认接口合同发布规格与真正的WaveDrom SVG；不从RTL推测行为。"""
import json
from pathlib import Path
import sys

SKILL = Path('C:/Users/Fang/.codex/skills/verilog-generator')
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(SKILL))
from scripts.python.workflow.spec_document import write_spec_bundle
from scripts.python.quality.formatter_ast import build_ast_report_for_path
from scripts.python.quality.vg_value_facts import module_widths


def port(name, width, description):
    return {'name': name, 'direction': 'input' if name.startswith('i_') else 'output',
            'width': width, 'description': description, 'role': description,
            'clock_domain': 'external_async' if name in ['i_bclk', 'i_lrclk', 'i_adcdat'] else 'i_clk'}


def module(name, ports, behavior, wave):
    return {'name': name, 'feature': 'codec_master', 'rtl_path': 'rtl/' + name + '.v',
        'interfaces': {'ports': [port(*p) for p in ports]},
        'clock': {'name': 'i_clk', 'edge': 'posedge', 'nominal_hz': 99999001},
        'reset': {'name': 'i_rstn', 'active_level': 0, 'type': 'asynchronous_assert_synchronous_release_by_proc_sys_reset'},
        'behavior': behavior, 'constraints': ['Verilog-2001；单系统时钟，固定16位槽、48kHz双声道。',
             '时钟/数据入口与片外建立保持采用独立预算；亚稳态不能由RTL仿真证明消失。'],
        'corner_cases': ['上电或重新使能处于半帧时，必须等真实左起点。',
             '失钟/欠载/阻塞/错误槽宽或包尾需要STOP和显式确认后恢复。'],
        'verification_cases': ['独立帧模型；异步相位、40%-60%占空、左右LSB跨界。',
             'xsim正常520帧与五类故障；周期和输入偏斜扫查，综合/实现/CDC/STA单独列证据。'],
        'timing_diagrams': [{'id': 'boundary', 'title': '已确认接口的示意时序（不是实测波形）',
             'scenario': 'i2s_boundary', 'description': '波形是合同示意；实际仿真必须另读xsim日志。',
             'wavejson': {'signal': wave, 'config': {'hscale': 2}}}]}


def main():
    sampler = module('audio_input_sampler', [
        ('i_clk', 1, 'PS输出的唯一过采样时钟'), ('i_rstn', 1, '专用复位器输出'),
        ('i_bclk', 1, 'H12上的异步位时钟电平，仅作为数据'),
        ('i_lrclk', 1, 'E10上的异步左右标记'), ('i_adcdat', 1, 'C11上的异步录音位'),
        ('o_rise', 1, '延迟上升事件'), ('o_fall', 1, '延迟下降事件'),
        ('o_channel', 1, '已稳定的声道电平'), ('o_sample', 1, '已稳定的ADC位')],
        ['三个独立三级ASYNC_REG链，BCLK额外延迟四拍后产生注册边沿。',
         'LR和ADC先稳定，再由串行引擎在延迟事件消费；不使用BCLK驱动PL时钟网络。'],
        [{'name': 'i_clk', 'wave': 'p..........'}, {'name': 'i_bclk', 'wave': '01.........'},
         {'name': 'sync_final', 'wave': '0..1.......'}, {'name': 'o_rise', 'wave': '0.......10.'}])
    engine = module('audio_serial_slave', [
        ('i_clk', 1, '与AXI相同的系统时钟'), ('i_rstn', 1, '专用低有效复位'),
        ('i_rise', 1, '已同步的上升事件'), ('i_fall', 1, '已同步的下降事件'),
        ('i_channel', 1, '稳定LR'), ('i_sample', 1, '稳定ADC位'),
        ('i_control', 32, '位0播放、位1采集、位2仅停机时确认错误'),
        ('i_s_axis_tdata', 32, '播放L低16/R高16'), ('i_s_axis_tlast', 1, '发送第256帧包尾'),
        ('i_s_axis_tvalid', 1, '播放负载所有权'), ('o_s_axis_tready', 1, '注册预取许可'),
        ('o_m_axis_tdata', 32, '录音L低16/R高16'), ('o_m_axis_tlast', 1, '保持型录音包尾'),
        ('o_m_axis_tvalid', 1, '保持型录音所有权'), ('i_m_axis_tready', 1, '内存接收许可'),
        ('o_dacdat', 1, 'D10唯一数字输出'), ('o_status', 32, '0xa13c签名与锁存诊断'),
        ('o_irq', 1, '错误保持型中断')],
        ['固定I2S一位延迟，边界上升采旧字LSB；下降事件寄存译码后装下一字。',
         '所有控制、状态、弹性缓冲和DMA流均属于i_clk，无独立48k采样发生器。',
         'TX缓存仅一帧；RX在空间不足时锁存错误，不覆盖旧负载。',
         '注册指令增加系统拍延迟，器件端采样率仍由WM8960决定。',
         '错误位0失钟、1槽宽、2欠载、3溢出、4包尾；位6播放对齐、7帧锁定。'],
        [{'name': 'BCLK', 'wave': 'p.......'}, {'name': 'LR', 'wave': '10......'},
         {'name': 'serial_bit', 'wave': '=.=.=.=.', 'data': ['old LSB', 'new MSB', 'bit14', 'bit13']},
         {'name': 'left_consume', 'wave': '010.....'}])
    testbench = module('tb_audio_serial_slave', [('o_pass', 1, '所有自检完成后才拉高')],
        ['内部10ns系统时钟，独立codec位流与DMA源汇，不读DUT移位寄存器求golden。',
         '1024帧向量由独立Python模型生成；520帧双向比较及两次256帧TLAST。',
         '五类故障另测：失钟、错误槽宽、欠载、溢出和错误包尾。',
         '额外覆盖运行中拒绝清错、非零负载回压保持、半帧启动、单向槽宽监视、复位隔离。',
         '648..652ns周期和10..30ns LR偏斜为数字压力，不代表振荡器实测或亚稳态模拟。'],
        [{'name': 'i_clk_internal', 'wave': 'p.........'},
         {'name': 'test_windows', 'wave': '=..=..=..=', 'data': ['duplex', 'faults', 'reset', 'complete']},
         {'name': 'o_pass', 'wave': '0........1'}])
    testbench['rtl_path'] = 'tb/tb_audio_serial_slave.v'
    testbench['clock']['nominal_hz'] = 100000000
    testbench['reset']['type'] = 'testbench_internal_async_assert'
    testbench['constraints'] = ['仅验证，含延时和task，不用于综合或板端部署。',
                               '仿真不能模拟模拟亚稳态或证明MTBF。']
    spec = {'modules': [sampler, engine, testbench], 'rtl_style_profile': 'erie_strict',
            'handshake_channels': [
                {'id': 'playback', 'valid': 'i_s_axis_tvalid', 'ready': 'o_s_axis_tready', 'payload': 'i_s_axis_tdata'},
                {'id': 'capture', 'valid': 'o_m_axis_tvalid', 'ready': 'i_m_axis_tready', 'payload': 'o_m_axis_tdata'}]}
    with (ROOT / 'spec.json').open('w', encoding='utf-8') as stream:
        json.dump(spec, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    settings = json.loads((SKILL / 'config/defaults.json').read_text(encoding='utf-8'))
    # 文档提取器把task形参/AMD属性字符串误认成端口，原始失败保留。
    # 改用同技能的formatter AST核对真实设计端口，不加入第二套Verilog解析器，
    # 也不把ACTIVE_LOW、lr等伪造成顶层端口；随后走正式no-source合同渲染入口。
    checked = []
    for contract in [sampler, engine]:
        ast = build_ast_report_for_path(ROOT / contract['rtl_path'])
        assert not ast['diagnostics'] and len(ast['modules']) == 1
        module_ast = ast['modules'][0]
        assert module_ast['name'] == contract['name']
        widths = module_widths(module_ast)
        actual = {p['name']: (p['direction'], widths[p['name']]) for p in module_ast['ports']}
        expected = {p['name']: (p['direction'], p['width']) for p in contract['interfaces']['ports']}
        assert actual == expected, (contract['name'], actual, expected)
        checked.append({'module': contract['name'], 'ports': actual, 'source': 'FORMATTER_AST'})
    result = write_spec_bundle(spec, ROOT, runtime_settings=settings)
    print(json.dumps({'design_source_checked': checked, 'confirmed_contract_bundle': result,
                      'document_source_extractor': 'FAILED_TASK_AND_ATTRIBUTE_FALSE_POSITIVES_RETAINED'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
