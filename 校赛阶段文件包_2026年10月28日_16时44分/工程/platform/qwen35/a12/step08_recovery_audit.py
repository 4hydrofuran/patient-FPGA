"""Audit retained recovery outcomes and compare fresh boot diagnostics to prior irq2."""
import base64
import hashlib
import json
import re
import sys
from common import ROOT,sha,save
from step08_common import OUT
sys.path.insert(0,str(ROOT/'platform/qwen35/a10'))
from kernel_log_gate import diagnostics
def j(p):return json.loads(p.read_text(encoding='utf-8-sig'))

if __name__=='__main__':
    cold=j(OUT/'cold-recovery-once-02.json')
    assert cold['status']=='CANDIDATE_LOGIN_OBSERVED_READONLY_CHECK_REQUIRED' and cold['closed']
    assert cold['boot_commands_sent']==cold['autoboot_stop_bytes_sent']==1
    assert cold['reboot_commands_sent']==0 and cold['default_boot_changed'] is False
    assert j(OUT/'restore_readback_01/receipt.json')['exit_code']==0
    read=j(OUT/'restore_readback_01/stdout.txt');records={};folder=OUT/'normal-reboot-records';folder.mkdir()
    for name,row in read['records'].items():
        b=base64.b64decode(row['base64'],validate=True)
        assert len(b)==row['bytes'] and hashlib.sha256(b).hexdigest()==row['sha256']
        with (folder/name).open('xb') as f:f.write(b)
        records[name]=json.loads(b)
    assert records['pre-reboot.json']['locks_exclusively_held'] and records['reboot-command.json']['exit_code']==0
    assert read['kernel']=='6.8.12-a10irq2' and read['unsaved']=='b true'
    before=j(ROOT/'evidence/model_pl_A/20261024-step06-review-v1/preflight_01/stdout.txt')
    after=j(OUT/'preflight_04/stdout.txt')
    clean=lambda s:re.sub(r'^<\d+>\[\s*[\d.]+\]\s*','',s)
    prior={clean(r['text']) for r in diagnostics(before['kernel_raw'])}
    changed=[clean(r['text']) for r in diagnostics(after['kernel_raw']) if clean(r['text']) not in prior]
    patterns=(r'WARNING: CPU: \d+ PID: 1 at crypto/asymmetric_keys/x509_loader.c:44 x509_load_certificate_list\+0xf0/0x1a8',
        r'CPU: \d+ PID: 1 Comm: swapper/0 Not tainted 6.8.12-a10irq2 #1',
        r'x23: [0-9a-f]+ x22: [0-9a-f]+ x21: [0-9a-f]+')
    assert all(any(re.fullmatch(p,line) for p in patterns) for line in changed)
    save(OUT/'BOOT_RECOVERY_AUDIT.json',dict(status='RECOVERED_IRQ2_AND_VOLATILE_NETWORK_DEFAULT_BOOT_UNCHANGED',
        current_boot=read['boot_id'],kernel=read['kernel'],normal_reboots=1,user_reported_cold_cycles=1,
        candidate_boot_commands=1,default_boot_pins=read['pins'],network_unsaved=True,
        initial_boot_diagnostic_lines=len(diagnostics(after['kernel_raw'])),
        prior_accepted_boot_diagnostic_lines=len(diagnostics(before['kernel_raw'])),changed_diagnostic_lines=changed,
        diagnostic_disposition='Only CPU/register variation in the existing X.509 startup warning; all raw diagnostics retained. Not a clean-kernel claim.',
        warm_reboot_stall='UNRESOLVED_CAUSE_FSBL_ONLY_OBSERVED_PRESERVED',
        prior_passes_unchanged=True,restore_readback_sha256=sha(OUT/'restore_readback_01/stdout.txt')))
    print('RECOVERY_AUDIT_PASS_KNOWN_BASELINE_LIMITATIONS_RETAINED')
