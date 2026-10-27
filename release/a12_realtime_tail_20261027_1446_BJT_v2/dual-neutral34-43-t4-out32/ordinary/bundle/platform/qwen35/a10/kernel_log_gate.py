"""Fail-closed kernel log continuity and diagnostics gate, with no device access.

No message is silently whitelisted. A separately reviewed baseline may be
acknowledged by its exact SHA256; new diagnostics always latch the gate closed.
This is a submission gate, not hardware isolation or a safe-to-unload proof.
"""
import hashlib
import re


class KernelLogBlocked(RuntimeError):
    pass


def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def diagnostics(text):
    found = []
    words = re.compile(r'\b(error|warning|warn|bug|oops|panic|failed|failure|fault|'
                       r'timeout|timed out|hung|lockup|unbalanced|corrupt\w*)\b|'
                       r'memory leak|call trace:|irq index \d+ not found', re.I)
    for index, line in enumerate(text.splitlines(), 1):
        priority = re.match(r'^<(\d+)>', line)
        severity = int(priority[1]) & 7 if priority else None
        if (severity is not None and severity <= 4) or words.search(line):
            found.append(dict(line=index, severity=severity, text=line))
    return found


class KernelLogGate:
    def __init__(self):
        self.previous = None
        self.boot_id = None
        self.blocked = False

    def observe(self, boot_id, text, reviewed_baseline_sha256=None):
        def fail(reason, **details):
            self.blocked = True
            return dict(allowed=False, reason=reason, **details)

        if self.blocked:
            return fail('LATCHED_BLOCKED')
        if not isinstance(boot_id, str) or not boot_id or not isinstance(text, str) or not text.strip():
            return fail('MISSING_KERNEL_LOG_OR_BOOT_ID')
        if not text.endswith('\n'):
            return fail('INCOMPLETE_KERNEL_LOG')
        if self.previous is None:
            found = diagnostics(text)
            if found and reviewed_baseline_sha256 != digest(text):
                return fail('UNREVIEWED_BASELINE_DIAGNOSTICS', diagnostics=found,
                            baseline_sha256=digest(text))
            self.previous, self.boot_id = text, boot_id
            return dict(allowed=True, reason='BASELINE_CAPTURED', baseline_sha256=digest(text),
                        baseline_diagnostics=found, baseline_reviewed=bool(found))
        if boot_id != self.boot_id:
            return fail('BOOT_CHANGED')
        if not text.startswith(self.previous):
            return fail('KERNEL_LOG_CONTINUITY_LOST')
        new = text[len(self.previous):]
        found = diagnostics(new)
        result = dict(previous_sha256=digest(self.previous), current_sha256=digest(text),
                      new_line_count=len(new.splitlines()), new_text=new, diagnostics=found)
        if found:
            return fail('NEW_KERNEL_DIAGNOSTIC', **result)
        self.previous = text
        return dict(allowed=True, reason='NO_NEW_DIAGNOSTIC', **result)
