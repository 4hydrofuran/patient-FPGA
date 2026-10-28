"""Check journal compaction does not skip checks or hide changed/rejected kernel observations."""
import ast,hashlib,json,threading,time,types
from pathlib import Path
from common import ROOT,save
from step10_common import OUT
from step08_health import compact_kernel_record

if __name__=='__main__':
    tree=ast.parse((ROOT/'platform/qwen35/a12/step10_manager.py').read_text(encoding='utf-8'))
    classes=[n for n in tree.body if isinstance(n,ast.ClassDef) and n.name in ('Platform','Owner')]
    class Base:
        def emit(self,event,**data):self.rows.append(dict(event=event,**data))
    ns=dict(IsolatedIdleTrial=Base,Window=Base,Path=Path,time=time,threading=threading,
            compact_kernel_record=compact_kernel_record,SPEC=dict(compact_health_journal=True))
    checks={'kernel':0,'live':0}
    def live(boot,full_resident=False):checks['live']+=1;return dict(memory_kib={'MemAvailable':3000000,'CmaFree':200000},full_resident=full_resident)
    ns['live_snapshot']=live
    exec(compile(ast.Module(body=classes,type_ignores=[]),'actual_task10_controller_classes','exec'),ns)
    p=ns['Platform'].__new__(ns['Platform']);p.run=OUT/'pc-journal';p.run.mkdir();p.rows=[];p.gate_lock=threading.RLock()
    raw='unchanged kernel\n';pin=hashlib.sha256(raw.encode()).hexdigest()
    def observe(allowed=True):
        checks['kernel']+=1
        p.emit('KERNEL_LOG_GATE',raw_log=raw,allowed=allowed,current_sha256=pin)
    observe();first=p.latest_kernel['observation_monotonic_ns'];observe()
    assert len(p.rows)==1 and p.latest_kernel['observation_monotonic_ns']>first
    observe(False);assert len(p.rows)==2 and not p.latest_kernel['allowed']
    p.emit('PROCESS_RELEASE_OBSERVATION',scan_complete=True);assert len(p.rows)==3
    owner=ns['Owner'].__new__(ns['Owner']);owner.platform=p
    owner.boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip();owner.full_resident=True
    p.kernel_checkpoint=lambda phase:observe()
    observations=[owner.health() for _ in range(4)]
    assert checks==dict(kernel=7,live=4)
    assert all(r['checks_skipped'] is False and r['kernel']['allowed'] for r in observations)
    assert len({r['checked_monotonic_ns'] for r in observations})==4
    assert len([r for r in p.rows if r['event']=='LIVE_HEALTH'])==1
    ns['SPEC']['compact_health_journal']=False
    count=len(p.rows);owner.health();owner.health();assert len(p.rows)==count+4
    save(OUT/'JOURNAL_PC.json',dict(status='PASS_ACTUAL_HEALTH_CHECKS_NEVER_SKIPPED_AND_REJECTIONS_DURABLE',
         checks=checks,actual_observations=observations,BOARD='NOT_TESTED'))
    print('PASS_PC_HEALTH_JOURNAL_SAFETY')
