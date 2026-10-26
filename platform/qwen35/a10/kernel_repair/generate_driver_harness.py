"""Extract actual reviewed functions, checking both source snapshots first."""
import argparse
import hashlib
import json
from pathlib import Path
from prepare_driver import function


def generate(bundle, output):
    manifest = json.loads((bundle/'manifest.json').read_text())
    texts = {}
    for kind in ['original', 'candidate']:
        for name, row in manifest['files'].items():
            raw = (bundle/kind/name).read_bytes()
            if hashlib.sha256(raw).hexdigest() != row[kind+'_sha256']:
                raise ValueError('Source snapshot mismatch')
            texts[kind, name] = raw.decode()
    output.mkdir(parents=True, exist_ok=False)
    for kind in ['original', 'candidate']:
        folder = output/kind
        folder.mkdir()
        names = ['zintc_isr', 'zocl_irq_intc_add']
        if kind == 'candidate':
            names += ['a10_irq_release_locked']
        names += ['zocl_irq_intc_remove', 'zocl_irq_intc_config', 'zintc_remove']
        with (folder/'irq_functions.inc').open('x') as f:
            f.write('\n\n'.join(function(texts[kind, 'zert/zocl_xgq_intc.c'], n)['text'] for n in names))
        with (folder/'cu_functions.inc').open('x') as f:
            f.write('\n\n'.join(function(texts[kind, 'common/cu.c'], n)['text'] for n in ['cu_probe', 'cu_remove']))
    print('Exact-function harness inputs generated; not a kernel or board simulation')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bundle', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    generate(a.bundle, a.output)
