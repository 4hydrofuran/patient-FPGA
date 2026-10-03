"""Extract exact selected synthesis artifacts and bind receipts to source snapshots."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    xo = ROOT / 'artifact/b03_candidate/w4a8_linear_v1.xo'
    if sha(xo) != '96ca2a5825c4e044e0159b7a1553a30d8546cc59ab5cfc9201d6d44d4b7ddd23':
        raise RuntimeError('Frozen candidate changed')
    destination = ROOT / 'evidence/b03/supplement/synthesis'
    outputs = {}
    with zipfile.ZipFile(xo) as archive:
        for name in archive.namelist():
            report = '/syn/report/' in name and name.endswith(('.rpt', '.xml'))
            generated_rtl = name.endswith('.v') and ('prefill_overlap' in name or '_m_axi' in name)
            if report or generated_rtl:
                target = destination / ('reports' if report else 'generated_rtl') / Path(name).name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(name))
                outputs[target.relative_to(ROOT).as_posix()] = {'xo_member': name, 'sha256': sha(target), 'bytes': target.stat().st_size}
    overlap = next(destination.glob('reports/*prefill_overlap_csynth.rpt'))
    fifo_rows = [line for line in overlap.read_text().splitlines() if re.match(r'^\|FIFO\s+\|', line)]
    if not fifo_rows:
        raise RuntimeError('No original FIFO resource row')
    buffers = {'weights_first': 2048, 'weights_second': 2048, 'scales_first': 128, 'scales_second': 128,
               'activations': 38912, 'token_scales': 32, 'totals': 1024}
    channel_note = {'candidate': 'double', 'source_sha256': sha(ROOT / 'src/w4a8_prefill_v1.cpp'),
                    'xo_sha256': sha(xo), 'scope': 'Static inferred structure/capacity and finite random-stall acceptance; no measured internal AXI FIFO occupancy.',
                    'array_buffer_bytes': buffers, 'user_hls_stream_channels': [],
                    'overlap_fifo_resource_row': fifo_rows, 'user_stream_fifo_occupancy': 'NOT_APPLICABLE_NO_USER_STREAM_CHANNEL',
                    'generated_axi_fifo_peak_occupancy': None, 'random_stall_transactions_passed': 32,
                    'ownership': 'load(next slot) and compute(current slot) use disjoint arrays; ownership swaps only after both functions return; last group disables prefetch',
                    'reports_and_rtl_extracted_from_exact_xo': outputs}
    (ROOT / 'reports/b03/supplement_buffers.json').write_text(json.dumps(channel_note, indent=2) + '\n', encoding='utf-8')
    snapshots = ROOT / 'evidence/b03/supplement/source_snapshots'
    candidates = ('src/w4a8_prefill_v1.cpp', 'src/w4a8_linear_v1.hpp', 'tb/tb_prefill_v1.cpp', 'tb/tb_prefill_bounds.cpp',
                  'tb/golden_w4a8.hpp', 'hls_prefill_double.cfg', 'hls_prefill_baseline.cfg', 'run_prefill.ps1',
                  'baseline/b02/src/w4a8_linear_v1.cpp', 'baseline/b02/src/w4a8_linear_v1.hpp')
    historical_runners = ('evidence/b03/initial_runner/run_prefill.ps1', 'evidence/b03/sw32_nominal_runner/run_prefill.ps1')
    for name in (*candidates, *historical_runners):
        target = snapshots / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, target)
    runner_map = {sha(ROOT / name): name for name in ('run_prefill.ps1', *historical_runners)}
    selected = json.loads((ROOT / 'artifact/b03_candidate/candidate.json').read_text())
    receipt_names = [selected['artifact']['synthesis_receipt'], *selected['nominal']['receipts'].values(), *selected['nominal']['cosim_batch_receipts']]
    for group in ('stall_basic', 'stall_lifecycle', 'stall_tail', 'stall_max_k', 'stall_max_n'):
        receipt_names.append(json.loads((ROOT / f'evidence/b03/batches/double/{group}/manifest.json').read_text())['receipt'])
    trace = {}
    for name in dict.fromkeys(receipt_names):
        receipt = json.loads((ROOT / name).read_text(encoding='utf-8-sig'))
        rows = {}
        for path, expected in receipt['input_sha256'].items():
            resolved = runner_map.get(expected.lower(), path) if path == 'run_prefill.ps1' else path
            if not (ROOT / resolved).is_file() or sha(ROOT / resolved) != expected.lower():
                raise RuntimeError('Unresolved selected input: ' + path + ' in ' + name)
            rows[path] = {'sha256': expected.lower(), 'exact_file': resolved,
                          'role': 'design_source' if path.startswith('src/') else 'test/config/helper/auxiliary'}
        trace[name] = {'receipt_sha256': sha(ROOT / name), 'input_resolution': rows}
    refresh = json.loads((ROOT / 'reports/b03/supplement_baseline_refresh.json').read_text(encoding='utf-8-sig'))
    if refresh['status'] != 'PASS' or refresh['fresh_csim_transactions'] != 50:
        raise RuntimeError('Canonical baseline refresh has not passed')
    provenance = {'status': 'READY_FOR_A_REVIEW', 'created_at_local': datetime.now().astimezone().isoformat(),
                  'selected_current_receipts_all_inputs_exactly_resolved': trace,
                  'baseline_actual_design_header': 'baseline/b02/src/w4a8_linear_v1.hpp',
                  'baseline_auxiliary_root_header_initial_sha256': 'b19301fdad51d5292e707176c1e0170cf8cfc2862c65c425e16dae0df5db8fba',
                  'historical_missing_tb_sha256': 'f51a3a0d2c62b96239ad82e3a9f3492b94b9dcfdd7eb86ff26c0e0da890dfd00',
                  'historical_missing_tb_status': 'NOT_RECOVERED_ORIGINAL_OLD_RECEIPTS_RETAINED_AS_HISTORY_ONLY',
                  'baseline_canonical_fresh_receipts': refresh,
                  'interpretation': 'Fresh current-TB baseline Csim50/synthesis removes the missing historical TB from active source-to-test provenance. It does not reconstruct or retroactively authenticate the old TB.',
                  'A_static_audit_detail_provided': False, 'A_acceptance': 'NOT_SIGNED_BY_B'}
    (ROOT / 'reports/b03/supplement_provenance.json').write_text(json.dumps(provenance, indent=2) + '\n', encoding='utf-8')
    print('PASS exact candidate reports + selected input provenance; missing historical TB explicitly retained as limitation')


if __name__ == '__main__':
    main()
