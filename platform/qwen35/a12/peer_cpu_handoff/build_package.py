"""Explicit allowlist handoff builder; creates a NEW staging dir, no credentials/assets."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
RUNTIME_COMMIT = '81e39ad34368329b5db77620721510fd91107e80'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', required=True, type=Path)
    a = ap.parse_args()
    out = a.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    provenance = {}
    def copy(src, dst):
        src = Path(src); target = out / dst
        if src.is_symlink() or not src.is_file(): raise ValueError(str(src))
        target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(src, target)
        provenance[dst] = {'source': src.relative_to(ROOT).as_posix(), 'sha256': sha(src), 'transform': 'BYTE_COPY'}
    runtime = ROOT / 'release/default_preboard/20261004-v2/source-bundle/project/third_party/llama'
    pins = json.loads((ROOT / 'evidence/model_pl_A/20261024-step10-v1/LLAMA_DERIVATION.json').read_text(encoding='utf-8'))
    for name, digest in pins['unchanged_source_pins'].items():
        if sha(runtime / name) != digest: raise ValueError('Runtime pin mismatch: ' + name)
    for folder in ['src', 'include', 'cmake', 'ggml', 'vendor', 'licenses']:
        for path in sorted((runtime / folder).rglob('*')):
            if path.is_file() and not any(p in {'.git', '__pycache__'} for p in path.parts):
                copy(path, 'source/llama/' + path.relative_to(runtime).as_posix())
    for name in ['CMakeLists.txt', 'LICENSE', 'AUTHORS', 'README.md']:
        copy(runtime / name, 'source/llama/' + name)
    timer = ROOT / 'evidence/model_pl_A/20261024-step10-v1/build-logs/ggml-cpu-timing.c'
    if sha(timer) != pins['changes']['ggml/src/ggml-cpu/ggml-cpu.c']['after']:
        raise ValueError('Timer source pin mismatch')
    copy(timer, 'source/llama/ggml/src/ggml-cpu/ggml-cpu.c')
    source = ROOT / 'evidence/model_pl_A/20261024-step10-v1/source-v2'
    for f in ['sp-hook.cpp', 'sp-hook.h']:
        if sha(source / f) != sha(ROOT / 'runtime/qwen35_w4a8' / f):
            raise ValueError('Hook has diverged')
        copy(source / f, 'source/runtime/' + f)
    for f in ['request_profile.cpp', 'request_profile.hpp']: copy(source / f, 'source/profile/' + f)
    for f in ['main.cpp', 'bridge.cpp', 'bridge.hpp', 'route.cpp', 'route.hpp']:
        copy(source / f, 'context/A12/' + f)
    for path, dst in [
        ('evidence/model_pl_A/20261024-step08-v1/SCHEDULING_SOURCE_qwen35.cpp', 'context/qwen35.cpp'),
        ('evidence/model_pl_A/20261024-step10-v1/LLAMA_DERIVATION.json', 'context/LLAMA_DERIVATION.json'),
        ('docs/A12_CPU_OPTIMIZATION_PLAN_20261024.md', 'context/CPU_OPTIMIZATION_PLAN.md'),
        ('eval/qwen35/a05/batch-fix-v1/REPORT.md', 'history/A05_REPORT.md'),
        ('eval/qwen35/a05/batch-fix-v1/root-cause-v2.json', 'history/root-cause-v2.json'),
        ('eval/qwen35/a05/batch-fix-v1/stable-projections.patch', 'history/stable-projections.patch'),
        ('eval/qwen35/a05/batch-fix-v1/stable-attention.patch', 'history/stable-attention.patch'),
        ('eval/qwen35/a05/graph-v2.patch', 'history/graph-v2.patch'),
        ('eval/qwen35/a05/state-v2/inputs.json', 'history/empty-output-inputs.json'),
        ('eval/qwen35/a05/state-v8/numerics.json', 'history/state-v8-numerics.json'),
        ('eval/qwen35/a05/state-v8/checks.json', 'history/state-v8-checks.json'),
        ('platform/qwen35/a05/empty_output_repro.py', 'history/reference_scripts/empty_output_repro.py'),
        ('platform/qwen35/a05/state_regression.py', 'history/reference_scripts/state_regression.py'),
        ('platform/qwen35/a05/native_client.py', 'history/reference_scripts/native_client.py'),
        ('platform/qwen35/a05/analyze_state.py', 'history/reference_scripts/analyze_state.py'),
        ('artifacts/qwen35-0.8b/source/LICENSE', 'assets/MODEL_PUBLIC_LICENSE.txt'),
    ]: copy(ROOT / path, dst)
    for path in sorted((ROOT / 'contracts/qwen35').iterdir()):
        if path.name in ['contracts.lock', 'quant_v1.json', 'sp_linear_v1.h', 'voice_v1.json', 'voice_examples.jsonl']:
            copy(path, 'contracts/qwen35/' + path.name)
    for name in ['README.md', 'TASKS.md', 'ACCEPTANCE.md', 'DELIVERY.md']: copy(HERE / name, name)
    for name in ['CMakeLists.txt', 'verify_package.py', 'build_and_test.py']: copy(HERE / name, 'tools/' + name)
    for name in ['projection.cpp', 'profile.cpp']: copy(HERE / name, 'tests/' + name)

    # Only the profile aggregates are required; omit device addresses/process/lease data.
    window = ROOT / 'evidence/model_pl_A/20261024-health-opt-v1/candidate/readback-v1/run-v1'
    for side, label in [('s1', 'CPU'), ('s2', 'PL')]:
        path = window / side / 'natural_profile/result.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        selected = {'domain': 'HISTORICAL_BOARD_AGGREGATES_NOT_NEW_RUN', 'source_sha256': sha(path),
                    'prompt_tokens': data['prompt_tokens'], 'output_tokens': len(data['output_tokens']),
                    'prefill_ms': data['prefill_ms'], 'reset_ms': data['reset_ms'],
                    'request_profile': data['request_profile']}
        write(out / ('baseline/' + label + '_PROFILE.json'), selected)
    model = json.loads((ROOT / 'models/model.lock.json').read_text(encoding='utf-8'))
    sidecar = json.loads((ROOT / 'models/sidecar_A/qwen35-v1/manifest.json').read_text(encoding='utf-8'))
    write(out / 'assets/MODEL_ASSETS.json', {'included_weights': False, 'model': model['model'],
          'revision': model['revision'], 'runtime_commit': model['runtime_commit'],
          'converted_files': model['converted_files'], 'sidecar_manifest_sha256': sha(ROOT / 'models/sidecar_A/qwen35-v1/manifest.json'),
          'sidecar_payload_files': {v['file']: v for e in sidecar['entries'] for v in e['files'].values()},
          'scope': 'Identity only; no model payload included. Full-model harness not provided by this component package.'})
    failures = []
    for name in ['empty-repro-v6', 'empty-repro-v7']:
        p = ROOT / ('eval/qwen35/a05/' + name + '/report.json')
        d = json.loads(p.read_text(encoding='utf-8'))
        failures.append({'source': str(p.relative_to(ROOT)), 'source_sha256': sha(p),
                         'expected': d['expected'], 'process_exit_code': d['exit_code'],
                         'records': {k: {f: v.get(f) for f in ['type', 'status', 'decode_rc', 'prompt_tokens', 'logits_mode']}
                                     for k, v in d['records'].items()}})
    write(out / 'history/EMPTY_OUTPUT_FAILURE_AND_FIX.json', {'scope': 'HISTORICAL_PC_ONLY', 'records': failures})
    expected = {
        'src/llama-graph.cpp': sha(runtime / 'src/llama-graph.cpp'),
        'ggml/src/ggml-cpu/ops.cpp': sha(runtime / 'ggml/src/ggml-cpu/ops.cpp'),
        'include/llama.h': sha(runtime / 'include/llama.h'),
        'ggml/src/ggml-cpu/ggml-cpu.c': sha(timer),
        'sp-hook.cpp': sha(source / 'sp-hook.cpp'), 'request_profile.cpp': sha(source / 'request_profile.cpp')}
    write(out / 'BASELINE.json', {'status': 'FROZEN_BASELINE_NOT_OPTIMIZED', 'runtime_commit': RUNTIME_COMMIT,
          'model_revision': model['revision'], 'source_pins': expected,
          'board_reference': {'prefill_seconds': 52.848003062, 'first_token_seconds': 52.867378826,
                              'other_bucket_seconds': 14.264297, 'other_bucket_calls': 29310,
                              'fused_extra_nodes': 1106},
          'task01_scope': 'CPU node categorization only; not permission/health manager',
          'task03_scope': 'Stable per-token GEMV scheduling/output assembly only',
          'new_optimization_results': None, 'BOARD': 'NOT_TESTED_FOR_THIS_PACKAGE'})
    write(out / 'templates/RESULTS.json', {'schema': 'A12_PEER_CPU_RETURN_V1',
          'source_base_manifest_sha256': None, 'candidate_source_sha256': None,
          'PC_components': 'NOT_TESTED', 'PC_full_model': 'NOT_TESTED', 'CROSS_BUILD': 'NOT_TESTED',
          'BOARD': 'NOT_TESTED', 'candidate_speedup_PC': None, 'board_TTFT_ms': None,
          'device_cycles': None, 'power_W': None, 'raw_samples': [], 'limitations': []})
    write(out / 'templates/FAILURES.json', {'failures': [], 'instruction': 'Append actual attempts, exit codes, reproductions and fixes; do not delete failed versions.'})
    write(out / 'fixtures/PROFILE_CASES.json', {'status': 'TARGET_REQUIREMENTS_NOT_IMPLEMENTED',
          'note': 'Logical categories, independent of chosen output bucket spelling. Fused groups have one elapsed interval.',
          'cases': [
              {'op': 'MUL_MAT', 'name': 'opaque', 'weight': 'blk.0.attn_gate.weight', 'expected': 'non_MLP_projection'},
              {'op': 'MUL_MAT', 'name': 'opaque', 'weight': 'unknown.weight', 'expected': 'matrix_unknown_identity'},
              {'op': 'MUL_MAT', 'name': 'opaque', 'weight': 'output.weight', 'expected': 'output_head'},
              {'op': 'CONCAT', 'name': 'attn_output-0', 'expected': 'data_movement_not_matrix'},
              {'op': 'CONT', 'name': 'opaque', 'expected': 'data_movement'},
              {'op': 'ADD', 'name': 'attn_residual-0', 'expected': 'residual_or_elementwise_not_attention_matrix'},
              {'op': 'RMS_NORM', 'fused_extra': 1, 'elapsed_us': 100, 'expected': 'normalization_fused_group_one_interval'},
              {'op': 'GLU', 'name': 'ffn_swiglu-0', 'expected': 'activation_not_MLP_linear'},
              {'op': 'CUSTOM', 'name': 'ffn_out-0', 'expected': 'MLP_linear'},
              {'op': 'CUSTOM', 'name': 'unknown', 'expected': 'unknown'},
              {'control': 'prefill_then_decode', 'expected': 'separate_counts_and_times'},
              {'control': 'reset_then_disabled', 'expected': 'no_stale_or_new_samples'}]})
    write(out / 'PROVENANCE.json', {'source_commit': RUNTIME_COMMIT,
          'files': provenance, 'generated_files': 'Other files are explicit derived summaries or task instructions.',
          'source_tree_origin': str(runtime.relative_to(ROOT)), 'secret_or_weight_payloads_included': False})
    write_manifest(out)
    print(json.dumps({'status': 'STAGED', 'path': str(out), 'files': len(list(out.rglob('*')))}, ensure_ascii=False))

def write_manifest(out):
    files = {p.relative_to(out).as_posix(): {'bytes': p.stat().st_size, 'sha256': sha(p)}
             for p in sorted(out.rglob('*')) if p.is_file() and p.name != 'MANIFEST.json'}
    write(out / 'MANIFEST.json', {'schema': 'A12_CPU_PEER_HANDOFF_V1', 'files': files,
          'scope': 'Task01A and Task03, no-board components only', 'runtime_commit': RUNTIME_COMMIT})

if __name__ == '__main__': main()
