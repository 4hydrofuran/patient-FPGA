"""Source-path assertions and small ownership models. NOT a running-kernel test.

Uses the exact Ubuntu source subset prepared by extract_kernel_refaudit.py and
the existing PC merged-DT audit. Never connects to, instruments, or modifies a board.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def function(text, name):
    match = re.search(r'^[A-Za-z_][A-Za-z0-9_ \t*]*\b' + re.escape(name) +
                      r'\([^;{}]*?\)\n\{', text, re.M)
    if not match:
        raise ValueError('missing function ' + name)
    start = text.index('{', match.start())
    depth = 1
    end = start + 1
    while depth and end < len(text):
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    if depth:
        raise ValueError('unbalanced function ' + name)
    return dict(line=text[:match.start()].count('\n') + 1, text=text[match.start():end])


def reference_model(extended, count, passes=1):
    # Successful direct-controller case only, no interrupt-map traversal.
    # parse_one acquires parent; parse_raw acquires it again; caller puts once.
    # The legacy interrupts path also puts parse_one's original parent.
    refs = 1
    for _ in range(count * passes):
        refs += 1  # parse_phandle_with_args / of_irq_find_parent
        refs += 1  # of_irq_parse_raw entry
        if not extended:
            refs -= 1  # parse_one out: of_node_put(p)
        refs -= 1  # of_irq_get / of_link_property caller
    return refs


def remove_model(mapped, nr_irq, fixed):
    remaining = set(mapped)
    removed = []
    i = 0
    while i < (nr_irq if fixed else len(remaining)):
        if i in remaining:
            remaining.remove(i)  # irq_dispose_mapping -> domain->mapcount--
            removed.append(i)
        i += 1
    return dict(removed=removed, remaining=sorted(remaining))


def audit(source, dt_audit):
    files = {}
    for name in ['drivers/of/irq.c', 'drivers/of/property.c',
                 'drivers/irqchip/irq-xilinx-intc.c', 'kernel/irq/irqdomain.c',
                 'drivers/base/platform.c']:
        files[name] = (source / name).read_text(encoding='utf-8')
    one = function(files['drivers/of/irq.c'], 'of_irq_parse_one')
    raw = function(files['drivers/of/irq.c'], 'of_irq_parse_raw')
    get = function(files['drivers/of/irq.c'], 'of_irq_get')
    link = function(files['drivers/of/property.c'], 'of_link_property')
    remove = function(files['drivers/irqchip/irq-xilinx-intc.c'], 'xilinx_intc_of_remove')
    dis = function(files['kernel/irq/irqdomain.c'], 'irq_domain_disassociate')
    checks = {
        'extended_returns_raw_without_put': bool(re.search(
            r'if \(!res\)\s+return of_irq_parse_raw\(addr, out_irq\);', one['text'])),
        'raw_gets_parent': 'ipar = of_node_get(out_irq->np);' in raw['text'],
        'raw_direct_success_without_put': bool(re.search(r'pr_debug\(" -> got it !.*?\n\s*return 0;', raw['text'])),
        'legacy_parent_put': 'of_node_put(p);' in one['text'],
        'irq_get_puts_once': get['text'].count('of_node_put(oirq.np);') == 1,
        'supplier_link_puts_once': link['text'].count('of_node_put(phandle);') == 1,
        'remove_uses_mutable_mapcount_bound': 'i < irqc->root_domain->mapcount' in remove['text'],
        'remove_disposes_child_mapping': 'irq_dispose_mapping(tempirq);' in remove['text'],
        'disassociate_decrements_mapcount': 'domain->mapcount--;' in dis['text'],
    }
    if not all(checks.values()):
        raise ValueError('source changed or unsupported path: ' + repr(checks))
    dt = json.loads(dt_audit.read_text(encoding='utf-8'))
    cells = [int(word, 16) for word in dt['zocl_interrupts_extended'].split()]
    if len(cells) != 96 or len(set(cells[::3])) != 1 or cells[1::3] != list(range(32)) or cells[2::3] != [4] * 32:
        raise ValueError('unexpected IRQ topology; cannot apply this model')
    return dict(domain='PC_SOURCE_AND_OWNERSHIP_MODEL_NOT_BOARD',
                source_package='linux-xilinx 6.8.0-1015.16', source_checks=checks,
                files={name: dict(sha256=sha(source / name)) for name in files},
                extraction_manifest_sha256=sha(source / 'extraction.json'),
                dt_audit_sha256=sha(dt_audit), irq_count=32,
                function_locations={'of_irq_parse_one': one['line'], 'of_irq_parse_raw': raw['line'],
                                    'of_irq_get': get['line'], 'of_link_property': link['line'],
                                    'xilinx_intc_of_remove': remove['line'], 'irq_domain_disassociate': dis['line']},
                reference_model=dict(start=1, extended_one_pass=reference_model(True, 32),
                                     extended_two_passes=reference_model(True, 32, 2),
                                     legacy_two_passes=reference_model(False, 32, 2),
                                     meaning='Two successful enumeration passes explain 64 extra refs; actual call counts not traced'),
                removal_model=dict(original=remove_model(range(32), 32, False),
                                   fixed_bound_model=remove_model(range(32), 32, True),
                                   meaning='Conditional on this remove path and 32 mapped IRQs; not measured runtime mappings'),
                board_changes=False, kernel_patch_installed=False, deployment_allowed=False,
                A10='NOT_PASSED_KERNEL_RECOVERY_RISK_OPEN')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--dt-audit', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    a = ap.parse_args()
    result = audit(a.source, a.dt_audit)
    with a.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
