"""Observe owned live pidfds and RO page across actual PC manager death."""
import argparse
import array
import ctypes as c
import fcntl
import json
import os
from pathlib import Path
import select
import shutil
import socket
import subprocess
import sys
import time
from plm_evidence import ROOT,OUT,read,save,sha,pin
from plm_manager import ticks
from request_journal_verified import canonical
def main():
    p=argparse.ArgumentParser();p.add_argument('--revision',type=int,required=True);p.add_argument('--tag',required=True);a=p.parse_args()
    assert a.tag.replace('-','').isalnum();os.umask(0o077);mirror=OUT/a.tag;mirror.mkdir();build=read(OUT/f'BUILD-v{a.revision}.json')
    libc=c.CDLL(None,use_errno=True);assert libc.prctl(36,1,0,0,0)==0
    parent,child=socket.socketpair(socket.AF_UNIX,socket.SOCK_SEQPACKET)
    log=(mirror/'manager.txt').open('xb');argv=[sys.executable,'-B',str(ROOT/'platform/qwen35/a12/plm_abrupt_manager.py'),'--revision',str(a.revision),'--tag',a.tag,'--notify-fd',str(child.fileno())]
    manager=subprocess.Popen(argv,pass_fds=(child.fileno(),),stdout=log,stderr=subprocess.STDOUT);child.close();mpidfd=os.pidfd_open(manager.pid);mticks=ticks(manager.pid)
    parent.settimeout(30);raw,anc,flags,_=parent.recvmsg(4096,socket.CMSG_SPACE(16),socket.MSG_CMSG_CLOEXEC);assert not flags&(socket.MSG_TRUNC|socket.MSG_CTRUNC);q=json.loads(raw)
    values=array.array('i')
    for level,kind,data in anc:
        assert level==socket.SOL_SOCKET and kind==socket.SCM_RIGHTS;values.frombytes(data[:len(data)//values.itemsize*values.itemsize])
    assert len(values)==2 and q['manager_pid']==manager.pid and q['native_start_ticks']==ticks(q['native_pid'])
    npidfd=os.pidfd_open(q['native_pid']);np=select.poll();np.register(npidfd,select.POLLIN);assert not np.poll(0)
    ro=os.open('/proc/self/fd/'+str(values[0]),os.O_RDONLY|os.O_CLOEXEC);os.close(values[0]);pipe=values[1]
    observer=read(OUT/'OBSERVER_REVIEWED-v2.json') if (OUT/'OBSERVER_REVIEWED-v2.json').exists() else dict(library=build['observer_library'],sha256=sha(build['observer_library']))
    assert sha(observer['library'])==observer['sha256']
    lib=c.CDLL(observer['library']);fn=lib.a12_plm_observe_fd_v1;fn.argtypes=[c.c_int,c.c_char_p,c.c_uint64];fn.restype=c.c_int
    def snapshot():
        b=c.create_string_buffer(4096);assert fn(ro,b,4096)==0;return json.loads(b.value)
    initial=snapshot();assert initial['claims']==0 and not initial['unknown_io'] and initial['worker_pid']==q['native_pid']
    try:os.write(ro,b'!')
    except OSError:pass
    else:raise AssertionError('RO page permits mutation')
    parent.sendall(b'OBSERVED_LIVE');mp=select.poll();mp.register(mpidfd,select.POLLIN);assert mp.poll(10000)
    manager.wait(timeout=2);assert manager.returncode==0
    at_death=snapshot();assert at_death['claims']==5 and at_death['unknown_io']
    directory=Path(q['directory']);lock=os.open(directory/'state/control.lock',os.O_RDWR|os.O_CLOEXEC)
    try:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:lock_blocked=True
    else:lock_blocked=False
    assert lock_blocked,'live native did not retain inherited coordinator lock'
    assert np.poll(10000);status=os.waitpid(q['native_pid'],0)[1];assert os.WIFEXITED(status) and os.WEXITSTATUS(status)==2
    data=b'';rp=select.poll();rp.register(pipe,select.POLLIN|select.POLLHUP)
    while rp.poll(100):
        chunk=os.read(pipe,32769-len(data))
        if not chunk:break
        data+=chunk;assert len(data)<=32768
    packet=json.loads(data);assert packet['event']=='failed' and packet['caller_y_unchanged'] is True
    assert packet['inventory']['stub_starts']==4 and packet['inventory']['stub_live']==148
    final=snapshot();assert final['revoked'] and final['unknown_io'] and final['claims']==5
    assert (directory/'state/DIRTY.json').exists()
    try:(directory/'state').mkdir(mode=0o700)
    except FileExistsError:restart_refused=True
    else:restart_refused=False
    assert restart_refused
    for path in directory.rglob('*'):
        if path.is_file():
            dest=mirror/path.relative_to(directory);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,dest)
    save(mirror/'RESULT.json',dict(status='PASS_ACTUAL_PC_MANAGER_EXIT_CACHED_GRANT_QUARANTINE',command=argv,manager_pid=manager.pid,manager_start_ticks=mticks,
        manager_pidfd_terminal=True,native_pidfd_terminal=True,native_exit_code=2,manager_exit_code=0,initial=initial,at_manager_death=at_death,final=final,
        native_failed_packet=packet,lock_remained_blocked_while_native_live=lock_blocked,dirty_marker_retained=True,restart_into_same_directory_refused=restart_refused,
        observer_library_sha256=observer['sha256'],readonly_observer_FD_retained_until_PC_harness_exit=True,release_allowed=False,replay_allowed=False,BOARD='NOT_TESTED',actual_FPGA_calls=None))
    log.close();parent.close();os.close(pipe);os.close(lock);os.close(mpidfd);os.close(npidfd)
    print('PASS_ACTUAL_PC_MANAGER_EXIT_CACHED_GRANT_QUARANTINE')
if __name__=='__main__':main()
