"""Capture real, UNQUANTIZED inputs using one original-weight HF CPU model.

Not a B golden, not a sidecar, not a board benchmark, not an A3 runtime.
"""
import argparse
import inspect
import json
import os
from pathlib import Path
import time

from model_audit import ROOT, sha


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--report', type=Path, required=True)
    ap.add_argument('--threads', type=int, default=4)
    a = ap.parse_args()
    if not 1 <= a.threads <= 8:
        raise ValueError('threads must be 1..8')
    if a.out.exists() or a.report.exists():
        raise FileExistsError('new output/report paths required')
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    import numpy as np
    import torch
    import transformers
    from transformers import AutoModelForCausalLM
    if transformers.__version__ != '4.57.6':
        raise RuntimeError('review a different Transformers implementation before capturing')
    pins = json.loads((ROOT / 'platform/a1/pins.json').read_text())
    model_dir = ROOT / 'platform/local/a1/model'
    if sha(model_dir / 'model.safetensors') != pins['model']['weight_sha256']:
        raise ValueError('original source hash mismatch')
    fixture = ROOT / 'bench/runtime/s0/fixture'
    fm = json.loads((fixture / 'manifest.json').read_text())
    for name, expected in fm['sha256'].items():
        if sha(fixture / name) != expected:
            raise ValueError('fixture changed: ' + name)
    ids = [int(x) for x in (fixture / 'tokens.txt').read_text().split()]
    if len(ids) != 256:
        raise ValueError('requires exact 256 token fixture')
    torch.set_num_threads(a.threads)
    torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    a.out.mkdir(parents=True)
    (a.out / 'INCOMPLETE').write_text('No success manifest until capture finishes.\n')
    started = time.monotonic()
    model = AutoModelForCausalLM.from_pretrained(str(model_dir), local_files_only=True,
        trust_remote_code=False, use_safetensors=True, dtype=torch.float32, attn_implementation='eager')
    model.eval()
    if model.get_input_embeddings().weight.data_ptr() != model.get_output_embeddings().weight.data_ptr():
        raise ValueError('expected HF tied embedding storage')
    if 'logits_to_keep' not in inspect.signature(model.forward).parameters:
        raise RuntimeError('unexpected forward interface')
    records = []

    def save(name, value):
        data = value.detach().cpu().contiguous().numpy().astype('<f4', copy=False)
        if not np.isfinite(data).all():
            raise ValueError('nonfinite capture')
        p = a.out / name
        with p.open('xb') as f:
            f.write(data.tobytes(order='C'))
        return dict(file=name, shape=list(data.shape), dtype='float32_le', sha256=sha(p), bytes=p.stat().st_size)

    hooks = []
    for layer in (0, 11, 23):
        for proj in ('gate', 'up', 'down'):
            module = getattr(model.model.layers[layer].mlp, proj + '_proj')
            if module.bias is not None:
                raise ValueError('unexpected MLP bias')
            def hook(mod, inputs, output, layer=layer, proj=proj):
                prefix = f'layer{layer:02d}-{proj}'
                records.append(dict(layer=layer, projection=proj, token_positions=list(range(248, 256)),
                    input=save(prefix + '-input.f32', inputs[0][0, -8:, :]),
                    original_fp32_output=save(prefix + '-output.f32', output[0, -8:, :]),
                    weight_shape=list(mod.weight.shape), bias=None))
            hooks.append(module.register_forward_hook(hook))
    with torch.inference_mode():
        output = model(input_ids=torch.tensor([ids], dtype=torch.long), use_cache=False, logits_to_keep=8)
        logits = save('logits.f32', output.logits[0])
    for hook in hooks:
        hook.remove()
    if len(records) != 9:
        raise ValueError('capture count mismatch')
    implementation = Path(inspect.getsourcefile(type(model)))
    manifest = dict(schema='a2-float-observation-0.1', stage='original',
        model_revision=pins['model']['revision'], original_weight_sha256=pins['model']['weight_sha256'],
        token_ids_sha256=fm['sha256']['tokens.txt'], chat_template_sha256=fm['sha256']['chat_template.txt'],
        prompt_sha256=fm['sha256']['prompt.txt'], context_token_ids=ids,
        positions=list(range(248, 256)), vocab_size=model.config.vocab_size,
        logits=logits, activations=records, sidecar_sha256=None,
        producer=dict(torch=torch.__version__, transformers=transformers.__version__, numpy=np.__version__,
                      implementation_sha256=sha(implementation), threads=a.threads, interop_threads=1,
                      device='cpu', weights_compute_dtype='FP32_from_original_BF16', attention='eager', use_cache=False),
        elapsed_total_s=time.monotonic() - started,
        note='Actual original-model activations; NOT B independent quantized golden; PC elapsed time is not a board/performance baseline. One model only, no GGUF loaded.',
        a2='NOT_PASSED')
    with (a.out / 'manifest.json').open('x', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)
    a.report.parent.mkdir(parents=True, exist_ok=True)
    with a.report.open('x', encoding='utf-8') as f:
        json.dump(dict(manifest=manifest, capture_directory=str(a.out.resolve())), f, indent=2)
    (a.out / 'INCOMPLETE').unlink()
    print(json.dumps(dict(activation_cases=len(records), logits_shape=logits['shape'], threads=a.threads, a2='NOT_PASSED')))


if __name__ == '__main__':
    main()
