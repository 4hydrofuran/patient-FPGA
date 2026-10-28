"""Read-only page reference and pidfds acquired from a live owned process."""
import ctypes as c
import fcntl
import json
import os
from pathlib import Path
import select
from mode_journal import need
from mode_evidence import read,sha

class PageObservation:
    def __init__(self,received_fd,build):
        self.fd=None;self.closed=False
        try:
            # SCM_RIGHTS duplicates the RW description. Replace it immediately
            # with a separate RO description, then discard the RW duplicate.
            self.fd=os.open('/proc/self/fd/'+str(received_fd),os.O_RDONLY|os.O_CLOEXEC)
        finally:os.close(received_fd)
        try:
            need((fcntl.fcntl(self.fd,fcntl.F_GETFL)&os.O_ACCMODE)==os.O_RDONLY,'observer FD is writable')
            need(sha(build['library'])==build['library_sha256'],'observer library changed')
            self.lib=c.CDLL(build['library']);self.call=self.lib.a12_pc_mode_read_page_v1
            self.call.argtypes=[c.c_int,c.c_void_p,c.c_uint64];self.call.restype=c.c_int
            self.snapshot()
        except BaseException:self.close();raise
    def snapshot(self):
        need(not self.closed,'observer page closed');out=c.create_string_buffer(1024)
        need(self.call(self.fd,out,len(out))==0,'read-only page snapshot rejected')
        return json.loads(out.value)
    def close(self):
        if not self.closed:self.closed=True;os.close(self.fd)

class ProcessObservation:
    def __init__(self,pid,ticks):
        self.pid=pid;self.ticks=ticks;self.fd=None
        # A PID number/file alone is not retained liveness authority.
        self.fd=os.pidfd_open(pid,0)
        try:
            text=(Path('/proc')/str(pid)/'stat').read_text();actual=int(text[text.rfind(')')+2:].split()[19])
            need(actual==ticks,'owned process start differs')
        except BaseException:self.close();raise
    def terminal(self):
        poll=select.poll();poll.register(self.fd,select.POLLIN);return bool(poll.poll(0))
    def close(self):
        if self.fd is not None:os.close(self.fd);self.fd=None
