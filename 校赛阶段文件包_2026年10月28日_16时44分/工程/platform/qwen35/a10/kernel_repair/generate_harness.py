"""Generate exact-function native test inputs, validating candidate manifest."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_kernel_refs_pc import function


def generate(bundle, output):
    manifest = json.loads((bundle / 'manifest.json').read_text(encoding='utf-8'))
    texts = {}
    parent_texts = {}
    for kind in ['original', 'candidate']:
        chunks = []
        for name, names in [('drivers/of/irq.c', ['of_irq_parse_one', 'irq_of_parse_and_map']),
                            ('drivers/irqchip/irq-xilinx-intc.c', ['xilinx_intc_of_remove'])]:
            data = (bundle / kind / name).read_bytes()
            if hashlib.sha256(data).hexdigest() != manifest['files'][name][kind + '_sha256']:
                raise ValueError('source/manifest mismatch')
            text = data.decode('utf-8')
            chunks.extend(function(text, symbol)['text'] for symbol in names)
        texts[kind] = '\n\n'.join(chunks) + '\n'
        name = 'drivers/irqchip/irqchip.c'
        data = (bundle / kind / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != manifest['files'][name][kind + '_sha256']:
            raise ValueError('parent source/manifest mismatch')
        text = data.decode('utf-8')
        text = text[text.index('#else\nstatic void a10_irqchip_parent_put' if kind == 'candidate'
                               else '#else\nint platform_irqchip_probe'):]
        names = (['a10_irqchip_parent_put'] if kind == 'candidate' else [])
        names += ['platform_irqchip_probe', 'platform_irqchip_remove']
        parent_texts[kind] = '\n\n'.join(function(text, n)['text'] for n in names) + '\n'
    output.mkdir(parents=True, exist_ok=False)
    for kind, text in texts.items():
        target = output / kind
        target.mkdir()
        with (target / 'functions.inc').open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(text)
        with (target / 'parent_functions.inc').open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(parent_texts[kind])
    print(json.dumps(dict(generated=str(output), board_access=False)))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--bundle', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    generate(args.bundle, args.output)
