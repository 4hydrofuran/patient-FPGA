"""Freeze A11 inputs on PC; never imports XRT or executes an ARM/board program.

Actual outputs are NOT populated here. Golden files stay in the PC reference
directory, separate from the input payload intended for a future board worker.
Existing A04 T1/T8 independent results are verified/reused, not recomputed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from quant.reference import scalar

CONTRACT = '83bd402b39350710d8689d50f79296e9625e9c75ccb0ecee145f08067c4ee3b6'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def readj(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def put(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as f:
        f.write(data)
    return dict(file=path.name, bytes=len(data), sha256=sha(data))


def putj(path, data):
    return put(path, (json.dumps(data, ensure_ascii=False, indent=2)+'\n').encode())


def rows(data, k):
    if len(data) % (4*k):
        raise ValueError('unaligned FP32 rows')
    v = struct.unpack('<'+'f'*(len(data)//4), data)
    return [v[i:i+k] for i in range(0, len(v), k)]


def schedule():
    items = [('hand', 1), ('tails_double_scale', 3)]
    for op in ('gate', 'up', 'down'):
        items += [(f'l00_{op}', t) for t in (1, 8, 3, 1, 8, 1, 8)]
    return [dict(job_id=i+1, weight=w, case=f'{w}_T{t}', T=t)
            for i, (w, t) in enumerate(items)]


def freeze(out, reference_binary):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    payload, refs = out/'inputs', out/'pc_reference'
    side, captures = ROOT/'models/sidecar_A/qwen35-v1', ROOT/'eval/qwen35/a04/captures-v1/S0_Q4'
    sources = {}

    def source(path, expected=None):
        data = path.read_bytes()
        digest = sha(data)
        if expected is not None and digest != expected:
            raise ValueError('frozen source hash mismatch: '+str(path))
        sources[str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)] = dict(sha256=digest, bytes=len(data))
        return data

    man = json.loads(source(side/'manifest.json'))
    cap = json.loads(source(captures/'manifest.json'))
    if man['contract_sha256'] != CONTRACT or man['source_revision'] != cap['source_revision']:
        raise ValueError('contract/revision mismatch')
    source(ROOT/'quant/reference/scalar.py')
    source(reference_binary)
    weights, cases, checks = {}, {}, []
    entries = {x['id']: x for x in man['entries']}
    records = {x['id']: x for x in cap['records']}
    for op in ('gate', 'up', 'down'):
        ident = f'l00_{op}'
        entry = entries[ident]
        n, k = entry['N'], entry['K']
        if (n, k) != ((1024, 3584) if op == 'down' else (3584, 1024)):
            raise ValueError('unexpected model dimensions')
        weights[ident] = dict(N=n, K=k, provenance=entry, files={})
        for name in ('w.bin', 'sw.bin'):
            info = entry['files'][name]
            data = source(side/info['file'], info['sha256'])
            if len(data) != info['bytes']:
                raise ValueError('weight length differs')
            weights[ident]['files'][name] = put(payload/ident/name, data)
        for t in (1, 8, 3):
            rec = records[('decode_' if t == 1 else 'prefill_')+ident]
            old = ROOT/'eval/qwen35/a04/real-v1'/('S0_Q4_'+rec['id'])
            comparison = json.loads(source(old/'comparison.json'))
            if not (comparison['integer_bit_exact'] is True and comparison['float_bit_exact'] is True
                    and comparison['cpp_vs_independent_reference']['tolerance_failures'] == 0):
                raise ValueError('unverified old reference')
            x_all = source(captures/rec['input']['file'], rec['input']['sha256'])
            x = x_all[:t*k*4]
            xq, sx = scalar.quant_activations(rows(x, k))
            for name, expected in (('xq.bin', xq), ('sx.bin', sx)):
                if source(old/'cpp'/name)[:len(expected)] != expected:
                    raise ValueError('independent quantization differs: '+ident)
            gold = {}
            for name, oldname, stride in (('y.bin', 'python_y.bin', n*4),
                                           ('sums.bin', 'python_sums.bin', n*(k//128)*4)):
                python = source(old/oldname)
                cpp = source(old/'cpp'/name)
                if python != cpp or len(python) != rec['T']*stride:
                    raise ValueError('independent result mismatch: '+ident)
                gold[name] = python[:t*stride]
            case = f'{ident}_T{t}'
            files = {name: put(payload/case/name, b) for name, b in
                     (('x.f32', x), ('xq.bin', xq), ('sx.bin', sx))}
            golden = {name: put(refs/case/name, b) for name, b in gold.items()}
            cases[case] = dict(weight=ident, N=n, K=k, T=t, files=files, golden=golden,
                activation_origin='real captured S0_Q4 activation; NOT a complete W4A8 or FPGA graph run',
                source_record=rec['id'], source_input_sha256=rec['input']['sha256'],
                source_rows=[0, t], original_token_positions=([256] if t == 1 else list(range(248,248+t))),
                reference='A04 independent Python scalar and C++ bit-exact results; T3 is first 3 token rows')
            if t == 3:
                checks.append(check_cpp(reference_binary, payload, refs, weights, case, cases[case]))
    # Two small representatives. The second merges N/K tails and two scale groups.
    small = [('hand', [[7., 0.], [0., 14.]], [[127., 127.]]),
             ('tails_double_scale', [[float(((r*3+j)%15)-7)*(0.25 if j<128 else 3.)
                                      for j in range(129)] for r in range(33)],
              [[float(((t*7+j)%31)-15)*(t+1)/8 for j in range(129)] for t in range(3)])]
    for ident, wrows, xrows in small:
        n, k, t = len(wrows), len(wrows[0]), len(xrows)
        w, sw = scalar.pack_weights(wrows)
        xq, sx = scalar.quant_activations(xrows)
        y, sums = scalar.execute(n, k, t, w, sw, xq, sx)
        if ident == 'hand' and y[:2] != [889., 1778.]:
            raise ValueError('hand reference differs')
        weights[ident] = dict(N=n, K=k, provenance='synthetic small mathematical test',
            files={name: put(payload/ident/name, b) for name, b in (('w.bin',w),('sw.bin',sw))})
        case = f'{ident}_T{t}'
        x = struct.pack('<'+'f'*(k*t), *(v for row in xrows for v in row))
        cases[case] = dict(weight=ident, N=n, K=k, T=t,
            files={name: put(payload/case/name,b) for name,b in (('x.f32',x),('xq.bin',xq),('sx.bin',sx))},
            golden={name: put(refs/case/name,b) for name,b in
                    (('y.bin',struct.pack('<'+'f'*len(y),*y)),('sums.bin',struct.pack('<'+'i'*len(sums),*sums)))},
            activation_origin='synthetic', reference='independent Python scalar; C++ crosscheck')
        checks.append(check_cpp(reference_binary,payload,refs,weights,case,cases[case]))
    real_weight_bytes = weights['l00_gate']['files']['w.bin']['bytes']+weights['l00_gate']['files']['sw.bin']['bytes']
    io = sum(((v+4095)//4096)*4096 for v in (8*4864,8*4,8*4864*4,64))
    report = dict(schema='A11_FROZEN_MINIMAL_V1', domain='PC', BOARD='NOT_TESTED',
        board_authorization_included=False, contract_sha256=CONTRACT, source_revision=man['source_revision'],
        cases=cases, weights=weights, schedule=schedule(), real_shape_submissions=21, small_submissions=2,
        same_worker_required=True, max_simultaneous_weight_handles=1,
        proposed_allocation=dict(logical_weight_bytes_per_real_handle=real_weight_bytes,
            page4096_aligned_io_bytes=io, explicit_bo_peak_bytes=io+real_weight_bytes,
            physical_peak_bytes=None, allocation_reachability='NOT_VERIFIED_ON_BOARD',
            note='One weight handle at a time; excludes XRT internal buffers, kernel, display and loader'),
        sources=sources, new_cpp_checks=checks, reused_full_real_reference_pairs=6,
        integer_debug_BOARD=None, hardware_cycles=None, measured_AXI_bytes=None,
        fp32_tolerance=dict(atol=1e-4,rtol=1e-5), actual_board_outputs=[])
    putj(out/'manifest.json', report)
    print(json.dumps(dict(status='PASS_PC_FREEZE',cases=len(cases),planned_board_calls=23,
                         new_cpp_checks=len(checks),BOARD='NOT_TESTED',budget=report['proposed_allocation'])))


def check_cpp(binary, payload, refs, weights, case, info):
    ident = info['weight']
    dest = refs/case/'new_cpp'
    argv = [str(binary),'run',str(info['N']),str(info['K']),str(info['T']),
            str(payload/ident/'w.bin'),str(payload/ident/'sw.bin'),str(payload/case/'x.f32'),str(dest)]
    p = subprocess.run(argv, capture_output=True, text=True, timeout=60)
    result = dict(argv=argv,exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr,domain='PC_REFERENCE_NOT_FPGA')
    putj(refs/case/'command.json', result)
    if p.returncode:
        raise RuntimeError('new PC reference failed: '+case)
    for name in ('y.bin','sums.bin'):
        if (dest/name).read_bytes() != (refs/case/name).read_bytes():
            raise ValueError('C++ differs from independent reference: '+case+'/'+name)
    for name in ('xq.bin','sx.bin'):
        if (dest/name).read_bytes() != (payload/case/name).read_bytes():
            raise ValueError('C++ quantization differs: '+case+'/'+name)
    return dict(case=case,status='PASS_PC_BIT_EXACT',command='pc_reference/'+case+'/command.json')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--reference-binary', required=True, type=Path)
    args = ap.parse_args()
    freeze(args.out.resolve(), args.reference_binary.resolve())
