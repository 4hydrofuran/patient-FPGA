"""Generate closeout evidence from actual receipts; cannot promote blocked Csim."""
import hashlib
import json
from pathlib import Path
import re
R = Path(__file__).resolve().parents[3]
E = R / 'evidence/A06_acceptance/a-owned-closeout-v1'
S = R / 'evidence/A06_acceptance/supplement-v1'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    portable = read(E / 'portable-receipt.json')
    assert portable['status'] == 'PASS_A_SERIALIZATION_OVERLAY'
    assert sum(portable['regenerated_vectors_exact_sha_match'].values()) == 382
    assert all(step['exit_code'] == 0 for step in portable['steps'].values())
    assert portable['immutable_payload_files'] == 1923 and not portable['kernel_source_modified']
    for name in ['portable-unit-v2', 'linux-portable-unit', 'prior-integrity', 'contracts', 'config']:
        assert read(E / 'commands' / (name + '.json'))['exit_code'] == 0, name
    pc = read(S / 'tests/pc.json')
    summary = json.loads(re.search(r'^SUMMARY (\{.*\})$', pc['stdout'], re.M)[1])
    assert pc['exit_code'] == 0 and summary['cases'] == 61 and summary['checks'] == 2800022
    old = read(S / 'REPORT.json')
    assert old['A_archived_RTL_replay']['transactions'] == 66
    assert old['A_archived_RTL_replay']['max_abs_error'] == 0
    windows = read(E / 'windows-csim-v2/result.json')
    assert windows['exit_code'] == 1 and not windows['numerical_Csim_pass']
    native = read(E / 'windows-csim-v2/csim.json')
    assert 'HLS 200-1023' in native['stdout'] + native['stderr']
    static = read(S / 'static.json')
    kernel = read(R / 'hw/linear_A/KERNEL_SOURCE.json')
    assert not kernel['accepted'] and not kernel['frozen']
    provenance = {key: old[key] for key in ['release_tag', 'source_commit', 'provider',
                    'selected_variant', 'xo_sha256', 'embedded_metadata_sha256', 'source_sha256']}
    matrix = [
        {'requirement': 'A06.1 receipt/source/XO/reports/vectors', 'status': 'PASS',
         'evidence': 'supplement-v1/inventory.json + static.json; 1925 archive files / 14 exact input receipts'},
        {'requirement': 'A06.2 header/XO binary ABI and A07 mapping', 'status': 'PASS',
         'evidence': 'supplement-v1/interface-map.json; 17 arguments + meta40 + hw/linear_A/A07_KERNEL_INTEGRATION.md'},
        {'requirement': 'A06.3 A independent PC arithmetic', 'status': 'PASS',
         'evidence': 'supplement-v1/tests/pc.json; 61 cases / 2800022 checks'},
        {'requirement': 'A06.3 A local Vitis Csim of current source', 'status': 'BLOCKED',
         'evidence': 'Linux license mismatch before simulation; windows-csim-v2/csim.json exit1 at K26 part check'},
        {'requirement': 'A06.4 actual shapes/required Csim and Cosim coverage', 'status': 'PASS_REUSED_EXACT_VERSION',
         'evidence': 'supplement-v1/final-checks-v2/REPORT.json; B full50; gate/down T1/T8 native Cosim; A04 RTL66 replay'},
        {'requirement': 'A06.5 part/tool/150MHz/resource/II/reuse review', 'status': 'PASS_REVIEW_NOT_TIMING_CLOSURE',
         'evidence': 'supplement-v1/static.json and XO-embedded reports; HLS slack -0.40ns'},
        {'requirement': 'A06.6 final accepted/frozen kernel', 'status': 'NOT_PASSED',
         'evidence': 'KERNEL_SOURCE accepted=false/frozen=false until actual local Csim passes'},
        {'requirement': 'Delivery clean portable vector byte reproduction', 'status': 'PASS_A_REPAIR',
         'evidence': 'portable-receipt.json + portable-logs/*; all382 SHA identical; B originals unchanged'},
    ]
    result = dict(provenance, status='PARTIAL_TOOLING_COMPLETE_LOCAL_CSIM_BLOCKED', accepted=False, frozen=False,
                  owner_of_remaining_corrections='A', awaiting_B=False, matrix=matrix,
                  PC_A_independent=summary, PC_A_portable='PASS_50_SYNTHETIC_PLUS_4_REAL_WEIGHT_SYNTHETIC_ACTIVATION',
                  unit_tests='PASS_3_METHODS_ON_WINDOWS_AND_LINUX',
                  vectors_exact_sha=382, B_originals_unchanged=1923,
                  A_local_Csim='NOT_PASSED_LICENSE_OR_PART_CHECK_BEFORE_NUMERICAL_RUN',
                  B_same_version_Csim='PASS_REUSED_FULL50_AND_BOTH_SHAPES_T1_T8',
                  archived_RTL=old['A_archived_RTL_replay'],
                  new_RTL_simulation='NOT_TESTED_NOT_REQUIRED_TO_REPEAT_VALID_SELECTED_REPORTS',
                  synthesis='REUSED_EXACT_XO_REPORTS', implementation='NOT_TESTED', BOARD='NOT_TESTED',
                  board_error=None, CMA=None, BO_budget=None,
                  A07_independent_crossbuild='PRIOR_VALID_EVIDENCE_PRESERVED_NOT_RERUN',
                  prior_failures=['Provider Linux CRLF selftest exit1', 'A reverse-patch unit assertion v1 exit1; test scoping fixed v2',
                                  'WSL-to-Windows launch exit127: interop disabled; no setting changed',
                                  'Actual Windows Vitis Csim exit1 K26 part check'],
                  residual_notes=['65 native Cosim PASS plus 1 maxK original failure/postcheck recovered; not 66 native PASS',
                                  '5 WDB databases not supplied; raw TV/logs received and independently replayed',
                                  'AXI internal FIFO occupancy unmeasured; no user-stream FIFO; P2 instrumentation only',
                                  'HLS timing estimate is not implementation timing closure'],
                  new_commit=None, push=False,
                  next='Official current-host license then one current-source independent Csim; no B dependency/no full optimization rerun')
    with (E / 'REPORT.json').open('x', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    tooling = dict(provenance, owner='A', kernel_modified=False, overlays=portable['overlays'],
                   original_provider_tool_failure='PRESERVED', A_corrected_tool_status='PASS',
                   full_kernel_acceptance=False, evidence='evidence/A06_acceptance/a-owned-closeout-v1/REPORT.json')
    with (R / 'hw/linear_A/A_RECEIPT_TOOLING.json').open('x', encoding='utf-8') as f:
        json.dump(tooling, f, indent=2)
    print(json.dumps({'status': result['status'], 'vectors_exact': 382, 'awaiting_B': False}))


if __name__ == '__main__':
    main()
