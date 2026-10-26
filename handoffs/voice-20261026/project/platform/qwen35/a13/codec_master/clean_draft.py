"""对已保存原稿作有限机械整理；功能/质量结论仍由独立门禁给出。"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
WIDTHS = {'reg_tx_frame': 32, 'flag_tx_pending': 1, 'flag_tx_started': 1,
          'reg_tx_shift': 16, 'reg_tx_right': 16, 'reg_tx_channel': 1,
          'cnt_tx_period': 8, 'reg_rx_channel': 1, 'flag_rx_locked': 1,
          'cnt_rx_bits': 5, 'reg_rx_shift': 16, 'reg_rx_left': 16,
          'cnt_rx_period': 8, 'cnt_watchdog': 16, 'reg_fault': 5,
          'rx_tdata_o': 32, 'rx_tvalid_o': 1, 'rx_tlast_o': 1, 'dacdat_o': 1}
ZERO_COMMENTS = {
    'reg_tx_frame': ['播放预取内容复位', '停机丢弃未发样本'],
    'flag_tx_pending': ['初始缓存没有归属帧', '停止时撤销DMA预取归属', '左帧已消费释放缓存'],
    'flag_tx_started': ['尚未遇到起播左边界', '停止或故障后撤销播放对齐'],
    'reg_tx_shift': ['串行发送器初始全零', '禁止运行时清除未发声道'],
    'reg_tx_right': ['复位右字保留区', '停机不承接旧帧右字'],
    'reg_tx_channel': ['发送边界历史初始为左'],
    'cnt_tx_period': ['DMA包内索引归首帧', '播放停止后下次从新包计数'],
    'reg_rx_channel': ['接收边界历史从右开始', '等待下一完整左声道起点'],
    'flag_rx_locked': ['接收器尚未建立帧同步', '采集关闭后撤销左右配对'],
    'cnt_rx_bits': ['槽内序号初始为零', '停止时清除残留位序', '边界末位已采样完成'],
    'reg_rx_shift': ['录音移位器初始无内容', '关闭时丢弃未完成声道', '上一声道末位已经送出'],
    'reg_rx_left': ['左声道暂存初始全零', '采集停止不保留跨窗口样本'],
    'cnt_rx_period': ['录音包从第一帧开始', '重新采集时包位置归零'],
    'cnt_watchdog': ['失钟检测年龄复位', '无使能不累计失钟时间', '收到位边沿刷新失钟年龄'],
    'reg_fault': ['复位清除全部诊断锁存', '停止后的显式故障确认'],
    'rx_tdata_o': ['对外录音负载初始全零', '软件停止后清除旧DMA负载'],
    'rx_tvalid_o': ['初始录音接口不持有有效帧', '停机后撤销录音接口归属', 'S2MM握手完成释放有效帧'],
    'rx_tlast_o': ['复位未持有包尾标记', '停止撤销前一包尾归属'],
    'dacdat_o': ['DAC数字输出初始为零', '禁止播放时输出数字静默位'],
}
ONE_COMMENTS = {'flag_tx_pending': 'DMA已交付一帧待发样本', 'flag_rx_locked': '完整左帧起点已到达',
                'rx_tvalid_o': '设备完成的立体声帧等待内存端'}
FAULT_COMMENTS = ['位时钟长时间没有边沿', '槽宽或LR位置异常', '播放缺少下一帧', '录音缓存来不及释放', '发送DMA周期包尾不匹配']


def sized(value, width):
    return str(width) + "'b" + format(value, '0' + str(width) + 'b')


def main():
    path = ROOT / 'rtl/audio_serial_slave.v'
    text = path.read_text(encoding='utf-8')
    text = text.replace('clear_fault', 'ack_errors')
    for name, width in WIDTHS.items():
        text = re.sub(r'\b' + name + r' = ([01]);',
                      lambda m: name + ' = ' + sized(int(m[1]), width) + ';', text)
    lines = []
    slot_comments = ['LR切换早于第十六位', '第十六位后仍没有LR切换']
    for line in text.splitlines():
        match = re.fullmatch(r'(\s*)(\w+)(\[\d+\])? <= ([01]);', line)
        if match:
            indent, name, selected, value = match.groups()
            width = 1 if selected else WIDTHS[name]
            if selected:
                index = int(selected[1:-1])
                comment = slot_comments.pop(0) if index == 1 else FAULT_COMMENTS[index]
            elif name == 'reg_rx_channel':
                comment = ZERO_COMMENTS[name].pop(0)
            elif value == '0':
                comment = ZERO_COMMENTS[name].pop(0)
            else:
                comment = ONE_COMMENTS[name]
            line = indent + name + (selected or '') + ' <= ' + sized(int(value), width) + '; // ' + comment
        lines.append(line)
    text = '\n'.join(lines) + '\n'
    for old, new in [("8'b0", "8'b00000000"), ("8'd1", "8'b00000001"),
                     ("5'd1", "5'b00001"), ("16'd1", "16'b0000000000000001"),
                     ("5'd15", "5'b01111")]:
        text = re.sub(re.escape(old) + r'(?![0-9a-fA-F])', new, text)
    with path.open('w', encoding='utf-8', newline='\n') as stream:
        stream.write(text)
    print('Finite literal/comment transformation applied; rerun independent gates')


if __name__ == '__main__':
    raise SystemExit('Historical failed-draft helper is retired; do not apply it to the final pipelined RTL.')
