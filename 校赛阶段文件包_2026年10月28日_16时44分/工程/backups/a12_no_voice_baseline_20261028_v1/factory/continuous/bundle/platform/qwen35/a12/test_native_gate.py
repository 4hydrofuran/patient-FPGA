"""Actual C++ SO_PEERCRED and borrowed flock, actual Python permission manager."""
import fcntl
import os
from pathlib import Path
import sys
import tempfile
import time
from common import ROOT,EVIDENCE,command,save
from supervisor import OwnedWorker


if __name__=='__main__':
    out=EVIDENCE/'native-gate';out.mkdir(exist_ok=False)
    binary=out/'gate-test'
    command(['g++','-std=c++17','-O2','-Wall','-Wextra','-Werror',
             '-I'+str(ROOT/'runtime/qwen35_w4a8/a12'),'-I'+str(ROOT/'platform/qwen35/a11'),
             '-I/home/member-a/qwen35-a05/source-v3/vendor/nlohmann',
             ROOT/'platform/qwen35/a12/test_gate.cpp','-o',binary],out/'compile.json')
    with tempfile.TemporaryDirectory() as temporary:
        path=Path(temporary)/'lock'
        with path.open('a+') as lock:
            os.chmod(path,0o600);fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            fields=Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()
            env=dict(os.environ,TEST_LOCK_FD=str(lock.fileno()),TEST_PARENT_TICKS=fields[19],TEST_LOCK_PATH=str(path))
            w=OwnedWorker([str(binary)],directory=out/'worker',env=env,inherited_fds=(lock.fileno(),),
                health=lambda:None,max_runs=1,max_loads=1,expires=time.monotonic()+10)
            assert w.get(2)['type']=='ready'
            w.send(dict(op='test'));assert w.get(2)['type']=='allowed'
            w.send(dict(op='test'));assert w.get(2)['type']=='denied'
            with path.open('a+') as observer:
                try:fcntl.flock(observer,fcntl.LOCK_EX|fcntl.LOCK_NB)
                except BlockingIOError:pass
                else:raise AssertionError('borrowed child lock unexpectedly unlocked parent')
            assert w.close(timeout=2)
    save(out/'SUMMARY.json',dict(status='PASS_PC_LINUX_CPP_PYTHON_PERMISSION_AND_FLOCK',
        checks=['direct-parent SO_PEERCRED','same inherited flock','bounded permission','denial before submission','normal child exit','parent lock retained'],
        BOARD='NOT_TESTED'))
    print('PASS_PC_LINUX_CPP_PYTHON_PERMISSION_AND_FLOCK')
