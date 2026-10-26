"""从匹配irq2内核派生独立DMA模块；仅离线输出，不修改内核或安装。"""
import difflib
import hashlib
import json
from pathlib import Path
import shutil

SRC = Path('/home/member-a/a10-kernel-irq2-20261021-v1/source')
ROOT = Path(__file__).resolve().parent
EXPECTED = 'cfe246984c760346a800c7e40a0f4bfada68e72ddc704e4daf99eca5b20e30b2'


def main():
    out = Path.cwd() / 'modules'
    out.mkdir(exist_ok=False)
    source = SRC / 'drivers/dma/xilinx/xilinx_dma.c'
    assert hashlib.sha256(source.read_bytes()).hexdigest() == EXPECTED
    original = source.read_text()
    text = original.replace('#include "../dmaengine.h"', '#include "internal_dmaengine.h"')
    begin = text.index('static struct dma_async_tx_descriptor *xilinx_dma_prep_dma_cyclic(')
    end = text.index('/**', begin)
    old = text[begin:end]
    new = old.replace('if (!period_len)',
        '/* A13 fixed 1024-byte periods, 2..64 periods, 32-bit DMA only. */\n'
        '\tif (period_len != 1024 || buf_len % period_len ||\n'
        '\t    buf_len / period_len < 2 || buf_len / period_len > 64 ||\n'
        '\t    ((u64)buf_addr & 3) || (u64)buf_addr >= (1ULL << 32) ||\n'
        '\t    (u64)buf_addr + buf_len > (1ULL << 32))')
    needle = '\t\t\thw->control = copy;'
    assert new.count(needle) == 1
    new = new.replace(needle, needle + '\n\n'
        '\t\t\t/* One packet and IOC boundary per ALSA period, not ring. */\n'
        '\t\t\tif (direction == DMA_MEM_TO_DEV) {\n'
        '\t\t\t\tif (!sg_used)\n'
        '\t\t\t\t\thw->control |= XILINX_DMA_BD_SOP;\n'
        '\t\t\t\tif (sg_used + copy == period_len)\n'
        '\t\t\t\t\thw->control |= XILINX_DMA_BD_EOP;\n\t\t\t}')
    obsolete = ('\t/* For the last DMA_MEM_TO_DEV transfer, set EOP */\n'
        '\tif (direction == DMA_MEM_TO_DEV) {\n'
        '\t\thead_segment->hw.control |= XILINX_DMA_BD_SOP;\n'
        '\t\tsegment->hw.control |= XILINX_DMA_BD_EOP;\n\t}\n')
    assert new.count(obsolete) == 1
    new = new.replace(obsolete, '')
    text = text[:begin] + new + text[end:]
    start = text.index('static const struct of_device_id xilinx_dma_of_ids[] = {')
    finish = text.index('};', start) + 2
    text = text[:start] + ('static const struct of_device_id xilinx_dma_of_ids[] = {\n'
        '\t{ .compatible = "patientqwen,a13-period-dma", .data = &axidma_config },\n'
        '\t{}\n};') + text[finish:]
    text = text.replace('EXPORT_SYMBOL(xilinx_vdma_channel_set_config);',
                         '/* Private candidate: do not duplicate built-in export. */')
    text = text.replace('xilinx_vdma_channel_set_config', 'a13_vdma_channel_set_config')
    text = text.replace('int a13_vdma_channel_set_config(', 'static int __maybe_unused a13_vdma_channel_set_config(')
    text = text.replace('.name = "xilinx-vdma"', '.name = "a13-period-dma"')
    assert 'EXPORT_SYMBOL' not in text
    (out / 'a13_period_dma.c').write_text(text)
    shutil.copyfile(SRC / 'drivers/dma/dmaengine.h', out / 'internal_dmaengine.h')
    for name in ['a13_serial_dai.c', 'a13_codec_card.c', 'Makefile']:
        shutil.copyfile(ROOT / 'drivers' / name, out / name)
    shutil.copyfile(SRC / 'sound/soc/codecs/wm8960.h', out / 'wm8960.h')
    (Path.cwd() / 'DMA_DERIVATION.patch').write_text(''.join(difflib.unified_diff(
        original.splitlines(True), text.splitlines(True), fromfile='matching-kernel/xilinx_dma.c',
        tofile='private-module/a13_period_dma.c')))
    manifest = {'upstream_sha256': EXPECTED, 'kernel': '6.8.12-a10irq2',
        'compatible': 'patientqwen,a13-period-dma', 'period_bytes': 1024, 'DMA_address_bits': 32,
        'installed': False, 'BOARD': 'NOT_TESTED', 'actual_power_current_mA': None,
        'files': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir()}}
    (Path.cwd() / 'DMA_DERIVATION.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(manifest))


if __name__ == '__main__':
    main()
