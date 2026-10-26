"""使用技能同一个formatter AST复核case位宽和例外身份；不改门禁结论。"""
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[4]
SRC = Path(__file__).resolve().parent
E = ROOT / 'evidence/a13_A/20261025-audio-codec-master-v1'
SKILL = Path('C:/Users/Fang/.codex/skills/verilog-generator')
sys.path.insert(0, str(SKILL))
from scripts.python.quality.formatter_ast import build_ast_report_for_path
from scripts.python.quality.formatter_backend.expression_facts import _parsed_expression
from scripts.python.quality.vg_branch_rules import _header_expression, _iter_case_labels
from scripts.python.quality.vg_value_facts import module_widths, module_constant_values, resolve_constant_bits

TARGETS = {'s_axis_tready_o', 'm_axis_tdata_o', 'm_axis_tlast_o', 'reg_tx_command',
    'reg_rx_command', 'reg_rx_channel', 'reg_tx_frame', 'flag_tx_pending', 'reg_tx_shift',
    'cnt_tx_period', 'reg_rx_right', 'cnt_watchdog', 'reg_fault'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def node_width(node, widths):
    """只消费已解析的concat/identifier/固定bit-select；未知节点一律阻断。"""
    if node['kind'] == 'identifier':
        return widths[node['name']]
    if node['kind'] == 'concat':
        return sum(node_width(child, widths) for child in node['operands'])
    if node['kind'] == 'select' and node['operator'] == 'bit' and not node['dynamic']:
        return 1
    raise ValueError(('Unsupported formatter AST width node', node))


def main():
    out = E / 'static-audit-final'
    out.mkdir(exist_ok=False)
    gate = json.loads((E / 'gate11.json').read_text(encoding='utf-8'))
    assert gate['delivery_ready'] is False
    assert gate['delivery_issues_by_rule'] == {'VG066': 1, 'VG084': 1, 'VG138': 10, 'VG146': 13}
    review = []
    attribute_findings = []
    for finding in gate['issues']:
        if finding['code'] == 'VG138':
            source = (SRC / 'rtl' / finding['path']).read_text(encoding='utf-8').splitlines()
            line = source[finding['line'] - 1]
            assert '(* X_INTERFACE_INFO = "xilinx.com:' in line
            attribute_findings.append({'line': finding['line'], 'source': line,
                                       'classification': 'METADATA_STRING_NOT_ARITHMETIC_LITERAL',
                                       'raw_status_unchanged': True})
        if finding['code'] != 'VG146':
            continue
        detail = finding['evidence']['detail']
        target = re.search(r'; target=([^;]+);', detail).group(1)
        count = int(re.search(r'operation_count=(\d+);', detail).group(1))
        assert target in TARGETS and 3 < count <= 5
        assert 'limit=3' in detail and 'loop_presence=absent' in detail
        review.append({'target': target, 'operation_count': count, 'raw_status': 'FAIL',
                       'user_permission': 'TARGETED_REVIEW_ONLY_20261025',
                       'acceptance': 'PENDING_EXACT_SOURCE_XSIM_ROUTED_STA_AND_CDC'})
    assert {v['target'] for v in review} == TARGETS
    checks = []
    for path in sorted((SRC / 'rtl').glob('*.v')):
        ast = build_ast_report_for_path(path)
        assert not ast['diagnostics'] and not ast['formatter_violations']
        (out / (path.stem + '_ast.json')).write_text(json.dumps(ast, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        for module in ast['modules']:
            assert all(block['clock'] == 'i_clk' for block in module['always'])
            widths = module_widths(module)
            constants = module_constant_values(module)
            for case, label in _iter_case_labels(module):
                if label.lower() == 'default':
                    continue
                expression = _header_expression(case['header'])
                tree = _parsed_expression(expression, 'A13-manual-width-fact')
                width = node_width(tree, widths)
                bits = resolve_constant_bits(label, constants)
                assert bits is not None and bits.width == width, (expression, label, width)
                checks.append({'module': module['name'], 'selector': expression,
                               'label': label, 'selector_bits': width, 'label_bits': bits.width})
    assert len(checks) > 30
    value = {'status': 'PASS_SUPPLEMENTARY_AST_REVIEW_NOT_RAW_GATE_PASS',
             'raw_gate_ready': False, 'raw_gate_sha256': sha(E / 'gate11.json'),
             'public_gates': gate['checks'], 'case_width_checks': checks,
             'targeted_operation_exceptions': review,
             'attribute_string_false_positive_review': attribute_findings,
             'other_raw_findings_not_waived': ['VG066_FORMATTER_INSERTED_PROTOCOL_NAVIGATION',
                                             'VG084_CONCAT_WIDTH_INCONCLUSIVE',
                                             'VG138_METADATA_STRINGS_NOT_ARITHMETIC'],
             'formatter_backend_owner': str(SKILL), 'second_verilog_parser_added': False,
             'rtl_sha256': {p.name: sha(p) for p in sorted((SRC / 'rtl').glob('*.v'))},
             'BOARD': 'NOT_TESTED', 'deployment_allowed': False}
    (out / 'RESULT.json').write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'status': value['status'], 'width_checks': len(checks), 'exceptions': len(review)}))


if __name__ == '__main__':
    main()
