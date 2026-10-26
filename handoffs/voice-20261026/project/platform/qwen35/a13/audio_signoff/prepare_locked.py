"""A-owned derived bind-only revision: no clock/config writes in hw_params.

Leaves old sealed sources and the matching kernel unchanged. This is NOT a
streaming implementation, a CDC waiver, an installer, or a deployable release.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[4]
BASE = Path('/home/member-a/a10-kernel-irq2-20261021-v1')
OLD = ROOT / 'platform/qwen35/a13/audio_pl'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def derive_card(text):
    start = text.index('\tstruct snd_soc_pcm_runtime *rtd = substream->private_data;', text.index('static int a13_params('))
    end = text.index('\n}\n', start)
    return text[:start] + '''\t/* No latent AUTO-PLL or CPU-clock setup in a bind-only release.
	 * A future common-clock streaming candidate is a separate design.
	 */
	return -EPERM;''' + text[end:]


def derive_formatter(text, derive):
    text = derive(text)
    marker = 'static const struct snd_soc_component_driver xlnx_asoc_component = {'
    guard = '''static int a13_locked_params(struct snd_soc_component *c,
		struct snd_pcm_substream *s, struct snd_pcm_hw_params *p)
{
	/* No Fs-multiplier update is reachable through this callback. */
	return -EPERM;
}
'''
    assert text.count(marker) == 1
    text = text.replace(marker, guard + marker, 1)
    old = '.hw_params\t= xlnx_formatter_pcm_hw_params,'
    assert text.count(old) == 1
    text = text.replace(old, '.hw_params\t= a13_locked_params,', 1)
    text = text.replace('static int xlnx_formatter_pcm_hw_params(',
                        'static int __maybe_unused xlnx_formatter_pcm_hw_params(', 1)
    return text


def main():
    spec = importlib.util.spec_from_file_location('a13_old_derive', OLD / 'prepare_modules.py')
    old = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(old)
    original = BASE / 'source/sound/soc/xilinx/xlnx_formatter_pcm.c'
    assert sha(original) == 'cd6ec9b958fea83b698cbb1d4b7c67ed132d380e498916cb63b9da5b059c0903'
    out = Path('modules')
    out.mkdir(exist_ok=False)
    shutil.copyfile(original, out / 'xlnx_formatter_original.c')
    (out / 'a13_formatter_pcm.c').write_text(derive_formatter(original.read_text(), old.derive))
    (out / 'a13_wm8960_card.c').write_text(derive_card((OLD / 'a13_wm8960_card.c').read_text()))
    for source in ['sound/soc/xilinx/xlnx_snd_common.h', 'sound/soc/codecs/wm8960.h']:
        shutil.copyfile(BASE / 'source' / source, out / Path(source).name)
    (out / 'Makefile').write_text('obj-m += a13_formatter_pcm.o\nobj-m += a13_wm8960_card.o\n')
    data = {'maintainer': 'A', 'kernel_source_modified': False, 'installed': False,
            'profile': 'BIND_ONLY_ALWAYS_EPERM_OPEN_PARAMS_TRIGGER_NO_AUDIO',
            'clock_topology': 'UNRESOLVED_NOT_IMPLEMENTED_FOR_STREAMING',
            'sources': {str(p): sha(p) for p in [original, OLD / 'prepare_modules.py', OLD / 'a13_wm8960_card.c']},
            'files': {p.name: sha(p) for p in out.iterdir() if p.is_file()}}
    with (out / 'SOURCE_MANIFEST.json').open('x') as stream:
        json.dump(data, stream, indent=2)
        stream.write('\n')
    print(json.dumps({key: value for key, value in data.items() if key not in ['files', 'sources']}))


if __name__ == '__main__':
    main()
