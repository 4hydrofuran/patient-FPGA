"""在PC编译执行匹配内核的真实格式翻转函数及候选纯回调；不是板端probe。"""
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[4]
KERNEL = Path('/home/member-a/a10-kernel-irq2-20261021-v1/source')
E = ROOT / 'evidence/a13_A/20261025-audio-codec-master-v1/dai-format-pc'
OLD = Path('/home/member-a/kv260-build/ra02-coordinator/work/01792895414441877711-A-a13-codecmaster-modules-api-dfce43e2/modules/a13_serial_dai.c')


def function(text, signature):
    begin = text.index(signature)
    end = text.index('\n}\n', begin) + 3
    return text[begin:end]


def main():
    E.mkdir(exist_ok=False)
    paths = [KERNEL / 'sound/soc/soc-core.c', KERNEL / 'include/sound/soc-dai.h',
             KERNEL / 'include/uapi/sound/asoc.h', Path(__file__).resolve().parent / 'drivers/a13_serial_dai.c',
             Path(__file__).resolve().parent / 'drivers/a13_codec_card.c', OLD]
    texts = [p.read_text(encoding='utf-8') for p in paths]
    needed = ['SND_SOC_DAI_FORMAT_I2S', 'SND_SOC_DAIFMT_I2S', 'SND_SOC_DAIFMT_NB_NF',
              'SND_SOC_DAIFMT_CBP_CFP', 'SND_SOC_DAIFMT_CBP_CFC', 'SND_SOC_DAIFMT_CBC_CFP',
              'SND_SOC_DAIFMT_CBC_CFC', 'SND_SOC_DAIFMT_CLOCK_PROVIDER_MASK']
    definitions = []
    for name in needed:
        matches = re.findall(r'^#define\s+' + name + r'\s+[^\n]+', texts[1] + '\n' + texts[2], re.M)
        assert len(matches) == 1, name
        definitions.extend(matches)
    flip = function(texts[0], 'unsigned int snd_soc_daifmt_clock_provider_flipped(')
    startup = function(texts[3], 'static int a13_startup(')
    deny = function(texts[4], 'static int a13_deny_start(')
    cmain = '''
#define VERIFY(condition) do { if (!(condition)) { printf("FAIL line=%d\\n", __LINE__); return 1; } } while (0)
int main(void) {
    unsigned int link = SND_SOC_DAIFMT_I2S | SND_SOC_DAIFMT_NB_NF | SND_SOC_DAIFMT_CBP_CFP;
    unsigned int cpu = snd_soc_daifmt_clock_provider_flipped(link);
    VERIFY((cpu & SND_SOC_DAIFMT_CLOCK_PROVIDER_MASK) == SND_SOC_DAIFMT_CBC_CFC);
    VERIFY(a13_set_fmt(0, cpu) == 0);
    VERIFY(a13_set_fmt(0, link) == -EINVAL);
    VERIFY(a13_set_fmt(0, cpu ^ (1 << 8)) == -EINVAL);
    VERIFY(a13_set_fmt(0, snd_soc_daifmt_clock_provider_flipped(cpu)) == -EINVAL);
    VERIFY(a13_startup(0, 0) == -EPERM);
    VERIFY(a13_deny_start(0) == -EPERM);
    puts("PASS actual-kernel-flip-and-driver-pure-callbacks checks=7 NOT_BOARD_PROBE");
    return 0;
}
'''
    commands = []
    for name, driver, expected in [('old', texts[5], 1), ('fixed', texts[3], 0)]:
        code = ('#include <errno.h>\n#include <stdio.h>\nstruct snd_soc_dai;\nstruct snd_pcm_substream;\n' +
                '\n'.join(definitions) + '\n' + flip + '\n' +
                function(driver, 'static int a13_set_fmt(') + '\n' + startup + '\n' + deny + cmain)
        source = E / (name + '.c')
        source.write_text(code, encoding='utf-8')
        for argv, wanted in [(['gcc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Wno-unused-parameter',
                               '-Werror', str(source), '-o', str(E / name)], 0), ([str(E / name)], expected)]:
            result = subprocess.run(argv, capture_output=True, text=True)
            entry = {'argv': argv, 'exit_code': result.returncode, 'expected_exit_code': wanted,
                     'stdout': result.stdout, 'stderr': result.stderr}
            commands.append(entry)
            (E / 'COMMANDS.json').write_text(json.dumps(commands, indent=2) + '\n', encoding='utf-8')
            assert result.returncode == wanted, entry
    value = {'status': 'PASS_PC_ACTUAL_PURE_CALLBACKS_OLD_REJECTION_REPRODUCED', 'checks': 7,
             'original_wrong_CPU_format_exit_code': 1, 'fixed_exit_code': 0,
             'inputs': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
             'BOARD_probe': 'NOT_TESTED', 'kernel_module_loaded': False}
    (E / 'RESULT.json').write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(value))


if __name__ == '__main__':
    main()
