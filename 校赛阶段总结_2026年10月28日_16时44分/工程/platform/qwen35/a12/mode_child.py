"""Pinned PC manager child with parent telemetry; never a Board entry point."""
import argparse
import array
import json
import os
from pathlib import Path
import signal
import socket
import threading
import types

from mode_evidence import ROOT,OUT,read,sha,save
from mode_journal import need
from request_journal_verified import canonical

def start_ticks(pid):
    text=(Path('/proc')/str(pid)/'stat').read_text();return int(text[text.rfind(')')+2:].split()[19])

def run(tag,cap,build,notify_fd,session_epoch,window_id,expected_source,fault=None):
    path=ROOT/'platform/qwen35/a12/microbatch_run.py';need(sha(path)==expected_source,'pinned PC runner changed')
    module=types.ModuleType('mode_pinned_batch_runner');module.__file__=str(path)
    exec(compile(path.read_bytes(),str(path),'exec'),module.__dict__);module.OUT=OUT
    original=module.BatchWorker;original_page=module.BatchPage;owned=[];cancelled=False
    notify=socket.socket(fileno=notify_fd)
    stop=threading.Event();control_lock=threading.RLock();notify.settimeout(.05)
    def cancel(signum,frame):
        nonlocal cancelled
        cancelled=True
        with control_lock:
            for worker in owned:worker._isolate('PC mode coordinator cancellation; no replay')
    def control():
        while not stop.is_set():
            try:raw=notify.recv(4096)
            except socket.timeout:continue
            except OSError:return
            if not raw:
                if not stop.is_set():cancel(None,None)
                return
            try:
                q=json.loads(raw);need(q==dict(event='MODE_CANCEL',session_epoch=session_epoch,window_id=window_id),'invalid PC cancel packet')
            except BaseException:cancel(None,None);return
            cancel(None,None)
    thread=threading.Thread(target=control,name='mode-control-receiver',daemon=True);thread.start()
    class Page(original_page):
        def close(self):
            stop.set()
            if threading.current_thread() is not thread:thread.join(1)
            need(not thread.is_alive(),'PC control receiver still live; page retained')
            with control_lock:return super().close()
    module.BatchPage=Page
    signal.signal(signal.SIGUSR1,cancel)
    class Tracked(original):
        def __init__(self,*args,**kw):
            need(not cancelled,'PC window cancelled before spawn')
            super().__init__(*args,**kw)
            with control_lock:owned.append(self)
            record=dict(event='MODE_NATIVE_OWNED',session_epoch=session_epoch,window_id=window_id,
                manager_pid=os.getpid(),manager_start_ticks=start_ticks(os.getpid()),
                native_pid=self.process.pid,native_start_ticks=start_ticks(self.process.pid),
                page_epoch=self.page.epoch,grant_size=cap,domain='PC_NATIVE_MATH_NOT_FPGA')
            notify.sendmsg([canonical(record)],[(socket.SOL_SOCKET,socket.SCM_RIGHTS,array.array('i',[self.page.fd]))])
            if cancelled:self._isolate('PC mode cancellation arrived during constructor')
    module.BatchWorker=Tracked
    try:module.run(tag,cap,build,fault=fault)
    finally:
        stop.set();thread.join(1);notify.close()
        if (OUT/('run-'+tag)).exists():
            save(OUT/('run-'+tag)/'MODE_CHILD.json',dict(session_epoch=session_epoch,window_id=window_id,
                control_thread_stopped=not thread.is_alive(),cancelled=cancelled,BOARD='NOT_TESTED',
                mode_child_sha256=sha(Path(__file__)),old_runner_sha256=expected_source))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--tag',required=True);p.add_argument('--cap',type=int,choices=(1,72),required=True)
    p.add_argument('--build',type=Path,required=True);p.add_argument('--notify-fd',type=int,required=True)
    p.add_argument('--session-epoch',required=True);p.add_argument('--window-id',required=True)
    p.add_argument('--runner-sha',required=True);p.add_argument('--fault',choices=('cached_revoke','end_log'))
    a=p.parse_args();run(a.tag,a.cap,a.build,a.notify_fd,a.session_epoch,a.window_id,a.runner_sha,a.fault)
