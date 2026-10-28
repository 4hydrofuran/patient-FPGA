"""PC-only incremental fix for the preserved A10 empty-unload double free.

Never edits a booted source tree/image or contacts the board. The lifecycle
harness compiles the actual remove function with no-MMIO stubs; it is NOT a
kernel/IRQ concurrency test or board acceptance.
"""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import subprocess

SOURCE_SHA = '2306934f1a7ca152a4732b3a1f7807c1d20d54a3cfe5e5c3fad2a36f35d3252a'


def repair(text):
    anchor = '\tiounmap(irqc->base);\n\tkfree(irqc);'
    if text.count(anchor) != 2:
        raise ValueError('expected exactly init-error and normal-remove frees')
    replacement = (
        '\t/* The dynamic OF node destructor also frees node->data. */\n'
        '#ifdef CONFIG_IRQCHIP_XILINX_INTC_MODULE_SUPPORT_EXPERIMENTAL\n'
        '\tif (intc->data == irqc)\n'
        '\t\tintc->data = NULL;\n'
        '#endif\n' + anchor)
    return text.replace(anchor, replacement)


def remove_function(text):
    start = text.index('static int xilinx_intc_of_remove(')
    end = text.index('\nstatic struct irqc_init_remove_funps', start)
    return text[start:end]


PREFIX = r'''
#include <stdlib.h>
#include <stddef.h>
#include <stdio.h>
#define CONFIG_IRQCHIP_XILINX_INTC_MODULE_SUPPORT_EXPERIMENTAL 1
#define IER 0
#define IAR 1
#define MER 2
struct device_node {void *data;};
struct domain {unsigned mapcount;};
struct xintc_irq_chip {int irq; struct domain *root_domain; unsigned nr_irq; void *base;};
static void irq_set_chained_handler_and_data(int i, void *a, void *b){(void)i;(void)a;(void)b;}
static unsigned irq_find_mapping(struct domain *d, unsigned i){(void)d;(void)i;return 0;}
static void irq_dispose_mapping(unsigned i){(void)i;}
static void irq_domain_remove(struct domain *d){(void)d;}
static void xintc_write(struct xintc_irq_chip *c, int reg, unsigned v){(void)c;(void)reg;(void)v;}
static void iounmap(void *p){(void)p;}
#define kfree free
'''
SUFFIX = r'''
int main(void){
    struct device_node node={0}, parent={0};
    struct xintc_irq_chip *irqc=calloc(1,sizeof(*irqc));
    if(!irqc)return 2;
    node.data=irqc;
    irqc->irq=5;
    if(xilinx_intc_of_remove(&node,&parent))return 3;
    /* Actual dynamic.c:388 performs this free on node destruction. */
    free(node.data);
    puts("LIFECYCLE_HARNESS_ONLY_NOT_BOARD");
    return 0;
}
'''


def prepare_and_test(source, output):
    raw = source.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA:
        raise ValueError('candidate source hash differs')
    old = raw.decode()
    new = repair(old)
    output.mkdir()
    (output / 'original.c').write_bytes(raw)
    (output / 'candidate.c').write_text(new)
    (output / 'repair.patch').write_text(''.join(difflib.unified_diff(
        old.splitlines(True), new.splitlines(True),
        fromfile='a/drivers/irqchip/irq-xilinx-intc.c',
        tofile='b/drivers/irqchip/irq-xilinx-intc.c')))
    report = dict(status='PC_ONLY_NOT_BOARD_ACCEPTED', board_contact=False,
                  original_sha256=SOURCE_SHA,
                  candidate_sha256=hashlib.sha256(new.encode()).hexdigest(), commands=[])
    for name, text in [('original', old), ('candidate', new)]:
        harness = output / (name + '_lifecycle.c')
        harness.write_text(PREFIX + remove_function(text) + SUFFIX)
        exe = output / (name + '_lifecycle')
        argv = ['gcc', '-std=c11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                '-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-no-pie',
                str(harness), '-o', str(exe)]
        p = subprocess.run(argv, capture_output=True, text=True)
        report['commands'].append(dict(argv=argv, exit_code=p.returncode, stdout=p.stdout, stderr=p.stderr))
        if p.returncode:
            raise RuntimeError('harness compile failed')
        p = subprocess.run([str(exe)], capture_output=True, text=True)
        report['commands'].append(dict(argv=[str(exe)], exit_code=p.returncode, stdout=p.stdout, stderr=p.stderr))
        expected = p.returncode != 0 and 'double-free' in p.stderr if name == 'original' else p.returncode == 0
        if not expected:
            report['status'] = 'UNEXPECTED_HARNESS_RESULT'
            break
    (output / 'audit.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(dict(status=report['status'], output=str(output))))
    if report['status'] != 'PC_ONLY_NOT_BOARD_ACCEPTED':
        raise RuntimeError('lifecycle evidence mismatch')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    prepare_and_test(args.source, args.output)
