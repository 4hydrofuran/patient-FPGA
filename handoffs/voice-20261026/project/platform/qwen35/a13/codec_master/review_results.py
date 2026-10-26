"""真实工具结果的项目级复核；不把进程exit0或风格例外当作整体PASS。"""
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[4]
E = ROOT / 'evidence/a13_A/20261025-audio-codec-master-v1'
SRC = Path(__file__).resolve().parent
WORK = ROOT / 'local/a13c_b05'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    for name in ['contracts-continue', 'config-continue', 'semantic-model', 'clock-budget-tests',
                 'sim-controller-s05', 'sim-queue-run-s05', 'post-controller-p04', 'post-queue-p04',
                 'hwh-b05-v2', 'dt-verify02', 'modules-queue-run-v5', 'collect-modules-v5',
                 'dai-format-pc', 'dma-guard-pc', 'static-audit-final', 'write-specs07', 'skill-package-shortpath',
                 'protected-old-verify']:
        assert load(E / (name + '.json'))['exit_code'] == 0, name
    assert load(WORK / 'NATIVE_COMPLETION.json')['exit_code'] == 1
    assert load(E / 'build-controller-b05.json')['exit_code'] == 1
    assert load(E / 'build-queue-b05.json')['exit_code'] == 1
    assert 'invalid command name "reset_path"' in (WORK / 'native.log').read_text(encoding='utf-8')
    post = ROOT / 'local/a13c_p04'
    assert load(post / 'NATIVE_COMPLETION.json')['exit_code'] == 0
    assert sha(post / 'reference/codec_master_routed.dcp') == sha(WORK / 'codec_master_routed.dcp')
    sim = ROOT / 'local/a13c_s05'
    assert load(sim / 'NATIVE_COMPLETION.json')['exit_code'] == 0
    for name in ['audio_input_sampler.v', 'audio_serial_slave.v']:
        assert sha(SRC / 'rtl' / name) == sha(WORK / 'inputs/rtl' / name) == sha(sim / 'inputs/rtl' / name)
    assert sha(SRC / 'tb/tb_audio_serial_slave.v') == sha(sim / 'inputs/tb/tb_audio_serial_slave.v')
    normal = (WORK / 'reports/timing.rpt').read_text(encoding='utf-8')
    section = normal.split('| Design Timing Summary', 1)[1].split('| Clock Summary', 1)[0]
    rows = re.findall(r'^\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(\d+)\s+(\d+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(\d+)\s+(\d+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(\d+)\s+(\d+)\s*$', section, re.M)
    assert len(rows) == 1
    row = rows[0]
    assert float(row[0]) >= 0 and float(row[1]) == 0 and int(row[2]) == 0
    assert float(row[4]) >= 0 and float(row[5]) == 0 and int(row[6]) == 0
    assert float(row[8]) >= 0 and float(row[9]) == 0 and int(row[10]) == 0
    post_timing = (post / 'reports/timing_original.rpt').read_text(encoding='utf-8')
    post_section = post_timing.split('| Design Timing Summary', 1)[1].split('| Clock Summary', 1)[0]
    assert ' '.join(row) in ' '.join(post_section.split())
    assert 'timing constraints are met.' in normal.lower()
    assert re.search(r'There are 0 (?:register/latch )?pins with no clock', normal)
    assert re.search(r'There are 0 pins that are not constrained for maximum delay', normal)
    critical = []
    for log in [WORK / 'native.log', *sorted((WORK / 'project/codec_master.runs').rglob('runme.log'))]:
        for line in log.read_text(encoding='utf-8', errors='replace').splitlines():
            if 'CRITICAL WARNING:' in line or line.startswith('ERROR:'):
                critical.append({'log': str(log.relative_to(WORK)), 'line': line})
    assert not critical, critical
    route = (WORK / 'reports/route.rpt').read_text(encoding='utf-8')
    routable = int(re.search(r'# of routable nets\.+\s*:\s*(\d+)', route).group(1))
    routed = int(re.search(r'# of fully routed nets\.+\s*:\s*(\d+)', route).group(1))
    errors = int(re.search(r'# of nets with routing errors\.+\s*:\s*(\d+)', route).group(1))
    assert routable == routed and errors == 0
    original_cdc = (WORK / 'reports/cdc.rpt').read_text(encoding='utf-8')
    topology = (post / 'reports/cdc_topology_view_only.rpt').read_text(encoding='utf-8')
    for content in [original_cdc, topology]:
        assert not re.search(r'^CDC-\d+\s+(Critical|Warning)\s+[1-9]', content, re.M)
    assert re.search(r'^CDC-3\s+Info\s+5\s', topology, re.M)
    assert all(name in topology for name in ['wm8960_bclk', 'wm8960_lrclk', 'wm8960_adcdat',
                                             'wm8960_iic_scl_io', 'wm8960_iic_sda_io'])
    certificate = (post / 'reports/AUDIO_SYNCHRONIZER_NETLIST_CERTIFICATE.txt').read_text(encoding='utf-8')
    assert certificate.count('ASYNC_REG=TRUE clock=clk_pl_0 DIRECT_SINGLE_FANOUT_VERIFIED') == 9
    sync_slacks = {}
    for stem in ['bclk', 'lrclk', 'adc']:
        for bit in [1, 2]:
            sync_slacks['{}_{}'.format(stem, bit)] = {}
            for mode, kind in [('max', 'Setup'), ('min', 'Hold')]:
                text = (post / 'reports' / ('sync_{}_{}_{}.rpt'.format(stem, bit, mode))).read_text(encoding='utf-8')
                values = re.findall(r'Slack\s+\((MET|VIOLATED)\)\s*:\s*(-?[\d.]+)ns', text)
                assert values and all(s == 'MET' and float(v) >= 0 for s, v in values)
                assert re.search(r'Path Type:\s+' + kind, text)
                sync_slacks['{}_{}'.format(stem, bit)][mode + '_slack_ns'] = float(values[0][1])
    static = load(E / 'static-audit-final/RESULT.json')
    controls = (WORK / 'reports/control_paths.txt').read_text(encoding='utf-8')
    slacks = {}
    for target, count, slack, requirement in re.findall(r'^(\w+) registers=(\d+) slack_ns=([\d.]+) requirement_ns=([\d.]+)$', controls, re.M):
        assert float(slack) >= 0 and float(requirement) == 10.0
        path_report = (WORK / 'reports' / ('path_' + target + '.rpt')).read_text(encoding='utf-8')
        path_slacks = re.findall(r'Slack\s+\((MET|VIOLATED)\)\s*:\s*(-?[\d.]+)ns', path_report)
        assert path_slacks and all(status == 'MET' and float(value) >= 0 for status, value in path_slacks)
        slacks[target] = {'register_bits': int(count), 'worst_setup_slack_ns': float(slack),
                          'reported_min_max_slacks_ns': [float(v) for _, v in path_slacks]}
    assert set(slacks) == {p['target'] for p in static['targeted_operation_exceptions']}
    for exception in static['targeted_operation_exceptions']:
        exception['acceptance'] = 'ACCEPTED_TARGETED_OFFLINE_ONLY_USER_AUTHORIZED_RAW_FAIL_RETAINED'
        exception['routed_timing'] = slacks[exception['target']]
        exception['simulation'] = 's05_EXACT_RTL_520_DUPLEX_FRAMES_FIVE_FAULT_CLASSES'
        exception['CDC'] = 'ORIGINAL_TIMED_AND_SEPARATE_TOPOLOGY_VIEW_CHECKED'
    gate = load(E / 'gate11.json')
    assert gate['delivery_ready'] is False
    result = {'status': 'OFFLINE_FUNCTIONAL_PHYSICAL_VERIFIED_WITH_TARGETED_EXCEPTIONS_TOOL_STYLE_OPEN',
              'implementation': {'attempt': 'b05', 'part': 'xck26-sfvc784-2LV-c', 'tool': 'Vivado 2026.1',
                  'WNS_ns': float(row[0]), 'TNS_ns': float(row[1]), 'WHS_ns': float(row[4]),
                  'THS_ns': float(row[5]), 'WPWS_ns': float(row[8]), 'TPWS_ns': float(row[9]),
                  'critical_warnings': 0, 'unrouted_nets': 0,
                  'outer_b05_exit_code': 1, 'postprocess_failure': 'UNSUPPORTED_reset_path_RETAINED',
                  'independent_same_DCP_postcheck': 'p04_exit0',
                  'xsa_sha256': sha(WORK / 'codec_master.xsa'), 'DCP_sha256': sha(WORK / 'codec_master_routed.dcp')},
              'simulation': {'attempt': 's05', 'duplex_frames': 520, 'complete_periods': 2,
                  'fault_classes': 5, 'ADC_DAC_bit_exact': True, 'DMA_full_system_cosimulation': 'NOT_TESTED'},
              'CDC': {'raw_report': 'b05/reports/cdc.rpt', 'topology_view': 'p04/reports/cdc_topology_view_only.rpt',
                  'topology_info_paths': 5, 'unsafe_paths_reported': 0, 'ASYNC_REG_audio_bits_checked': 9,
                  'original_constraints_interstage_min_max_slacks_ns': sync_slacks,
                  'MTBF_s': None, 'physical_metastability_not_simulated': True},
              'targeted_operation_exceptions': static['targeted_operation_exceptions'],
              'raw_strict_gate': {'ready': False, 'errors': gate['errors'], 'strict_warnings': gate['strict_warnings'],
                  'findings_by_rule': gate['delivery_issues_by_rule'], 'gate_sha256': sha(E / 'gate11.json')},
              'other_tool_findings': static['other_raw_findings_not_waived'],
              'case_width_checks': len(static['case_width_checks']),
              'modules': load(E / 'module-candidates-v5/RESULT.json')['status'],
              'DMA_address_period_guard_PC_checks': 11,
              'DT': load(E / 'dt-verified/RESULT.json')['status'],
              'HWH': load(E / 'hwh-b05-v2/RESULT.json')['status'],
              'BOARD': 'NOT_TESTED', 'board_connections': 0, 'audio_attempts': 0,
              'actual_current_mA': None, 'deployment_allowed': False,
              'public_static_gates': {k: v['status'] for k, v in gate['checks'].items()},
              'actual_model_settings': 'unknown', 'DeepSeek_used_for': 'Fixed pin table text only; not acceptance',
              'next': 'Board remains reserved to other task until independent postcheck and explicit release; no auto-load'}
    with (E / 'OFFLINE_REVIEW.json').open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    reasons = {'s_axis_tready_o': '握手同拍撤销ready，增加寄存级会重复接受，保留短缓存许可译码。',
        'm_axis_tdata_o': 'STOP与整帧装载的保持mux；回压负载由寄存器持有。',
        'm_axis_tlast_o': '包尾随当前负载寄存，不能用下一拍计数替代。',
        'reg_tx_command': '下降事件、声道及许可的固定译码，无命令自反馈FSM。',
        'reg_rx_command': '边界位属于旧声道，固定译码与流水对齐已重仿真。',
        'reg_rx_channel': '停机跟踪LR避免半帧重启误认边界。',
        'reg_tx_frame': '只由完整valid-ready移交写入，STOP丢弃旧帧。',
        'flag_tx_pending': '同拍接收和设备消费的所有权更新不可拆成延迟许可。',
        'reg_tx_shift': '清零/保持/装左右字/移位的短mux，末位不被边界覆盖。',
        'cnt_tx_period': '显式全宽进位后取低8位，固定模256不变。',
        'reg_rx_right': '右字包含边界LSB；与发布缓存指令共同对齐。',
        'cnt_watchdog': '用本拍饱和值限制计数，不等延迟比较结果而回绕。',
        'reg_fault': '五种独立事件逐位锁存，只有停机确认可清除。'}
    lines = ['# 逐项例外与保留的工具问题', '',
        '用户授权：允许逐项例外，以实际核验结果放行。仅适用于以下13个VG146短控制目标。',
        '全局操作预算仍为3，原始FAIL、旧失败和严格门禁delivery_ready=false均保留。',
        '本表的接受范围仅为无板候选核验；不得解释为板端部署、模拟电气或音频放行。', '',
        '| 目标 | 操作数／原门槛 | 实现后setup余量ns | 评审理由 |', '| --- | --- | --- | --- |']
    for item in result['targeted_operation_exceptions']:
        lines.append('| {} | {} / 3 | {:.3f} | {} |'.format(item['target'], item['operation_count'],
            item['routed_timing']['worst_setup_slack_ns'], reasons[item['target']]))
    lines += ['', '各目标的min/max报告、全设计STA、原始CDC和独立拓扑视图、同源RTL的s05回归均保留。', '',
        '## 不属于用户操作数例外的工具局限', '',
        '- VG066：formatter自动插入的AXI-Stream导航标签近似重复；实体功能注释已分别书写，原告警不抹除。',
        '- VG084：自动case位宽不确定；同一formatter AST补充核对46个标签位宽，实际xvlog/xelab与综合通过。',
        '- VG138：10条AMD接口属性字符串被误当成无位宽数值；AST绑定到字符串所在端口逐条复核，不修改任何数值门槛。',
        '- 文档source提取器误识别task形参及属性字符串；失败保留。正式设计端口改用同一formatter AST核对，规格经正式WaveDrom入口渲染。',
        '- 技能包完整本地自检在隔离短路径副本通过；旧长路径失败保留，安装技能本身没有改写。', '',
        '这些补充评审不把原始严格门禁改为PASS，不以本地技能包自检代替本项目RTL核验。', '']
    with (E / 'EXCEPTIONS.md').open('x', encoding='utf-8') as stream:
        stream.write('\n'.join(lines))
    summary = result['implementation']
    report = ['# WM8960 codec-master：无板核验报告', '',
        '结论：无板功能与物理实现核验已完成，含用户授权的13条操作数逐项例外；严格自动风格门禁仍未整体通过。',
        '不是上板放行：BOARD=NOT_TESTED，未连接板卡、加载位流、安装模块、录音或试音，电流仍null。', '',
        '## 实际完成的层级', '', '| 层级 | 结果与范围 |', '| --- | --- |',
        '| Python语义模型 | 5项原有测试；1024帧独立向量；源码连续性以每次INPUTS.json核对 |',
        '| 新时钟离散模型 | 4项：四拍等待扫查、两拍负例、正窗口与慢系统时钟拒绝；MTBF未测 |',
        '| 真实RTL仿真 | xsim2026.1 s05；520帧双向逐位比较、2周期TLAST、5类故障；额外偏斜/回压/清错/重同步/复位检查 |',
        '| 综合／布局布线 | Vivado2026.1 b05，xck26-sfvc784-2LV-c；实际bit/XSA/routed DCP，BD关键警告0，布线错误0；外层后处理exit1保留，p04同一DCP补验exit0 |',
        '| 时序 | WNS={:.3f}ns，TNS={:.3f}ns；WHS={:.3f}ns，THS={:.3f}ns；WPWS={:.3f}ns |'.format(
            summary['WNS_ns'], summary['TNS_ns'], summary['WHS_ns'], summary['THS_ns'], summary['WPWS_ns']),
        '| CDC | 原始约束报告及clock interaction保留；9个音频ASYNC_REG、逐级直连/唯一扇出/同钟证书及6条级间min/max；另有仅分析用的5条Info拓扑视图，未报告Warning/Critical |',
        '| 驱动 | 3个真实AArch64模块、vermagic6.8.12-a10irq2；真实内核格式翻转PC执行7项，DMA地址/周期C拒绝条件执行11项；未probe或装载 |',
        '| 设备树 | 在原irq2备份上真实编译/合并，全部11个新增节点disabled；实际HWH核对地址、IRQ、时钟、完整流接口 |',
        '| 文档工具 | WaveDrom3.6.1实际渲染三个模块规格；技能包隔离短路径本地自检通过，不代表项目RTL风格通过 |',
        '| BOARD／电气／声学 | 全部NOT_TESTED，完整PS/DDR/AXI DMA协同仿真也未运行 |', '',
        '## 逐项例外与工具局限', '',
        '见EXCEPTIONS.md及OFFLINE_REVIEW.json。13条VG146原始FAIL不删除，操作预算仍为3；每条都有同源重仿真及真实min/max和CDC证据。',
        '额外VG066导航注释、VG084 concat求宽与10条VG138属性字符串问题保留原判定，补充评审不改写严格门禁。', '',
        '| 原始公开门禁 | 状态 |', '| --- | --- |']
    report += ['| {} | {} |'.format(k, v) for k, v in result['public_static_gates'].items()]
    report += ['', '上表testbench/toolchain的not_requested是静态门禁自身的状态；实际xsim/综合/实现证据单独列在上方，不能互相冒充。', '',
        '## 保留的失败与修复', '',
        '- b01：BD实例名config为HDL保留字，未综合；更名csr，旧输入/退出码保留。',
        '- b02：XDC中的foreach/if未被正式接受，三个异步入口产生负余量；位流虽生成仍判失败，不继承其时序。',
        '- b03：两拍等待版得到正STA，但离散相位反例显示跨链等待偏紧；后来四拍版重新仿真、综合实现。',
        '- b03/b04：逐根信号接通而正式AXIS元数据/接口连接不完整，3条BD关键警告保留；最终版完整S_AXIS/M_AXIS消除。',
        '- b04：一个AMD Tcl app-loader子任务在create_project阶段报Could not open C for writing，未进入该模块综合；真实退出后仅归档本任务预约。原因未据此证明，未修改安装环境；最终版使用干净工程默认缓存重建。',
        '- b05：实现及XSA/DCP导出完成后，补充CDC脚本的reset_path命令不受支持，外层exit1原样保留；p01/p02只有IIC报告、音频拓扑未被自动覆盖，复核拒绝；p03实际获得全部5条Info及网表证书，但min_max/max_paths1仅选出保持路径，复核再次拒绝；p04分别报告12条setup/hold路径后通过，未改逻辑或重导出。',
        '- 驱动最初派生导出标记及DAI probe API不匹配、CPU端主从格式未翻转均保留；v4修格式，v5增加32位起始地址与对齐拒绝，避免u64加法回绕绕过检查；旧格式和旧回绕反例被真实C执行复现。',
        '- HWH检查器最初把0x0与0作字符串比较；修成整数比较并检查真实参数名，原失败保留。',
        '- 完整AXIS绑定后，HWH将可选TKEEP省略于DMA的PORTS；从4位常量源的CONNECTIONS核对目标及15数值，并保留生成HDL，先前StopIteration失败保留。',
        '- 文档提取器误认task形参及属性；采用同一formatter AST核对真实设计端口，正式no-source入口渲染已确认合同，不伪造端口。',
        '- 技能包长路径失败及收集器误用stdout.log失败保留；分别在隔离短路径、正确stdout.txt下补验，不改安装技能。', '',
        '## 仍不放行的项目', '',
        '保留4条IIC缺外部延迟、3条零分类延迟等methodology提示，以及PS/SmartConnect AWUSER/ARUSER元数据宽度提示和供应商优化告警。',
        '不填虚假IIC电气延迟，不豁免新的板端告警。实际IIC边沿/上拉、电压/电流、24MHz与PLL、BCLK/LR及板外setup/hold、Linux DMA/IRQ和恢复仍需静默实测。',
        'p03的BCLK源自身输入延迟被忽略提示保留；p04仅对LR/ADC设置分类延迟。重读原约束的供应商waiver重复提示保留，拓扑报告使用-no_waiver；分析视图没有被用于STA、实现或导出。',
        '对应原因及安全方法见source-final/MEASUREMENTS.md。当前永久EPERM驱动及disabled设备树不得直接改字段解锁开流。', '',
        '## 回滚与产物', '',
        '实际工具快照和每次INPUTS、completion、日志见native-tools；最终产物在native-tools/b05/artifacts，禁止本轮加载。',
        'XSA SHA256：`{}`。'.format(summary['xsa_sha256']),
        'routed DCP SHA256：`{}`。'.format(summary['DCP_sha256']),
        '旧a06、982项旧封存证据及2266项私有TTS包校验保持不变；不复制或发布权重。共享文档仅新增本轮A13内容，不覆盖TT10。',
        '没有本轮板端变更需要撤销。未来回滚不能盲目加载输出时钟的旧a06，必须先解除与codec master的双驱动风险。',
        '下一步仍等待另一任务独立后检及明确释放，并在新鲜身份、原件备份、唯一租约/双锁和新的调试窗口下推进；本轮不自动进入BOARD。', '',
        'actual_model_settings=unknown；无协作子代理；DeepSeek只用于固定引脚表文本，不参与架构、RTL、驱动或证据验收。', '']
    with (E / 'REPORT.md').open('x', encoding='utf-8') as stream:
        stream.write('\n'.join(report))
    print(json.dumps({'status': result['status'], 'implementation': result['implementation'],
                      'exceptions': len(slacks), 'BOARD': 'NOT_TESTED', 'deployment_allowed': False}))


if __name__ == '__main__':
    main()
