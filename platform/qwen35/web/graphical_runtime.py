"""Small, explicit adaptations for a PS desktop beside the accepted PL owner."""
import json
from pathlib import Path
import queue
import re
import time


def graphical_gate(base):
    helpers=base.observe_action.__globals__
    class GraphicalGate(base):
        def observe_action(self,boot,raw,baseline_sha,action,verified_32_irq_dt=False):
            if (self.previous is None or self.blocked or boot!=self.boot_id
                    or not raw.startswith(self.previous) or not raw.endswith('\n')):
                return super().observe_action(boot,raw,baseline_sha,action,verified_32_irq_dt)
            new=raw[len(self.previous):]
            allowed=set(helpers['reviewed_messages'](action))
            if action=='load_test' and verified_32_irq_dt:allowed.add(helpers['IRQ_END'])
            accepted=[];rejected=[];seen=set()
            for entry in helpers['diagnostics'](new):
                message=re.sub(r'^<\d+>\[\s*\d+(?:\.\d+)?\]\s*','',entry['text'])
                audit=(entry['severity']==4 and re.fullmatch(r'kauditd_printk_skb: [1-9][0-9]* callbacks suppressed',message))
                if audit:
                    accepted.append(dict(entry,review='AUDIT_RATE_LIMIT_NOTICE_NOT_ACCELERATOR_DIAGNOSTIC'))
                elif message in allowed and message not in seen:
                    accepted.append(entry);seen.add(message)
                else:rejected.append(entry)
            result=dict(previous_sha256=helpers['digest'](self.previous),current_sha256=helpers['digest'](raw),
                        new_text=new,action=action,reviewed_advisories=accepted,rejected_diagnostics=rejected)
            if rejected:
                self.blocked=True
                return dict(allowed=False,reason='UNREVIEWED_OR_DUPLICATE_DIAGNOSTIC',**result)
            self.previous=raw
            return dict(allowed=True,reason='NO_UNREVIEWED_DIAGNOSTIC',**result)
    return GraphicalGate


def settle_terminal(transport,timeout=10):
    """Collect a failed call's final message without authorizing or delivering work."""
    if not transport.inflight:return True
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        try:result=transport.worker.messages.get(timeout=min(.25,max(.001,deadline-time.monotonic())))
        except queue.Empty:continue
        if result is None:return False
        if result.get('type') in ('result','error','cache_created'):
            if result.get('id')!=transport.pending_id:
                raise RuntimeError('Foreign terminal response during failed-call cleanup')
            transport.last_result=result;transport.inflight=False
            transport.api.save(transport.path/'failed-call-terminal.json',dict(delivered=False,response=result))
            return True
    return False


def prepare_profile(profile):
    profile=Path(profile);profile.mkdir(parents=True,exist_ok=True)
    preferences={'layers.acceleration.disabled':True,'gfx.webrender.software':True,
                 'webgl.disabled':True,'browser.shell.checkDefaultBrowser':False,
                 'browser.startup.homepage_override.mstone':'ignore'}
    (profile/'user.js').write_text(''.join('user_pref('+json.dumps(k)+','+json.dumps(v)+');\n' for k,v in preferences.items()))
