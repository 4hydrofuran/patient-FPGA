"""Accept only observed current-source Csim plus hash-bound prior A06 evidence."""
import hashlib
import json
from pathlib import Path
import re
import zipfile

R = Path(__file__).resolve().parents[3]
E = R / 'evidence/A06_acceptance/final-20261004-v1'
S = R / 'evidence/A06_acceptance/supplement-v1'
C = R / 'evidence/A06_acceptance/a-owned-closeout-v1'
B = R / 'hw/linear_B_received/B03-supplement-e227297-20261003/payload'


def read(p):
    return json.loads(p.read_text(encoding='utf-8'))


def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for data in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(data)
    return h.hexdigest()


def main():
    # Mutable governance can advance in other A tasks, but no scientific/test
    # evidence from the prior sealed acceptance increment may silently change.
    mutable = {'AGENTS.md', 'docs/PROJECT_STATUS.json', 'docs/status/A.md',
               'docs/DESIGN_GAP.md', 'docs/TEST_MATRIX.md', 'hw/linear_A/KERNEL_SOURCE.json'}
    previous = read(C / 'files.sha256.json')['files']
    governance_changes = []
    for name, digest in previous.items():
        observed = sha(R / name)
        if observed != digest:
            if name not in mutable:
                raise ValueError('Changed prior sealed evidence: ' + name)
            governance_changes.append({'path': name, 'prior_sha256': digest, 'current_sha256': observed})
    manifest = read(B / 'B03_package_manifest.json')
    for name, entry in manifest['files'].items():
        assert sha(B / name) == entry['sha256'], name
    # Original A04 reference, hand fixtures and the same real sidecar inputs.
    a04 = {k.replace('\\', '/'): v for k, v in read(R / 'eval/qwen35/a04/files.sha256.json').items()}
    checked_a04 = []
    for name, digest in a04.items():
        if name.startswith('quant/reference/') or name.startswith('models/sidecar_A/qwen35-v1/'):
            assert sha(R / name) == digest, name
            checked_a04.append(name)
    assert 'quant/reference/w4a8.cpp' in checked_a04
    source = read(E / 'before/hw/linear_A/KERNEL_SOURCE.json')
    assert source['selected_source_sha256'] == sha(B / 'src/w4a8_prefill_v1.cpp')
    assert source['selected_header_sha256'] == sha(B / 'src/w4a8_linear_v1.hpp')
    xo = R / source['xo_path']
    assert sha(xo) == source['xo_sha256']
    with zipfile.ZipFile(xo) as z:
        xml = z.read(source['embedded_metadata_member'])
        assert hashlib.sha256(xml).hexdigest() == source['embedded_metadata_sha256']
    interface = read(S / 'interface-map.json')
    assert len(interface['arguments']) == 17 and interface['meta']['bytes'] == 40
    assert interface['metadata_sha256'] == source['embedded_metadata_sha256']
    config = (E / 'csim/acceptance.cfg').read_bytes()
    assert config == (S / 'tests/acceptance.cfg').read_bytes(), 'Numerical Csim config changed'
    inputs = read(E / 'csim/host.json')
    for name, digest in inputs['input_sha256'].items():
        local = Path(name.replace('/mnt/c/Patientqwen', R.as_posix()))
        # Queue cfg is copied verbatim above and may be outside the Windows view.
        if name.endswith('/acceptance.cfg'):
            assert hashlib.sha256(config).hexdigest() == digest
        else:
            assert sha(local) == digest, name
    license_info = read(E / 'license-install.json')
    assert inputs['license_sha256'] == license_info['license_sha256']
    assert inputs['boot_id'] == license_info['boot_id']
    assert inputs['interfaces']['eth0'].replace(':', '') == license_info['host_id']
    receipt = read(E / 'csim/csim.json')
    result = read(E / 'csim/result.json')
    assert receipt['exit_code'] == 0 and result['numerical_Csim_pass'] is True
    text = receipt['stdout'] + receipt['stderr']
    assert 'CSim done with 0 errors' in text and 'HLS Build v2026.1 6493734' in text
    summaries = [json.loads(s) for s in re.findall(r'^SUMMARY (\{.*\})\s*$', text, re.M)]
    assert len(summaries) == 1 and summaries[0]['cases'] == 61 and summaries[0]['checks'] == 2800022
    assert summaries[0]['build_id'] == int(source['selected_build_id'], 16)
    cases = [json.loads(s) for s in re.findall(r'^RESULT (\{.*\})\s*$', text, re.M)]
    assert len(cases) == 61 and all(c['status'] == 'PASS' for c in cases)
    for n, k in [(3584, 1024), (1024, 3584)]:
        for t in range(1, 9):
            assert any(c.get('N') == n and c.get('K') == k and c.get('T') == t for c in cases)
    for t in range(1, 9):
        assert any(c['case'] == 'tail_cross_scale' and c['T'] == t for c in cases)
    assert sum(c['case'].startswith('kernel_error_') for c in cases) == 18
    assert sum(c['case'].startswith('host_reject_') for c in cases) == 10
    for name in ['hand', 'repeat_call', 'zero_group', 'int32_bound_113792', 'fp32_group_order']:
        assert any(c['case'] == name for c in cases), name
    numeric = [c for c in cases if 'max_abs_error' in c]
    assert all(c['max_abs_error'] == 0 and c['fp32_bit_differences'] == 0 for c in numeric)
    portable = read(C / 'portable-receipt.json')
    assert sum(portable['regenerated_vectors_exact_sha_match'].values()) == 382
    assert all(v['exit_code'] == 0 for v in portable['steps'].values())
    prior = read(C / 'REPORT.json')
    proof = read(S / 'final-checks-v2/REPORT.json')
    for name in ['gate_t1', 'gate_t8', 'down_t1', 'down_t8']:
        assert proof['B_Cosim_original_reports'][name]['native'] == 'PASS', name
    assert prior['archived_RTL']['transactions'] == 66
    matrix = prior['matrix']
    for item in matrix:
        if item['requirement'] == 'A06.3 A local Vitis Csim of current source':
            item.update(status='PASS', evidence='final-20261004-v1/csim/csim.json: actual exit0, 61 cases / 2800022 checks')
        if item['requirement'] == 'A06.6 final accepted/frozen kernel':
            item.update(status='READY_TO_FREEZE', evidence='All numerical/ABI/source and required reused RTL receipts verified; A07 offline only')
    report = {'status': 'PASS_A06_OFFLINE_KERNEL_ACCEPTANCE', 'acceptance_owner': 'A',
              'provider': 'B', 'source_commit': source['source_commit'], 'selected_variant': 'double',
              'build_id': source['selected_build_id'], 'source_sha256': source['selected_source_sha256'],
              'header_sha256': source['selected_header_sha256'], 'xo_sha256': source['xo_sha256'],
              'embedded_metadata_sha256': source['embedded_metadata_sha256'],
              'matrix': matrix, 'Csim': summaries[0], 'case_results': cases,
              'csim_log_sha256': sha(E / 'csim/csim.json'), 'current_source_config_unchanged': True,
              'Csim_max_abs_error': max(c['max_abs_error'] for c in numeric),
              'prior_sealed_files_checked': len(previous), 'governance_changes_since_prior': governance_changes,
              'A04_reference_and_sidecar_files_verified': len(checked_a04),
              'B_payload_files_verified': len(manifest['files']), 'strict_vectors_exact': 382,
              'archived_RTL': prior['archived_RTL'], 'new_RTL_run': 'NOT_TESTED_REUSED_EXACT_SAME_SOURCE_REQUIRED_COSIM',
              'synthesis': 'REUSED_EXACT_XO_HLS_REPORTS', 'HLS_slack_ns': -0.40,
              'implementation': 'NOT_TESTED', 'ARM_execution': 'NOT_TESTED', 'BOARD': 'NOT_TESTED',
              'board_error': None, 'power': None, 'CMA': None, 'BO_budget': None,
              'license': {'sha256': license_info['license_sha256'], 'host_id': license_info['host_id'],
                          'validation': 'PASS_ACTUAL_CURRENT_SOURCE_VITIS_CSIM', 'persistent_MAC_guarantee': False},
              'failures_preserved': True, 'new_commit': None, 'push': False,
              'A07_implementation_or_B04_not_accepted_by_this_report': True,
              'next': 'A07 offline platform link and implementation review; no board authorization'}
    with (E / 'AUDIT.json').open('x', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(json.dumps({k: report[k] for k in ['status', 'Csim', 'strict_vectors_exact', 'B_payload_files_verified', 'BOARD']}))


if __name__ == '__main__':
    main()
