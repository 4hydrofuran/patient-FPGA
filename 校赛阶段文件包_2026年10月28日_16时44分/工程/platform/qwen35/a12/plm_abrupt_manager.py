"""Deliberate PC manager os._exit after a cached grant claim; no forced worker signal."""
import argparse
import array
import json
import os
from pathlib import Path
import socket
import threading
import time
from plm_manager import Manager
from plm_evidence import OUT,read,save
from plm_page import COUNT,UNKNOWN
from request_journal_verified import canonical
def main():
    p=argparse.ArgumentParser();p.add_argument('--revision',type=int,required=True);p.add_argument('--tag',required=True);p.add_argument('--notify-fd',type=int,required=True);a=p.parse_args()
    os.umask(0o077);build=OUT/f'BUILD-v{a.revision}.json';work=Path(read(build)['workspace'])
    m=Manager(build,work/('run-'+a.tag),cap=72);m.ready();notify=socket.socket(fileno=a.notify_fd)
    q=dict(domain='PC_XRT_CONTROL_ONLY',manager_pid=os.getpid(),native_pid=m.p.pid,native_start_ticks=m.worker_ticks,
        page_epoch=m.page.epoch,context_sha256=m.context_sha,directory=str(m.directory))
    fds=array.array('i',[m.page.fd,m.p.stdout.fileno()]);notify.sendmsg([canonical(q)],[(socket.SOL_SOCKET,socket.SCM_RIGHTS,fds)])
    if notify.recv(16)!=b'OBSERVED_LIVE':os._exit(4)
    def disappear():
        until=time.monotonic()+10
        while time.monotonic()<until:
            s=m.page.state()
            if (s&COUNT)>=5 and s&UNKNOWN:os._exit(0)
            time.sleep(.001)
        os._exit(5)
    threading.Thread(target=disappear,daemon=True).start();m.run_request(0,native_fault='pause_claim');os._exit(6)
if __name__=='__main__':main()
