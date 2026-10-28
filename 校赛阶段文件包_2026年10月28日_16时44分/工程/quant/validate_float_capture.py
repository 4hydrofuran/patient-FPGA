"""Recompute captured linear outputs from raw BF16 tensor bytes, one layer at a time.

This tests source orientation/capture, NOT W4A8 accuracy or independent B reference.
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import torch
from model_audit import ROOT, sha, tensor_header


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--capture', type=Path, required=True)
    ap.add_argument('--audit', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    with a.out.open('x', encoding='utf-8') as report:
        m = json.loads((a.capture / 'manifest.json').read_text())
        audit = json.loads(a.audit.read_text())
        if (m['stage'] != 'original' or m['original_weight_sha256'] != audit['source_sha256']
                or (a.capture / 'INCOMPLETE').exists()):
            raise ValueError('incompatible or incomplete capture')
        rows = {r['source_tensor']: r for r in audit['tensors']}
        source = ROOT / 'platform/local/a1/model/model.safetensors'
        if sha(source) != audit['source_sha256']:
            raise ValueError('source changed')
        header, base = tensor_header(source)
        torch.set_num_threads(4)
        results, states = [], {}

        def read(item):
            if Path(item['file']).name != item['file'] or item['dtype'] != 'float32_le':
                raise ValueError('capture path/dtype invalid')
            p = a.capture / item['file']
            if p.is_symlink() or sha(p) != item['sha256']:
                raise ValueError('capture hash invalid')
            x = np.fromfile(p, dtype='<f4').reshape(item['shape'])
            if not np.isfinite(x).all():
                raise ValueError('nonfinite capture')
            return torch.from_numpy(x)

        with source.open('rb') as f, torch.inference_mode():
            for item in m['activations']:
                name = f"model.layers.{item['layer']}.mlp.{item['projection']}_proj.weight"
                row = rows[name]
                lo, hi = header[name]['data_offsets']
                f.seek(base + lo)
                raw = bytearray(f.read(hi - lo))
                if hashlib.sha256(raw).hexdigest() != row['source_tensor_sha256']:
                    raise ValueError('tensor changed')
                w = torch.frombuffer(raw, dtype=torch.bfloat16).reshape(row['logical_shape_N_K']).float()
                x, y = read(item['input']), read(item['original_fp32_output'])
                actual = torch.nn.functional.linear(x, w)
                error = (actual - y).double()
                results.append(dict(layer=item['layer'], projection=item['projection'],
                                    max_abs_error=error.abs().max().item(), rmse=error.square().mean().sqrt().item(),
                                    input_shape=list(x.shape), output_shape=list(actual.shape)))
                states[(item['layer'], item['projection'])] = (x, y)
                del raw, w, actual
            topology = []
            for layer in sorted({i['layer'] for i in m['activations']}):
                gx, gy = states[(layer, 'gate')]
                ux, uy = states[(layer, 'up')]
                dx, _ = states[(layer, 'down')]
                if not torch.equal(gx, ux):
                    raise ValueError('gate/up inputs are not shared normalized activation')
                error = (torch.nn.functional.silu(gy) * uy - dx).abs().max().item()
                topology.append(dict(layer=layer, gate_up_input_bytes_equal=True, swiglu_input_max_abs_error=error))
        result = dict(status='FLOAT_ORIENTATION_DIAGNOSTIC_ONLY', threads=4,
                      linear_results=results, topology=topology, threshold=None,
                      quantization_error='NOT_MEASURED', hardware_error='NOT_MEASURED',
                      independent_b_reference=False, a2='NOT_PASSED')
        json.dump(result, report, indent=2)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
