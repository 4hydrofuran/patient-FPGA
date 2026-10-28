"""Compare aligned observations, separating quantization from hardware error.

Metric reporting only: no invented acceptance threshold and no model loading.
"""
import argparse
import json
from pathlib import Path
import numpy as np
from model_audit import sha


def load(directory):
    if (directory / 'INCOMPLETE').exists():
        raise ValueError('incomplete observation')
    m = json.loads((directory / 'manifest.json').read_text())
    item = m['logits']
    p = directory / item['file']
    if Path(item['file']).name != item['file'] or p.is_symlink():
        raise ValueError('invalid logits path')
    if item['dtype'] != 'float32_le' or sha(p) != item['sha256']:
        raise ValueError('logits dtype/hash mismatch')
    expected = [len(m['positions']), m['vocab_size']]
    if item['shape'] != expected or min(expected) < 1 or p.stat().st_size != expected[0] * expected[1] * 4:
        raise ValueError('logits shape/size mismatch')
    if len(set(m['positions'])) != len(m['positions']) or any(type(x) is not int or x < 0 or x >= len(m['context_token_ids']) for x in m['positions']):
        raise ValueError('invalid token positions')
    return m, np.memmap(p, dtype='<f4', mode='r', shape=tuple(expected))


def compare_meta(a, b, kind):
    if a.get('schema') != 'a2-float-observation-0.1':
        raise ValueError('unsupported observation schema')
    for key in ('schema', 'model_revision', 'original_weight_sha256', 'token_ids_sha256',
                'chat_template_sha256', 'prompt_sha256', 'context_token_ids', 'positions', 'vocab_size'):
        if a[key] != b[key]:
            raise ValueError('incompatible observation: ' + key)
    if kind != 'diagnostic':
        # A standalone HF capture cannot silently become a llama.cpp quality
        # baseline. A3 supplies this shared, reviewed full-graph protocol.
        for key in ('engine_commit', 'non_mlp_model_sha256', 'evaluation_protocol'):
            if not a.get('comparison_basis', {}).get(key) or a['comparison_basis'][key] != b.get('comparison_basis', {}).get(key):
                raise ValueError('comparison basis missing/different: ' + key)
    stages = (a['stage'], b['stage'])
    if kind == 'quantization':
        if stages != ('original', 'sidecar_cpu') or not b.get('sidecar_sha256'):
            raise ValueError('quantization comparison requires original vs sidecar_cpu')
    elif kind == 'hardware':
        if stages != ('sidecar_cpu', 'sidecar_fpga') or not a.get('sidecar_sha256') or a['sidecar_sha256'] != b.get('sidecar_sha256'):
            raise ValueError('hardware comparison requires identical sidecar')
    elif kind == 'diagnostic':
        if a['stage'] != b['stage'] or a.get('sidecar_sha256') != b.get('sidecar_sha256'):
            raise ValueError('diagnostic requires same stage and sidecar identity')
    else:
        raise ValueError('unknown comparison kind')


def metrics(a, b):
    if a.shape != b.shape or a.ndim != 2 or min(a.shape) < 1:
        raise ValueError('invalid array shapes')
    max_abs = sq = cosine = kl = agreement = 0.0
    for ra, rb in zip(a, b):
        x, y = np.asarray(ra, dtype=np.float64), np.asarray(rb, dtype=np.float64)
        if not np.isfinite(x).all() or not np.isfinite(y).all():
            raise ValueError('nonfinite logits')
        diff = x - y
        max_abs = max(max_abs, float(np.abs(diff).max()))
        sq += float(np.dot(diff, diff))
        nx, ny = np.linalg.norm(x), np.linalg.norm(y)
        cosine += float(np.dot(x, y) / (nx * ny)) if nx and ny else float(not nx and not ny)
        lx, ly = x - x.max(), y - y.max()
        lx -= np.log(np.exp(lx).sum())
        ly -= np.log(np.exp(ly).sum())
        kl += float(np.sum(np.exp(lx) * (lx - ly)))
        agreement += float(np.argmax(x) == np.argmax(y))
    return dict(max_abs_error=max_abs, rmse=(sq / a.size) ** 0.5,
                mean_cosine=cosine / len(a), mean_kl_reference_to_candidate=kl / len(a),
                top1_agreement=agreement / len(a), threshold=None, accepted=None)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('reference', type=Path)
    ap.add_argument('candidate', type=Path)
    ap.add_argument('--kind', choices=['diagnostic', 'quantization', 'hardware'], required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    with args.out.open('x', encoding='utf-8') as out:
        ma, a = load(args.reference)
        mb, b = load(args.candidate)
        compare_meta(ma, mb, args.kind)
        result = dict(kind=args.kind, metrics=metrics(a, b),
                      reference_manifest_sha256=sha(args.reference / 'manifest.json'),
                      candidate_manifest_sha256=sha(args.candidate / 'manifest.json'),
                      note='Same teacher-forced context/positions required; not medical quality or G1/A2 acceptance')
        json.dump(result, out, indent=2)
    print(json.dumps(result))
