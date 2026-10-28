"""Actual frozen PC model through local microbatch guard; no board entry."""
import argparse
import threading
import time
import types
from unittest import mock

from microbatch_evidence import ROOT,OUT,read,save,sha,pin
from microbatch_page import BatchPage,COUNT
from microbatch_worker import BatchWorker,BatchController
from request_journal_verified import require


def run(tag,grant_size,build_path,*,fault=None):
    build=read(build_path);path=ROOT/'platform/qwen35/a12/native_request_run.py'
    require(sha(path)=='329f6476be73f155ae5e1159751512442bf81346815e626b046575f99259e5d0','frozen native runner differs')
    module=types.ModuleType('microbatch_frozen_runner');module.__file__=str(path)
    exec(compile(path.read_bytes(),str(path),'exec'),module.__dict__);module.OUT=OUT
    module.NativeRequestController=BatchController;workers=[];pending=[];owners=[];watchers=[];stop=threading.Event();injections=[]
    OriginalOwner=module.PCOwner

    class Owner(OriginalOwner):
        def __init__(self,*args,**kw):super().__init__(*args,**kw);self.closed_after_observer_stop=False;owners.append(self)
        def close(self):
            if self.closed_after_observer_stop:return
            # The frozen runner closes owner FDs in its finally block. This
            # candidate's background callback also checks those FDs, so join
            # it HERE before delegating that close, including on request error.
            stopped=[w.monitor.stop() for w in pending if hasattr(w,'monitor')]
            terminal=all(not hasattr(w,'process') or w.process.poll() is not None for w in pending)
            if all(stopped) and terminal:super().close();self.closed_after_observer_stop=True

    module.PCOwner=Owner

    class Worker(BatchWorker):
        def __init__(self,*args,**kw):
            self._fault_injected=False
            config=read(read(kw['env']['SP_A12_CONFIG'])['backend_config'])
            self.local_page=BatchPage(build['library'],expires_ns=int(kw['expires']*1e9))
            pending.append(self)
            kw['env']=dict(kw['env'],SP_A12_BATCH_PAGE_FD=str(self.local_page.fd))
            kw['inherited_fds']=tuple(kw['inherited_fds'])+(self.local_page.fd,)
            super().__init__(*args,page=self.local_page,context_sha256=config['context_sha256'],
                grant_size=grant_size,**kw);workers.append(self)
            if fault=='cached_revoke':
                def revoke():
                    while not stop.wait(.0005):
                        if self.page.gate()&COUNT>=5:
                            observed=self.page.revoke();injections.append(dict(kind=fault,
                                revoke_prior_gate=observed,revoke_prior_claims=observed&COUNT,
                                monotonic_ns=time.monotonic_ns()))
                            self._fault_injected=True;self._isolate('PC injected revoke while cached grant remains');return
                thread=threading.Thread(target=revoke,daemon=True);thread.start();watchers.append(thread)
        def _durable(self,**row):
            if fault=='end_log' and row.get('event')=='REQUEST_END_PC_CANDIDATE' and not self._fault_injected:
                self._fault_injected=True;original=self._journal.append
                def blocked(raw):
                    observed=self.page.revoke();self._isolate('PC injected revoke during END append')
                    injections.append(dict(kind=fault,revoke_prior_gate=observed,revoke_prior_claims=observed&COUNT,
                        monotonic_ns=time.monotonic_ns(),actual_original_append_completed=True))
                    return original(raw)
                with mock.patch.object(self._journal,'append',side_effect=blocked):return super()._durable(**row)
            return super()._durable(**row)

    module.NativeJournalWorker=Worker
    source=[pin(ROOT/'platform/qwen35/a12'/n) for n in
        ('microbatch_guard.hpp','microbatch_page.py','microbatch_worker.py','microbatch_run.py')]
    try:module.run('strict' if grant_size==1 else 'request',tag,build_path)
    finally:
        stop.set()
        for thread in watchers:thread.join(2)
        reports=[]
        for w in workers:
            stopped=w.monitor.stop();g=w.page.gate()
            threads_stopped=all(not t.is_alive() for t in watchers) and not w.permission_thread.is_alive() and not w.reader_thread.is_alive()
            reports.append(dict(manager_reserved_jobs=w.runs,grants=w.batch_serial,
                shared_claims=g&COUNT,gate_before_close=g,monitor=w.monitor.status(),monitor_stopped=stopped,
                worker_epoch=w.worker_epoch,result_boundaries=w.result_boundaries,
                worker_exit_code=w.process.poll(),watchers_stopped=all(not t.is_alive() for t in watchers),
                all_protocol_and_observer_threads_stopped=threads_stopped and stopped))
            if stopped and threads_stopped and w.process.poll() is not None:w.page.close()
        partial=[]
        for w in pending:
            if w in workers:continue
            monitor=getattr(w,'monitor',None);process=getattr(w,'process',None)
            stopped=monitor is None or monitor.stop();terminal=process is None or process.poll() is not None
            if stopped and terminal:w.local_page.close()
            partial.append(dict(observer_stopped=stopped,CPU_process_terminal=terminal,
                owner_retained=not (stopped and terminal)))
        if (OUT/('run-'+tag)).exists():
            save(OUT/('run-'+tag)/'MICROBATCH.json',dict(schema='PC_MICROBATCH_INTEGRATION_V1',source_at_launch=source,
                adapter_sha256=build['library_sha256'],build_receipt=str(build_path),grant_size=grant_size,
                workers=reports,partial_initialization=partial,owner_FDs_closed_after_observer_stop=[o.closed_after_observer_stop for o in owners],
                injections=injections,fault=fault,BOARD='NOT_TESTED',PL_calls=0,
                shared_page_bytes=4096,trusted_controlled_worker_required=True,
                manager_independent_per_projection_decision=False,board_binding=False,production_default=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--tag',required=True);p.add_argument('--grant-size',type=int,choices=[1,72],required=True)
    p.add_argument('--build',type=__import__('pathlib').Path,default=OUT/'BUILD-v5-reviewed.json')
    p.add_argument('--fault',choices=['cached_revoke','end_log']);a=p.parse_args();run(a.tag,a.grant_size,a.build,fault=a.fault)
