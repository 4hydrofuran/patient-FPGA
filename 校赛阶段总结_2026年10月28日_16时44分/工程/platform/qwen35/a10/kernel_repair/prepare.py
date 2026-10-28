"""Produce a NEW PC-only kernel patch candidate from SHA-pinned source files.

This is a derived-source generator, not a system installer. Originals remain
unchanged. No SSH, device opens, module loading, or boot-media operations.
"""
import argparse
import difflib
import hashlib
import json
from pathlib import Path

PINNED = {
    'drivers/of/irq.c': '6b1eeb06ae1f40b05b5f35f41985bf8d3547ea77d54a5eabb7c4e1adcaa580a2',
    'drivers/irqchip/irq-xilinx-intc.c': '2b2fa4b7ae737ee9bfce05effacb3108feae436490cb6dfee15c056694fc8091',
    'drivers/irqchip/irqchip.c': 'f6fcbc340927a484670aece4ec299c8d810033909b510ade86171ec178060983',
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('ambiguous/missing source anchor')
    return text.replace(old, new, 1)


def repair(name, text):
    if name == 'drivers/of/irq.c':
        # Semantic backport of upstream 0cb58d6c7b55; retain 6.8 goto-out cleanup
        # instead of introducing a new __free() cleanup API dependency.
        text = once(text,
                    '\tif (!res)\n\t\treturn of_irq_parse_raw(addr, out_irq);',
                    '\tif (!res) {\n\t\tp = out_irq->np;\n'
                    '\t\tres = of_irq_parse_raw(addr, out_irq);\n\t\tgoto out;\n\t}')
        # Upstream 962a2805e47b: also balance the parent-controller mapping call.
        text = once(text, '\tstruct of_phandle_args oirq;\n\n\tif (of_irq_parse_one(dev, index, &oirq))',
                    '\tstruct of_phandle_args oirq;\n\tunsigned int ret;\n\n'
                    '\tif (of_irq_parse_one(dev, index, &oirq))')
        text = once(text, '\treturn irq_create_of_mapping(&oirq);',
                    '\tret = irq_create_of_mapping(&oirq);\n\tof_node_put(oirq.np);\n\n\treturn ret;')
        return text
    if name == 'drivers/irqchip/irq-xilinx-intc.c':
        # A-owned fix. mapcount is neither a stable bound nor maximum hwirq + 1.
        # No changes to MMIO ordering, clocks, device-tree topology, or DMA policy.
        return once(text, '\t\tfor (i = 0; i < irqc->root_domain->mapcount; i++) {',
                    '\t\t/* Mappings may be sparse; disposal decrements mapcount. */\n'
                    '\t\tfor (i = 0; i < irqc->nr_irq; i++) {')
    if name == 'drivers/irqchip/irqchip.c':
        # Experimental path owns the of_irq_find_parent reference until detach.
        # devres also releases on failed/deferred probe; never put an arbitrary
        # count or prematurely drop the reference saved in parent_node.
        text = once(text, '#else\nint platform_irqchip_probe(struct platform_device *pdev)',
                    '#else\nstatic void a10_irqchip_parent_put(void *data)\n'
                    '{\n\tof_node_put(data);\n}\n\n'
                    'int platform_irqchip_probe(struct platform_device *pdev)')
        text = once(text,
                    '\tirqchip = devm_kzalloc(&pdev->dev, sizeof(*irqchip), GFP_KERNEL);\n'
                    '\tif (!irqchip)\n\t\treturn -ENOMEM;\n',
                    '\tirqchip = devm_kzalloc(&pdev->dev, sizeof(*irqchip), GFP_KERNEL);\n'
                    '\tif (!irqchip) {\n\t\tof_node_put(par_np);\n\t\treturn -ENOMEM;\n\t}\n\n'
                    '\tif (par_np == np) {\n\t\tof_node_put(par_np);\n\t\tpar_np = NULL;\n\t}\n'
                    '\tif (par_np) {\n\t\tint ret;\n\n'
                    '\t\tret = devm_add_action_or_reset(&pdev->dev,\n'
                    '\t\t\t\t\t       a10_irqchip_parent_put, par_np);\n'
                    '\t\tif (ret)\n\t\t\treturn ret;\n\t}\n')
        return text
    raise ValueError('source not allowlisted')


def prepare(source, output):
    originals = {}
    for name, expected in PINNED.items():
        data = (source / name).read_bytes()
        if sha(data) != expected:
            raise ValueError('SHA mismatch: ' + name)
        originals[name] = data.decode('utf-8')
    changed = {name: repair(name, text) for name, text in originals.items()}
    output.mkdir(parents=True, exist_ok=False)
    patch = ''
    manifest = dict(schema='A10_KERNEL_REPAIR_CANDIDATE_V1',
                    source_package='linux-xilinx 6.8.0-1015.16',
                    status='PC_SOURCE_CANDIDATE_NOT_BOOTABLE_NOT_BOARD_ACCEPTED',
                    deployment_authorized=False, board_changes=False, files={},
                    upstream_commits=['0cb58d6c7b558a69957fabe159bfb184196e1e8d',
                                      '962a2805e47b933876ba0e4c488d9e89ced2dd29'],
                    local_fix='A-owned stable nr_irq bound and experimental parent devres ownership; normal quiescent remove only',
                    unresolved=['active/chained IRQ teardown synchronization not proved',
                                'complete kernel/modules build and rollback boot validation'])
    for name in originals:
        for directory, text in [('original', originals[name]), ('candidate', changed[name])]:
            path = output / directory / name
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('x', encoding='utf-8', newline='\n') as stream:
                stream.write(text)
        patch += ''.join(difflib.unified_diff(originals[name].splitlines(keepends=True),
                                             changed[name].splitlines(keepends=True),
                                             fromfile='a/' + name, tofile='b/' + name))
        manifest['files'][name] = dict(original_sha256=PINNED[name],
                                      candidate_sha256=sha(changed[name].encode()))
    with (output / 'repair.patch').open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(patch)
    manifest['patch_sha256'] = sha(patch.encode())
    with (output / 'manifest.json').open('x', encoding='utf-8') as stream:
        json.dump(manifest, stream, indent=2)
    return manifest


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    print(json.dumps(prepare(args.source, args.output)))
