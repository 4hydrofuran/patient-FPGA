"""Generate a separate future Window v2, preserving original source and frozen bundles."""
import json
from common import ROOT,sha,save

OUT=ROOT/'evidence/model_pl_A/20261024-step07-finalize-v1'

EXTENSION=r'''

from step07_finalize_policy import complete_scan


class Window(WindowBase):
    """Future controller component; no PL load/unload/reset or automatic work."""
    def start_worker(self,*args,**kwargs):
        self._owned_worker=super().start_worker(*args,**kwargs)
        return self._owned_worker

    def _finalize_record(self,event,**data):
        path=self.evidence/'finalization-events.jsonl'
        fd=os.open(path,os.O_WRONLY|os.O_APPEND|os.O_CREAT|os.O_NOFOLLOW,0o600)
        try:
            with os.fdopen(fd,'a',encoding='utf-8',closefd=False) as f:
                f.write(json.dumps(dict(event=event,monotonic_ns=time.monotonic_ns(),**data))+'\n')
                f.flush();os.fsync(fd)
        finally:os.close(fd)

    def _kernel_ok(self):
        self.health(closing=True)
        return True

    def _verify_default(self):
        ref=Path('/sys/module/zocl/refcnt')
        overlays=Path('/sys/kernel/config/device-tree/overlays')
        applied=[p for p in overlays.glob('k26-starter-kits*/status') if p.read_text().strip()=='applied']
        if ref.exists() or not applied or Path('/sys/class/fpga_manager/fpga0/state').read_text().strip()!='operating':
            raise RuntimeError('default PL restore not proven')
        r=subprocess.run(['systemctl','is-active','gdm'],capture_output=True,text=True,timeout=3)
        if r.returncode or r.stdout.strip()!='active':raise RuntimeError('GDM restore not proven')

    def finish(self,worker):
        self._owned_worker=worker
        if not worker.closed or worker.process.returncode!=0:raise RuntimeError('normal worker exit not proven')
        self.owner_check();self.health(closing=True)
        snapshot=complete_scan(collect,require_no_users,self.boot,self._kernel_ok,self._finalize_record)
        self._verify_default()
        self.owner_check()
        target=CENTRAL/'history'/self.review['window_id'];target.parent.mkdir(exist_ok=True)
        if target.exists():raise FileExistsError('consumed window')
        index=len(list(self.evidence.glob('final-resource-scan-*.json')))+1
        save(self.evidence/f'final-resource-scan-{index:04}.json',snapshot)
        self._finalize_record('FINALIZATION_PREPARED_FOR_ATOMIC_ARCHIVE',normal_worker_exit=True,hardware_operations=0)
        (CENTRAL/'active').rename(target)
        for fd in reversed(self.locks):os.close(fd)
        self.locks=[];self.finished=True

    def _apply_finalize_ticket(self,path):
        trusted_file(path)
        r=json.loads(path.read_text(encoding='utf-8'))
        expected=dict(schema='A12_FINALIZE_ONLY_V2',op='finish_only',boot_id=self.boot,
            window_id=self.review['window_id'],manager_pid=os.getpid(),
            manager_start_ticks=start_ticks(Path('/proc/self')),lease_sha256=self.lease_hash)
        if set(r)!=set(expected)|{'expires_monotonic_ns'} or any(r[k]!=v for k,v in expected.items()):
            raise RuntimeError('foreign or widened finalize ticket')
        if type(r['expires_monotonic_ns']) is not int or not 0<r['expires_monotonic_ns']-time.monotonic_ns()<=30_000_000_000:
            raise RuntimeError('stale/unbounded finalize ticket')
        worker=getattr(self,'_owned_worker',None)
        if worker is None or not worker.closed or worker.process.returncode!=0:
            raise RuntimeError('finalize ticket cannot terminate pending/bad worker')
        self.owner_check()
        target=path.with_name('consumed-'+path.name)
        if target.exists():raise RuntimeError('replayed finalize ticket')
        path.rename(target)
        self._finalize_record('EXPLICIT_FINALIZE_ONLY_TICKET_ACCEPTED',request=r,file=str(target))
        self.finish(worker)
        return True

    def retain_until_finished(self,reason):
        latch=self.evidence/'ISOLATED.json'
        if not latch.exists():save(latch,dict(reason=reason,lease_retained=True,no_kill=True,recovery='EXPLICIT_ROOT_FINALIZE_ONLY_V2'))
        seen=set()
        while not self.finished:
            for p in sorted(self.evidence.glob('finalize-request-*.json')):
                if p.name in seen:continue
                seen.add(p.name)
                try:
                    if self._apply_finalize_ticket(p):
                        # Caller may still be inside the original exception handler.
                        # This is our own controlled exit after actual lock/lease cleanup.
                        raise SystemExit(0)
                except Exception as exc:
                    self._finalize_record('FINALIZE_TICKET_REFUSED_RESOURCES_RETAINED',file=str(p),reason=type(exc).__name__+': '+str(exc))
            time.sleep(1)
'''


def generated_source():
    source=ROOT/'platform/qwen35/a12/window.py';s=source.read_text(encoding='utf-8');before=sha(source)
    assert s.count('class Window:')==1;s=s.replace('class Window:','class WindowBase:')
    assert s.count('from supervisor import OwnedWorker')==1
    s=s.replace('from supervisor import OwnedWorker','from step07_supervisor import OwnedWorker')
    assert s.count('baseline.read_text()')==1;s=s.replace('baseline.read_text()',"baseline.read_bytes().decode('utf-8')")
    old="r=subprocess.run(['dmesg','--raw'],capture_output=True,text=True,timeout=3)"
    assert s.count(old)==1;s=s.replace(old,"r=subprocess.run(['dmesg','--raw'],capture_output=True,timeout=3)")
    assert s.count('self.gate.observe(self.boot,r.stdout)')==1
    s=s.replace('self.gate.observe(self.boot,r.stdout)',"self.gate.observe(self.boot,r.stdout.decode('utf-8'))")
    return s+EXTENSION,before


if __name__=='__main__':
    text,before=generated_source()
    target=ROOT/'platform/qwen35/a12/window_closeout_v2.py'
    with target.open('x',encoding='utf-8',newline='\n') as f:f.write(text)
    save(OUT/'WINDOW_V2_DERIVATION.json',dict(original_sha256=before,new_sha256=sha(target),
        original_unchanged=sha(ROOT/'platform/qwen35/a12/window.py')==before,BOARD_runtime='NOT_TESTED',
        changes=['raw kernel bytes preserved','save every failed full scan','strict bounded observation retries',
                 'explicit root identity/lease/expiry-bound finalize-only tickets','normal self-exit after actual cleanup'],
        integration='Future manager must explicitly import window_closeout_v2.Window in a new reviewed bundle; old board process/bundle not patched'))
    print('Separate future Window v2 generated; original source and board bundle preserved')
