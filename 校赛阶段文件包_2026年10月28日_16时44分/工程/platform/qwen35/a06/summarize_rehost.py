"""Validate actual Vitis receipts; write incremental evidence, never old reports."""
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]
E = ROOT / 'evidence/A06_acceptance'
OUT = E / 'license-rehost-v1'

def main():
    results = []
    for variant in ['baseline', 'reuse', 'double']:
        path = E / f'csim-retry-rehost-20261003-v2/{variant}.json'
        receipt = json.loads(path.read_text())
        assert receipt['exit_code'] == 0, variant
        output = receipt['stdout'] + receipt['stderr']
        summaries = re.findall(r'^SUMMARY (\{.*\})\s*$', output, re.M)
        assert len(summaries) == 1, variant
        summary = json.loads(summaries[0])
        assert summary['status'] == 'PASS' and summary['cases'] == 61 and summary['checks'] == 2800022
        assert 'CSim done with 0 errors' in output
        results.append(dict(variant=variant, exit_code=0, summary=summary,
                            log=path.relative_to(ROOT).as_posix(),
                            sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    report = {
        'stage': 'A06', 'status': 'NOT_ACCEPTED_B_DELIVERY_BLOCKED',
        'license': {'installed': '/home/member-a/.Xilinx/kv260-a-rehost-20261003.lic',
                    'sha256': '46ef2a17d5100e55d7181a8e9b7acc4d79580852a921cdea6c5eeccb33bf177f',
                    'host_id': '00155dbc2453', 'validation': 'PASS_ACTUAL_VITIS_2026_1_CSIM',
                    'vivado_synthesis_implementation': 'NOT_TESTED_THIS_RETRY',
                    'persistent_mac_guarantee': False, 'previous_license_unchanged': True},
        'results': results, 'total_cases': 183, 'total_checks': 8400066,
        'PC': 'PRIOR_PASS_PRESERVED_NOT_RERUN', 'Csim': 'PASS_3_VARIANTS',
        'Cosim': 'NOT_TESTED_THIS_RETRY', 'synthesis': 'NOT_TESTED_THIS_RETRY',
        'implementation': 'NOT_TESTED', 'aarch64_build': 'NOT_TESTED', 'BOARD': 'NOT_TESTED',
        'hardware_error': None, 'production_kernel_accepted': False,
        'prior_failure': 'v1 exit1 KeyError: Windows backslash manifest key; preserved; v2 normalizes paths and verifies every original input hash',
        'blockers': ['B final variant not selected', 'actual XO and embedded metadata missing',
                     'B raw Cosim and historical build identity gaps remain'],
        'new_commit': None, 'push': False}
    with (OUT / 'REPORT.json').open('x', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(json.dumps({'status': report['status'], 'Csim': report['Csim'], 'cases': 183, 'checks': 8400066}))

if __name__ == '__main__':
    main()
