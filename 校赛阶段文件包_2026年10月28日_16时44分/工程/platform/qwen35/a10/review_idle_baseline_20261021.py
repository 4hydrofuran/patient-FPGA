"""One exact, already inspected baseline review; not a reusable warning whitelist.

PC only. Any different capture, boot, diagnostic count or unknown diagnostic
fails. This acknowledges existing conditions for the authorized idle attempt;
it does not close defects or permit any future/new diagnostic.
"""
import json
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
from candidate_idle_trial import (KERNEL, MACHINE, DRIVER_SHA, REVIEW_SCOPE,
                                 validate_review, need)
from kernel_log_gate import diagnostics, digest
sys.path.insert(0, str(Path(__file__).resolve().parent / 'kernel_repair'))
from audit_candidate_boot_evidence import decode_log

ROOT = Path(__file__).resolve().parents[3]
E = ROOT / 'evidence/board_platform/A10_20261018_intake'
BOOT = '751e617d-c003-4b99-be03-bb5c78235d24'
RAW_SHA = '9a7a65b5df99d79c5f406396e0417aee70c13b4b900b2d83538bacc0750a3dc7'


def rationale(d):
    line = d['line']
    msg = re.sub(r'^<\d+>\[\s*[\d.]+\] ', '', d['text'])
    if line == 3 and msg == 'KASLR disabled due to lack of seed':
        return 'Existing boot hardening limitation, not a computation result. Isolated maintenance only; do not claim hardened production boot.'
    if line == 57 and msg.startswith('GIC: Adjusting CPU interface base to '):
        return 'Boot-time GIC base adjustment already recorded before any test overlay; not evidence for PL interrupt correctness. New IRQ diagnostics remain blocked.'
    if line == 221 and msg.startswith('mtdoops: mtd device '):
        return 'No mtdoops sink supplied. No flash/QSPI writes or deliberate crash tests are authorized; UART/PC capture is the evidence sink.'
    if line == 237 and msg.startswith('device-mapper: core: CONFIG_IMA_DISABLE_HTABLE '):
        return 'Existing IMA duplicate-measurement policy notice. No IMA, device-mapper or boot-security configuration is changed.'
    if 269 <= line <= 298 or line in (311, 317):
        return 'Existing boot-time X509 certificate parse/signature-trust defect remains OPEN, including its complete stack trace. Candidate and driver were hash/ABI-checked separately; permit only the isolated idle attempt, not a claim of trusted module loading. A new load failure/warning still stops.'
    if line == 316 and msg == 'sched: RT throttling activated':
        return 'Existing boot scheduler throttle notice; do not alter scheduling or disable protection. No real-time workload or performance result is authorized.'
    if msg == 'The requested pinctrl feature is not supported in the current firmware.' or msg.startswith('zynqmp-pinctrl firmware:zynqmp-firmware:pinctrl: '):
        return 'Existing firmware/pinctrl compatibility limitation remains OPEN. This attempt does not change boot firmware/MIO/pin configuration or exercise external I/O; it only checks the previously audited idle PL package. New messages still stop.'
    if line in (353, 356) and msg == 'fb0: Framebuffer is not in virtual address space.':
        return 'Existing framebuffer notice; display operation is not an acceptance claim. UART remains the maintenance channel.'
    if 'supply ' in msg and msg.endswith('not found, using dummy regulator') and msg.startswith(('onboard-usb-dev ', 'at24 ')):
        return 'Existing board description/regulator limitation remains OPEN. No USB/EEPROM power-control or external peripheral exercise is performed.'
    if line in (492, 493) and msg.startswith('cdns-wdt ') and 'Xilinx Watchdog Timer with timeout ' in msg:
        return 'Informational watchdog configuration line matched by the word timeout; not an observed timeout. Do not open, arm, disarm or reconfigure the watchdog.'
    if line == 519 and msg == 'clk: Not disabling unused clocks':
        return 'Existing clk_ignore_unused boot setting, unchanged from original boot. No clock/frequency optimization or power claim.'
    if line == 703 and msg == 'kauditd_printk_skb: 127 callbacks suppressed':
        return 'Existing boot audit-message rate limiting, retained as incomplete audit verbosity, not a hardware success. Any later loss of log continuity or new diagnostic stops the attempt.'
    if line in (705, 706) and msg.startswith('OF: overlay: WARNING: memory leak will occur if overlay removed, property: /fpga-region/'):
        return 'Existing default-overlay property-lifetime warning remains OPEN. This review is baseline-only for the specifically authorized one idle lifecycle, not permission for repeated cycling; any new warning or refcount diagnostic stops.'
    raise RuntimeError('Unreviewed diagnostic: ' + str(d))


def main():
    source = E / 'idle_window_raw_kernel_20261021_02.json'
    record = json.loads(source.read_text(encoding='utf-8-sig'))
    need(record['exit_code'] == 0 and BOOT in record['command'], 'wrong/incomplete collection')
    raw_bytes = decode_log(record['raw'])
    raw = raw_bytes.decode('utf-8', errors='strict')
    need(digest(raw) == RAW_SHA and 'Linux version ' + KERNEL + ' ' in raw, 'capture changed')
    found = diagnostics(raw)
    need(len(found) == 186, 'diagnostic inventory changed')
    review = dict(
        schema='A10_IDLE_BASELINE_REVIEW_V1', scope=REVIEW_SCOPE, boot_id=BOOT,
        kernel=KERNEL, machine_id_sha256=MACHINE, driver_sha256=DRIVER_SHA,
        compute_authorized=False, raw_dmesg_sha256=RAW_SHA,
        reviewer='Codex agent scoped review 2026-10-21; not independent human sign-off',
        review_rationale='All 186 entries of this exact captured baseline were inspected. Existing platform/security limitations remain OPEN. Authorization is the user-confirmed single idle window, not compute or production acceptance. New diagnostics are not waived.',
        source_receipt=str(source.relative_to(ROOT)).replace('\\', '/'),
        diagnostic_decisions=[dict(diagnostic=d, decision='ACCEPT_BASELINE_FOR_IDLE_ONLY',
                                   rationale=rationale(d)) for d in found])
    validate_review(review, raw)
    output = E / 'idle-window-review-20261021-v1'
    output.mkdir()
    with (output / 'baseline.raw.txt').open('xb') as stream:
        stream.write(raw_bytes)
    with (output / 'baseline.review.json').open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(review, indent=2) + '\n')
    print(json.dumps(dict(status='EXACT_BASELINE_REVIEW_ONLY_NOT_BOARD_ACCEPTANCE',
                         raw_sha256=RAW_SHA, diagnostics=len(found), output=str(output),
                         new_diagnostics_waived=False, board_contact=False), indent=2))


if __name__ == '__main__':
    main()
