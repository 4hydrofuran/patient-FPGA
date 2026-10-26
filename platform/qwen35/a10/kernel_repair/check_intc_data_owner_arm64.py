"""Cross-compile only the revised TU with the exact existing kernel flags.

Original build/source files remain untouched. No linking, signing, image
generation, upload or board access.
"""
import hashlib
import json
from pathlib import Path
import shlex
import subprocess

BASE = Path('/home/member-a/a10-kernel-full-20261019-v1')
OUT = Path('/mnt/c/Patientqwen/platform/build/a10-intc-data-owner-20261021-v1')
source = OUT / 'candidate.c'
if hashlib.sha256(source.read_bytes()).hexdigest() != '3e9b896dc046f2bbfa2208ff78f7fc0c136a98318e45f0cfe4ff90fcca8a4a07':
    raise RuntimeError('unreviewed revision')
cmdfile = BASE / 'build/drivers/irqchip/.irq-xilinx-intc.o.cmd'
line = cmdfile.read_text().splitlines()[0]
prefix = 'savedcmd_drivers/irqchip/irq-xilinx-intc.o := '
if not line.startswith(prefix):
    raise RuntimeError('unexpected kernel command')
argv = shlex.split(line[len(prefix):])
original = str(BASE / 'source/drivers/irqchip/irq-xilinx-intc.c')
if argv[0] != 'aarch64-amd-linux-gcc' or argv.count(original) != 1 or argv.count('-o') != 1:
    raise RuntimeError('compiler/source/output differs')
obj = OUT / 'irq-xilinx-intc.revised.o'
if obj.exists():
    raise RuntimeError('output exists')
argv[argv.index(original)] = str(source)
argv[argv.index('-o') + 1] = str(obj)
dep = '-Wp,-MMD,drivers/irqchip/.irq-xilinx-intc.o.d'
if argv.count(dep) != 1:
    raise RuntimeError('dependency output differs')
argv[argv.index(dep)] = '-Wp,-MMD,' + str(OUT / 'irq-xilinx-intc.revised.d')
commands = [argv,
    ['aarch64-amd-linux-objdump', '-d', '--disassemble=of_node_release', str(BASE / 'build/vmlinux')],
    ['aarch64-amd-linux-objdump', '-d', '--disassemble=xilinx_intc_of_remove', str(obj)]]
report = dict(status='ARM64_TU_ONLY_NOT_FULL_KERNEL_NOT_BOARD',
              original_command_sha256=hashlib.sha256(cmdfile.read_bytes()).hexdigest(), commands=[])
with (OUT / 'arm64_audit.json').open('x') as stream:
    for cmd in commands:
        p = subprocess.run(cmd, cwd=BASE / 'build', capture_output=True, text=True)
        report['commands'].append(dict(argv=cmd, exit_code=p.returncode, stdout=p.stdout, stderr=p.stderr))
        if p.returncode:
            report['status'] = 'FAILED'
            break
    if obj.exists():
        report['object_sha256'] = hashlib.sha256(obj.read_bytes()).hexdigest()
    json.dump(report, stream, indent=2)
print(json.dumps({k: v for k, v in report.items() if k != 'commands'}))
if report['status'] == 'FAILED':
    raise SystemExit(1)
