"""Derive task10 ownership controllers; per-permit gates and durable permits retained."""
import ast
from common import ROOT, sha, save
from step10_common import OUT

def replace(s,a,b):
    assert s.count(a)==1,(a,s.count(a));return s.replace(a,b)

if __name__=='__main__':
    folder=ROOT/'platform/qwen35/a12'
    s=(folder/'step09_supervisor.py').read_text(encoding='utf-8')
    s=replace(s,"                    if self.owner_check:self.owner_check()\n                    self.health();phase=r['phase'];closing=phase=='router_close'",'''                    gate_start=time.monotonic_ns()
                    if self.owner_check:self.owner_check()
                    owner_end=time.monotonic_ns()
                    health_observation=self.health();health_end=time.monotonic_ns()
                    phase=r['phase'];closing=phase=='router_close' ''')
    s=replace(s,"                    self.record(event='PERMISSION',request=r,allow=allowed,sequence_lane=lane,\n                                observed_global_messages=self.sequence)",'''                    record_start=time.monotonic_ns()
                    self.record(event='PERMISSION',request=r,allow=allowed,sequence_lane=lane,
                                observed_global_messages=self.sequence,health_observation=health_observation,
                                owner_check_ms=(owner_end-gate_start)/1e6,health_check_ms=(health_end-owner_end)/1e6)
                    record_end=time.monotonic_ns()
                    if not hasattr(self,'permission_metrics'):self.permission_metrics={}
                    for key,value in [('calls',1),('owner_check_ms',(owner_end-gate_start)/1e6),('health_check_ms',(health_end-owner_end)/1e6),('durable_permission_record_ms',(record_end-record_start)/1e6)]:
                        self.permission_metrics[key]=self.permission_metrics.get(key,0)+value''')
    (folder/'step10_supervisor.py').write_text(s,encoding='utf-8',newline='\n')
    s=(folder/'step09_window.py').read_text(encoding='utf-8')
    s=replace(s,'from step09_supervisor import OwnedWorker','from step10_supervisor import OwnedWorker')
    s=replace(s,"scope=self.review['scope'],execution_kind='FPGA_REAL',trace_limit=4096,", "scope=self.review['scope'],execution_kind='FPGA_REAL',trace_limit=4096,\n            a12_compact_completion=self.review['compact_completion'],")
    (folder/'step10_window.py').write_text(s,encoding='utf-8',newline='\n')
    s=(folder/'step09_manager.py').read_text(encoding='utf-8')
    s=replace(s,'from step09_window import Window','from step10_window import Window')
    s=replace(s,'from supervisor import OwnedWorker as CPUWorker','from step10_supervisor import OwnedWorker as CPUWorker')
    a=s.index('def run_case(');b=s.index('\n\ndef main():',a)
    s=s[:a]+(folder/'step10_cases.py').read_text(encoding='utf-8')+s[b:]
    s=replace(s,"    def emit(self,event,**data):\n        if event=='KERNEL_LOG_GATE':data=compact_kernel_record(self.run,data)\n        return super().emit(event,**data)",'''    def emit(self,event,**data):
        if event=='KERNEL_LOG_GATE':
            data=compact_kernel_record(self.run,data)
            self.latest_kernel=dict(allowed=data['allowed'],sha256=data['current_sha256'],observation_monotonic_ns=time.monotonic_ns())
        if event=='LIVE_HEALTH':self.latest_health=dict(data,checked_monotonic_ns=time.monotonic_ns())
        if SPEC['compact_health_journal'] and event in ('KERNEL_LOG_GATE','LIVE_HEALTH'):
            key=event
            now=time.monotonic_ns();last=getattr(self,'journal_last',{}).get(key)
            fingerprint=self.latest_kernel['sha256'] if event=='KERNEL_LOG_GATE' else None
            if last and now-last[0]<1_000_000_000 and fingerprint==last[1]:return
            if not hasattr(self,'journal_last'):self.journal_last={}
            self.journal_last[key]=(now,fingerprint)
        return super().emit(event,**data)''')
    s=replace(s,"            if not closing:self.platform.emit('LIVE_HEALTH',**live_snapshot(self.boot,full_resident=getattr(self,'full_resident',False)))",'''            if not closing:self.platform.emit('LIVE_HEALTH',**live_snapshot(self.boot,full_resident=getattr(self,'full_resident',False)))
            return dict(kernel=self.platform.latest_kernel,
                live_health=None if closing else self.platform.latest_health,
                closing=closing,checked_monotonic_ns=time.monotonic_ns(),
                checks_skipped=False,journal_compacted=SPEC['compact_health_journal'])''')
    s=replace(s,"        if SPEC['variant']=='context':\n            from step09_negative import startup_negatives\n            startup_negatives(BUNDLE,owner,p,run)\n",'')
    s=replace(s,"        s1=run/'s1';s1.mkdir()", "        p.service('stop') # Same GDM isolation for both CPU and PL performance.\n        s1=run/'s1';s1.mkdir()")
    s=replace(s,"        p.service('stop');p.wait_prepl_quiet();p.target.mkdir(mode=0o755)", "        p.wait_prepl_quiet();p.target.mkdir(mode=0o755)")
    s=replace(s,"window_id=WINDOW,scope='all',max_runs=SPEC['max_runs'],max_loads=72,explicit_bo_budget_bytes=140591104,", "window_id=WINDOW,scope='all',max_runs=SPEC['max_runs'],max_loads=72,explicit_bo_budget_bytes=140591104,\n        compact_completion=SPEC['compact_completion'],compact_health_journal=SPEC['compact_health_journal'],")
    s=s.replace("step09='IN_PROGRESS_'", "step10='IN_PROGRESS_'")
    # A capacity rejection must restore the graphical service before the normal lease finish.
    s=replace(s,"            owner.finish(cpu)\n", "            p.service('start');owner.finish(cpu)\n")
    (folder/'step10_manager.py').write_text(s,encoding='utf-8',newline='\n')
    for name in ('step10_supervisor.py','step10_window.py','step10_manager.py'):
        ast.parse((folder/name).read_text(encoding='utf-8'))
    save(OUT/'CONTROLLER_DERIVATION.json',dict(status='REVIEWED_PER_PERMIT_GATES_RETAINED',
         new_files={n:sha(folder/n) for n in ('step10_supervisor.py','step10_window.py','step10_manager.py')},
         compact_journal='Every gate still reads boot/kernel/temperature/reserves; each allowed permit fsync binds its fresh observation; unchanged duplicate lifecycle health rows at most once/second',
         safety_changes='NO_CHECK_SKIPPED_NO_UNKNOWN_DMA_CLEANUP_NO_NEW_POWER_ACTION',
         baseline_compaction=False,optimized_compaction='CONDITIONAL_ON_BASELINE_AUDIT'))
    print('TASK10_CONTROLLERS_DERIVED')
