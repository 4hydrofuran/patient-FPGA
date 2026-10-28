"""Actual held-pidfd concurrency regression; no model/FPGA/library operations."""
import os
import select
import subprocess
import sys
import threading
import time
from types import SimpleNamespace
from modelpl_evidence import OUT,save
from modelpl_manager import ModelManager,base
def main():
    worker=subprocess.Popen([sys.executable,'-c','import sys;sys.stdin.read()'],stdin=subprocess.PIPE)
    fd=os.pidfd_open(worker.pid);m=ModelManager.__new__(ModelManager);m.p=worker;m.pidfd=fd;m.page=SimpleNamespace(deadline=time.monotonic_ns()+30_000_000_000)
    m.poller=select.poll();m.poller.register(fd,select.POLLIN)
    def stress(function):
        gate=threading.Barrier(8);errors=[]
        def task():
            gate.wait()
            for _ in range(200):
                try:function(m)
                except BaseException as exc:errors.append(str(exc))
        threads=[threading.Thread(target=task) for _ in range(8)]
        for t in threads:t.start()
        for t in threads:t.join(5)
        assert all(not t.is_alive() for t in threads);return errors
    previous=stress(base.Manager._owned);current=stress(ModelManager._owned)
    assert previous and all('concurrent poll() invocation' in x for x in previous)
    assert not current and worker.poll() is None
    worker.stdin.close();worker.wait(timeout=5);assert worker.returncode==0
    try:m._owned()
    except RuntimeError:terminal_refused=True
    else:terminal_refused=False
    assert terminal_refused
    save(OUT/'OWNER_CONCURRENCY_RESULT.json',dict(status='PASS_HELD_PIDFD_CONCURRENCY_AND_TERMINAL_REFUSAL',threads=8,calls_per_thread=200,
        previous_shared_poll_errors=len(previous),new_poll_errors=len(current),same_held_pidfd=True,PID_reopened=False,
        worker_pid=worker.pid,worker_exit_code=0,terminal_refused=terminal_refused,BOARD='NOT_TESTED',actual_model=False))
    os.close(fd);print('PASS_HELD_PIDFD_CONCURRENCY_AND_TERMINAL_REFUSAL')
if __name__=='__main__':main()
