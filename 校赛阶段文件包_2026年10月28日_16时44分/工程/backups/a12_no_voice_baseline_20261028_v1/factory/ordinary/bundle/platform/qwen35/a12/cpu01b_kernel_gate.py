import cpu01b_observer as ob
"""Exact action-scoped advisories for the user-approved bounded A10 window.

These remain recorded limitations, not fixed defects. All other diagnostics
and lost log continuity latch shut. Never waive IRQ/refcount errors.
"""
import re
from kernel_log_gate import KernelLogGate, diagnostics
from cpu02_support import digest
TEST_PROPERTIES = ('/fpga-region/firmware-name', '/__symbols__/misc_clk_0', '/__symbols__/clocking0', '/__symbols__/afi0', '/__symbols__/axi_intc_0', '/__symbols__/axi_vip_pltf', '/__symbols__/w4a8_linear_v1_1')
DEFAULT_PROPERTIES = ('/fpga-region/firmware-name', '/fpga-region/resets')
PREFIX = 'OF: overlay: WARNING: memory leak will occur if overlay removed, property: '
IRQ_END = 'zocl-drm axi:zyxclmm_drm: error -ENXIO: IRQ index 32 not found'

def reviewed_messages(action):
    if action == 'load_test':
        return {PREFIX + p for p in TEST_PROPERTIES}
    if action == 'load_default':
        return {PREFIX + p for p in DEFAULT_PROPERTIES}
    if action == 'insmod':
        return {'zocl: loading out-of-tree module taints kernel.'}
    return set()

class MinimalGate(KernelLogGate):

    def observe_action(self, boot, raw, baseline_sha, action, verified_32_irq_dt=False):
        with ob.span('health.kernel_gate_total'):
            if self.previous is None or self.blocked:
                return self.observe(boot, raw, baseline_sha)
            if boot != self.boot_id or (raw is not self.previous and not raw.startswith(self.previous)) or (not raw.endswith('\n')):
                return self.observe(boot, raw, baseline_sha)
            new = raw[len(self.previous):]
            allowed, seen = (reviewed_messages(action), set())
            if action == 'load_test' and verified_32_irq_dt:
                allowed.add(IRQ_END)
            accepted, rejected = ([], [])
            for entry in diagnostics(new):
                message = re.sub('^<\\d+>\\[\\s*\\d+(?:\\.\\d+)?\\]\\s*', '', entry['text'])
                if message in allowed and message not in seen:
                    accepted.append(entry)
                    seen.add(message)
                else:
                    rejected.append(entry)
            result = dict(previous_sha256=digest(self.previous), current_sha256=digest(raw), new_text=new, action=action, reviewed_advisories=accepted, rejected_diagnostics=rejected)
            if rejected:
                self.blocked = True
                return dict(allowed=False, reason='UNREVIEWED_OR_DUPLICATE_DIAGNOSTIC', **result)
            self.previous = raw
            return dict(allowed=True, reason='NO_UNREVIEWED_DIAGNOSTIC', **result)
