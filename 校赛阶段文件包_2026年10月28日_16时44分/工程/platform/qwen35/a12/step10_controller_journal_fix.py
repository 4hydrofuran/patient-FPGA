"""Keep rejected observations durable even when the log payload is unchanged."""
import json,shutil
from common import ROOT,sha,save
from step10_common import OUT
if __name__=='__main__':
    p=ROOT/'platform/qwen35/a12/step10_manager.py'
    shutil.copyfile(p,OUT/'manager-before-journal-rejection-guard.py')
    s=p.read_text(encoding='utf-8');a='            if last and now-last[0]<1_000_000_000 and fingerprint==last[1]:return'
    b="            if last and now-last[0]<1_000_000_000 and fingerprint==last[1] and (event!='KERNEL_LOG_GATE' or data['allowed'] is True):return"
    assert s.count(a)==1;s=s.replace(a,b);p.write_text(s,encoding='utf-8',newline='\n')
    (OUT/'FROZEN_CONTROLLERS.json').rename(OUT/'FROZEN_CONTROLLERS-v1.json')
    frozen=json.loads((OUT/'FROZEN_CONTROLLERS-v1.json').read_text(encoding='utf-8'));frozen['files']['step10_manager.py']=sha(p)
    frozen['revision']='Rejected gate observations are always durably recorded; before first BOARD compute'
    save(OUT/'FROZEN_CONTROLLERS.json',frozen)
