"""A2 format-independent source/graph inventory, never a sidecar exporter."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import tarfile

ROOT = Path(__file__).resolve().parents[1]
LLAMA = '4762ad7316dcdec20016ab5985fb46a27902204d'
ARCHIVE_SHA = '06b6a3a1c2d12becc05d02c701274ab1f6d033399b4a20a166b919289e19233c'


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(4 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def unique_pairs(pairs):
    result = {}
    for k, v in pairs:
        if k in result:
            raise ValueError('duplicate JSON key: ' + k)
        result[k] = v
    return result


def tensor_header(path):
    size = path.stat().st_size
    with path.open('rb') as f:
        raw = f.read(8)
        if len(raw) != 8:
            raise ValueError('short header')
        n = struct.unpack('<Q', raw)[0]
        if not 0 < n <= min(16 << 20, size - 8):
            raise ValueError('invalid header length')
        tensors = json.loads(f.read(n), object_pairs_hook=unique_pairs)
    tensors.pop('__metadata__', None)
    intervals = []
    for name, item in tensors.items():
        shape = item['shape']
        if not shape or any(type(x) is not int or x <= 0 for x in shape):
            raise ValueError('invalid tensor shape: ' + name)
        width = {'BF16': 2, 'F16': 2, 'F32': 4}.get(item['dtype'])
        start, end = item['data_offsets']
        if width is None or type(start) is not int or type(end) is not int or start < 0 or end - start != math.prod(shape) * width or 8 + n + end > size:
            raise ValueError('invalid tensor bytes: ' + name)
        intervals.append((start, end))
    intervals.sort()
    if not intervals or intervals[0][0] != 0 or intervals[-1][1] != size - 8 - n:
        raise ValueError('payload extent mismatch')
    if any(a[1] != b[0] for a, b in zip(intervals, intervals[1:])):
        raise ValueError('tensor overlap or gap')
    return tensors, 8 + n


def mapping(config, tensors):
    if config.get('architectures') != ['Qwen2ForCausalLM'] or config.get('hidden_act') != 'silu':
        raise ValueError('unreviewed architecture/activation')
    h, mid, layers = (config[k] for k in ('hidden_size', 'intermediate_size', 'num_hidden_layers'))
    rows = []
    for layer in range(layers):
        for proj, shape, node, inp in [
            ('gate', [mid, h], 'ffn_gate', 'ffn_norm'),
            ('up', [mid, h], 'ffn_up', 'ffn_norm'),
            ('down', [h, mid], 'ffn_out', 'ffn_swiglu'),
        ]:
            name = f'model.layers.{layer}.mlp.{proj}_proj.weight'
            item = tensors[name]
            if item['shape'] != shape or item['dtype'] != 'BF16':
                raise ValueError('unexpected MLP shape/dtype: ' + name)
            if name.removesuffix('weight') + 'bias' in tensors:
                raise ValueError('unexpected MLP bias')
            rows.append(dict(source_tensor=name, source_dtype='BF16', logical_shape_N_K=shape,
                             gguf_name=f'blk.{layer}.ffn_{proj}.weight', ggml_ne_K_N=shape[::-1],
                             graph_weight=f'model.layers[{layer}].ffn_{proj}', graph_output=node,
                             graph_input=inp, layer=layer, transpose_payload=False, bias=None,
                             data_offsets=item['data_offsets']))
    embedding = tensors['model.embed_tokens.weight']
    if embedding['shape'] != [config['vocab_size'], h]:
        raise ValueError('embedding shape mismatch')
    if config.get('tie_word_embeddings') is not True or 'lm_head.weight' in tensors:
        raise ValueError('unreviewed tied-head storage: explicit handling required')
    if 'lm_head.bias' in tensors:
        raise ValueError('unexpected output bias')
    expected_bias = {f'model.layers.{i}.self_attn.{p}_proj.bias'
                     for i in range(layers) for p in ('q', 'k', 'v')}
    actual_bias = {n for n in tensors if n.endswith('.bias')}
    if actual_bias != expected_bias:
        raise ValueError('unexpected bias set')
    return rows


def source_proof(root):
    archive = root / 'platform/local/a1/llama.tar.gz'
    if sha(archive) != ARCHIVE_SHA:
        raise ValueError('llama archive changed')
    base = root / ('platform/local/a1/llama.cpp-' + LLAMA)
    locations = {
        'convert_hf_to_gguf.py': [242, 2753],
        'gguf-py/gguf/tensor_mapping.py': [338, 392, 429],
        'gguf-py/gguf/gguf_writer.py': [263],
        'src/llama-model.cpp': [2732, 7756],
        'src/llama-model-loader.cpp': [789],
        'src/llama-graph.cpp': [554, 643],
        'ggml/src/ggml.c': [2971],
    }
    evidence = []
    with tarfile.open(archive, 'r:gz') as tar:
        for name, lines in locations.items():
            member = tar.extractfile('llama.cpp-' + LLAMA + '/' + name)
            expected = hashlib.sha256(member.read()).hexdigest()
            if sha(base / name) != expected:
                raise ValueError('local pinned source changed: ' + name)
            evidence.append(dict(file=str((base / name).relative_to(root)).replace('\\', '/'),
                                 sha256=expected, reviewed_lines=lines))
    return evidence


def memory_estimate(config, tensors, rows, gguf_bytes):
    mlp_bytes = sum(tensors[r['source_tensor']]['data_offsets'][1] - tensors[r['source_tensor']]['data_offsets'][0] for r in rows)
    weight = scale = 0
    for r in rows:
        n, k = r['logical_shape_N_K']
        npad, kpad = (n + 31) // 32 * 32, (k + 127) // 128 * 128
        weight += npad * kpad // 2
        scale += npad * (kpad // 128) * 4
    return dict(status='SHAPE_BASED_PLANNING_NOT_ALLOCATED_OR_FROZEN',
                original_tensor_payload_bytes=sum(i['data_offsets'][1] - i['data_offsets'][0] for i in tensors.values()),
                original_mlp_bf16_bytes=mlp_bytes, original_gguf_file_bytes=gguf_bytes,
                proposed_w4_payload_bytes=weight, proposed_f32_scales_bytes=scale,
                proposed_sidecar_payload_bytes=weight + scale,
                sidecar_metadata_and_page_alignment_bytes=None,
                resident_weight_bo_bytes=None, original_gguf_resident_pages_bytes=None,
                sidecar_resident_pages_bytes=None, repack_copy_resident_bytes=None,
                runtime_workspace_bytes=None, linux_budget_bytes=None, pl_budget_bytes=None,
                example_kv_f16_512_tokens_bytes=2 * config['num_hidden_layers'] * 512 * config['num_key_value_heads'] * (config['hidden_size'] // config['num_attention_heads']) * 2,
                policy='Never add file-backed RSS twice; BO copy and file-backed pages MAY coexist. No full second model; no per-token weight quantization. A3 must avoid original MLP loading, account tied-head buffers and measure actual residency.')


def audit(root):
    pins = json.loads((root / 'platform/a1/pins.json').read_text())
    model = root / 'platform/local/a1/model/model.safetensors'
    if sha(model) != pins['model']['weight_sha256']:
        raise ValueError('source weight hash mismatch')
    config_path = root / 'platform/local/a1/model/config.json'
    config = json.loads(config_path.read_text())
    tensors, offset = tensor_header(model)
    rows = mapping(config, tensors)
    with model.open('rb') as f:
        for row in rows:
            lo, hi = row['data_offsets']
            f.seek(offset + lo)
            row['source_tensor_sha256'] = hashlib.sha256(f.read(hi - lo)).hexdigest()
    return dict(version='a2-source-audit-0.1', status='FORMAT_INDEPENDENT_ONLY',
                source_revision=pins['model']['revision'], source_sha256=pins['model']['weight_sha256'],
                config_sha256=sha(config_path), config=config, llama_commit=LLAMA,
                reviewed_source=source_proof(root), tensors=rows,
                attention_biases={n: t['shape'] for n, t in tensors.items() if n.endswith('.bias')},
                embedding_head=dict(tied_config=True, explicit_lm_head_stored=False,
                                    source='model.embed_tokens.weight', gguf='token_embd.weight',
                                    storage_shape=tensors['model.embed_tokens.weight']['shape'],
                                    runtime='output falls back to TENSOR_DUPLICATED; physical alias/copy must be measured per backend'),
                memory=memory_estimate(config, tensors, rows, (root / 'platform/local/a1/Qwen2.5-0.5B-Instruct-f16.gguf').stat().st_size),
                graph_note='down output callback is ffn_out for this no-bias graph, NOT guaranteed ffn_down; last layer may select only requested token rows',
                sidecar_exported=False, b_crosscheck='NOT_RUN', a2='NOT_PASSED')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('x', encoding='utf-8') as f:
        result = audit(ROOT)
        json.dump(result, f, indent=2, ensure_ascii=False)
        f.write('\n')
    print(json.dumps(dict(tensors=len(result['tensors']), memory=result['memory'], a2=result['a2'])))
