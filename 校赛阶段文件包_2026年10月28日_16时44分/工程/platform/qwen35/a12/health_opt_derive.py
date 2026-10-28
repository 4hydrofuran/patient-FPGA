"""Derive isolated controllers from the sealed task10 candidate; no ARM rebuild."""
import ast
import json
from pathlib import Path
from common import ROOT,sha,save

OUT=ROOT/'evidence/model_pl_A/20261024-health-opt-v1'
def replace(s,a,b):
    assert s.count(a)==1,(a,s.count(a));return s.replace(a,b)

if __name__=='__main__':
    parent=ROOT/'evidence/model_pl_A/20261024-step10-v1/optimized/bundle-v1'
    src=OUT/'controllers';src.mkdir(exist_ok=True)
    s=(parent/'control/step10_manager.py').read_text(encoding='utf-8')
    s=s.replace('from step10_window import Window','from health_opt_window import Window')
    s=replace(s,'from step08_health import live_snapshot,compact_kernel_record',
              'from step08_health import compact_kernel_record\nfrom health_opt import PersistentKmsg, StableTemperatures, HealthSchedule, HealthBlocked')
    s=replace(s,'self.owner=None;self.gate_lock=threading.RLock()',
              "self.owner=None;self.gate_lock=threading.RLock()\n        self.health_schedule=HealthSchedule(self.gate_lock)\n        self.kmsg_reader=None;self.stable_temperatures=None;self.topology_checked_ns=0\n        self.health_parts=dict(kernel_ms=0.0,temperature_memory_ms=0.0,kernel_calls=0)")
    anchor='    def guard(self,identity=None):'
    additions='''    def kernel_checkpoint(self,phase,mutation=None):
        if phase!='a12_serialized_health':
            super().kernel_checkpoint(phase,mutation)
            if self.kmsg_reader is not None:
                self.kmsg_reader.assert_full_snapshot(self.kernel_gate.previous)
            return
        start=time.monotonic_ns()
        try:
            if self.kmsg_reader is None:
                self.kmsg_reader=PersistentKmsg()
                # Exact baseline equivalence before using the new source.
                super().kernel_checkpoint(phase,mutation)
                self.kmsg_reader.assert_full_snapshot(self.kernel_gate.previous)
            else:
                raw=self.kmsg_reader.drain()
                boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
                result=self.kernel_gate.observe_action(boot,raw,None,'none',False)
                self.emit('KERNEL_LOG_GATE',phase=phase,raw_log=raw,**dict(result,action='none'))
                if not result['allowed']:raise HealthBlocked('incremental kernel gate rejected')
        except BaseException:
            self.kernel_gate.blocked=True
            raise
        finally:
            self.health_parts['kernel_ms']+=(time.monotonic_ns()-start)/1e6
            self.health_parts['kernel_calls']+=1

    def live_health(self,boot,full_resident):
        start=time.monotonic_ns()
        assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==boot
        if self.stable_temperatures is None:self.stable_temperatures=StableTemperatures()
        now=time.monotonic_ns()
        if now-self.topology_checked_ns>=1_000_000_000:
            self.stable_temperatures.verify_topology();self.topology_checked_ns=now
        temps=self.stable_temperatures.read()
        mem={l.split(':')[0]:int(l.split()[1]) for l in Path('/proc/meminfo').read_text().splitlines()}
        if mem['MemAvailable']<1114112 or mem['CmaFree']<98304:raise HealthBlocked('full-model live extra reserve gate')
        result=dict(temperatures_mC=temps,memory_kib={k:mem[k] for k in ('MemAvailable','CmaFree','CmaTotal')},
            full_resident=full_resident,actual_reserve=admission(mem,140591104,already_charged_bo_bytes=140591104) if full_resident else None)
        self.health_parts['temperature_memory_ms']+=(time.monotonic_ns()-start)/1e6
        return result

'''
    s=replace(s,anchor,additions+anchor)
    s=replace(s,"    def health(self,*,closing=False):\n        with self.platform.gate_lock:",
                "    def health(self,*,closing=False):\n        return self.platform.health_schedule.fresh(lambda:self._health_observation(closing=closing))\n\n    def _health_observation(self,*,closing=False):\n        with self.platform.gate_lock:")
    s=replace(s,"live_snapshot(self.boot,full_resident=getattr(self,'full_resident',False))",
                "self.platform.live_health(self.boot,getattr(self,'full_resident',False))")
    s=replace(s,'        owner.owner_check();owner.health()\n        try:r=worker.messages.get(timeout=.25)',
                "        owner.platform.health_schedule.idle(owner._health_observation,owner.owner_check)\n        try:r=worker.messages.get(timeout=.25)")
    s=replace(s,"        after=dict(getattr(worker,'permission_metrics',{}))",
                "        after=dict(getattr(worker,'permission_metrics',{}))\n        save(case/'health-metrics.json',dict(schedule=owner.platform.health_schedule.metrics,parts=owner.platform.health_parts,reader_records=owner.platform.kmsg_reader.records,reader_drains=owner.platform.kmsg_reader.drains))")
    s=replace(s,"p.snapshot('gdm_restored');owner.finish(pl)\n", "p.snapshot('gdm_restored');owner.finish(pl)\n        p.stable_temperatures.verify_topology()\n        p.kmsg_reader.close()\n")
    (src/'health_opt_manager.py').write_text(s,encoding='utf-8',newline='\n')
    s=(parent/'platform/qwen35/a12/step10_window.py').read_text(encoding='utf-8')
    # Import unchanged supervisor: every fresh observation and fsync permit retained.
    (src/'health_opt_window.py').write_text(s,encoding='utf-8',newline='\n')
    for p in src.glob('*.py'):ast.parse(p.read_text(encoding='utf-8'))
    save(OUT/'DERIVATION.json',dict(parent_manifest_sha256=sha(parent/'manifest.json'),
        changes={p.name:sha(p) for p in src.glob('*.py')},module_sha256=sha(ROOT/'platform/qwen35/a12/health_opt.py'),
        unchanged=['ARM binary','xclbin','public ABI','mathematics','thresholds','per-permit fresh observation','fsync permission record','normal release/restore'],
        baseline_source='DMESG_AT_INITIAL_AND_ALL_LIFECYCLE_ACTION_BOUNDARIES',
        incremental_source='READONLY_PERSISTENT_KMSG_EXACT_ANCHOR_AND_SEQUENCE_LOSS_LATCH'))
    print('HEALTH_CONTROLLERS_DERIVED')
