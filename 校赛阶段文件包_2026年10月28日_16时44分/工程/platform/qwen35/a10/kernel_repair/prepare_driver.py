"""Create a SHA-pinned, separate XRT candidate; never edit the original package."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_kernel_refs_pc import function

PINS = {
    'zert/zocl_xgq_intc.c': '6faec55907a1854d108e9344f57e9e729635c7de41b2cc65957d1d6abf52a089',
    'common/cu.c': '90db03f6a5195c27ce69284dc86ef169d31f1ff6e261e5f31429ce96097d0341',
}


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Missing/ambiguous source anchor')
    return text.replace(old, new, 1)


def repair_intc(text, template):
    text = once(text, '#include <linux/platform_device.h>', '#include <linux/platform_device.h>\n#include <linux/mutex.h>')
    text = once(text, 'spinlock_t\t\t\tzei_lock;', 'struct mutex\t\t\tzei_lock;')
    text = once(text, '\tzintc->zei_num_irqs = num_irqs;', '\tzintc->zei_num_irqs = num_irqs;\n\tmutex_init(&zintc->zei_lock);')
    # Remove each old API once, then insert the reviewed functions before vtable.
    for name in ['zintc_remove', 'zocl_irq_intc_add', 'zocl_irq_intc_remove', 'zocl_irq_intc_config']:
        text = once(text, function(text, name)['text'], '')
    return once(text, 'static struct zocl_ert_intc_drv_data zocl_irq_intc_drvdata',
                template + '\nstatic struct zocl_ert_intc_drv_data zocl_irq_intc_drvdata')


def repair_cu(text):
    probe = function(text, 'cu_probe')['text']
    reg = ('\tif (info->intr_enable && info->protocol != CTRL_NONE) {\n'
           '\t\tintc = zocl_find_pdev(ERT_CU_INTC_DEV_NAME);\n'
           '\t\tif (intc)\n\t\t\terr = zocl_ert_intc_add(intc, info->intr_id, cu_isr, zcu);\n'
           '\t\tif (!intc || err) {\n\t\t\tDRM_WARN("Failed to initial CU interrupt. "\n'
           '\t\t\t\t "Fall back to polling\\n");\n\t\t\tzcu->base.info.intr_enable = 0;\n\t\t}\n\t}\n')
    changed = once(probe, reg, '')
    changed = once(changed, '\tplatform_set_drvdata(pdev, zcu);',
                   '\t/* Core, locks and semaphores must exist before IRQ registration. */\n' + reg + '\n\tplatform_set_drvdata(pdev, zcu);')
    changed = once(changed, '\tif (!zcu->irq_name)\n\t\treturn -ENOMEM;',
                   '\tif (!zcu->irq_name) {\n\t\terr = -ENOMEM;\n\t\tgoto err2;\n\t}')
    changed = once(changed, 'err2:\n\tzocl_kds_del_cu', 'err2:\n\tkfree(zcu->irq_name);\n\tzocl_kds_del_cu')
    text = once(text, probe, changed)
    remove = function(text, 'cu_remove')['text']
    irq = ('\tif (info->intr_enable) {\n\t\tintc = zocl_find_pdev(ERT_CU_INTC_DEV_NAME);\n'
           '\t\tif (intc)\n\t\t\tzocl_ert_intc_remove(intc, info->intr_id);\n\t}\n')
    attrs = ('\twrite_lock(&zcu->attr_rwlock);\n'
             '\tsysfs_remove_group(&pdev->dev.kobj, &cu_attrgroup);\n'
             '\twrite_unlock(&zcu->attr_rwlock);\n')
    changed = once(remove, irq, '')
    changed = once(changed, attrs, '')
    changed = once(changed, '\tinfo = &zcu->base.info;\n',
                   '\t/* Drain sysfs readers without holding their spin-based rwlock. */\n'
                   '\tsysfs_remove_group(&pdev->dev.kobj, &cu_attrgroup);\n'
                   '\tinfo = &zcu->base.info;\n'
                   '\t/* Drain IRQ callbacks while CU core and MMIO are still alive. */\n' + irq)
    return once(text, remove, changed)


def prepare(source, output):
    originals = {}
    for name, digest in PINS.items():
        raw = (source / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError('Original SHA mismatch: ' + name)
        originals[name] = raw.decode()
    template = Path(__file__).with_name('driver_irq_functions.inc').read_text()
    candidates = {'zert/zocl_xgq_intc.c': repair_intc(originals['zert/zocl_xgq_intc.c'], template),
                  'common/cu.c': repair_cu(originals['common/cu.c'])}
    output.mkdir(parents=True, exist_ok=False)
    manifest = {'schema': 'A10_XRT_IRQ_REPAIR_V1', 'source_package': 'xrt-dkms 2.18.0-0ubuntu1',
                'status': 'PC_CANDIDATE_NOT_BOARD_ACCEPTED', 'board_changes': False,
                'deployment_authorized': False, 'files': {},
                'limits': ['normal quiescent teardown only', 'no proof of active DMA recovery',
                           'vendor polling fallback retained and must be visible/rejected by IRQ acceptance gate']}
    patch = ''
    for name, old in originals.items():
        new = candidates[name]
        row = {}
        for kind, text in [('original', old), ('candidate', new)]:
            target = output / kind / name
            target.parent.mkdir(parents=True, exist_ok=True)
            data = text.encode()
            with target.open('xb') as f:
                f.write(data)
            row[kind + '_sha256'] = hashlib.sha256(data).hexdigest()
        manifest['files'][name] = row
        patch += ''.join(difflib.unified_diff(old.splitlines(True), new.splitlines(True), 'a/' + name, 'b/' + name))
    with (output / 'repair.patch').open('x', newline='\n') as f:
        f.write(patch)
    manifest['patch_sha256'] = hashlib.sha256(patch.encode()).hexdigest()
    with (output / 'manifest.json').open('x') as f:
        json.dump(manifest, f, indent=2)
    print(json.dumps(manifest))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    prepare(a.source, a.output)
