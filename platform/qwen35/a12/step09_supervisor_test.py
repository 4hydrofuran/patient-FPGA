"""Exercise the exact new permission hook over real Linux IPC/flock; fake child only."""
import fcntl,json,os,signal,sys,time
from step09_common import OUT
from common import save
from step09_supervisor import OwnedWorker

CHILD=r'''
import json,os,signal,socket,sys
signal.signal(signal.SIGUSR1,lambda *a:None)
s=socket.socket(fileno=int(os.environ['SP_A12_CONTROL_FD']));f=s.makefile('r');seq={'router':0,'backend':0}
def permit(phase,job):
 lane='router' if phase.startswith('router') else 'backend';seq[lane]+=1
 s.sendall((json.dumps(dict(sequence=seq[lane],phase=phase,job=job,pid=os.getpid()))+'\n').encode())
 return json.loads(f.readline())['allow']
assert permit('router_open',0) and permit('device_open',0) and permit('weight_load',1)
print(json.dumps(dict(type='ready')),flush=True)
for line in sys.stdin:
 req=json.loads(line)
 if req['op']=='shutdown':assert permit('router_close',0);break
 assert permit('submit',1)
 # This double marks completion synchronously before requesting the next permission.
 print(json.dumps(dict(type='completed',job=1)),flush=True)
 assert not permit('submit',2)
 print(json.dumps(dict(type='result',status='CANCELLED',partial_output_usable=False)),flush=True)
'''
if __name__=='__main__':
    path=OUT/'pc-boundary.lock'
    with path.open('x') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        w=OwnedWorker([sys.executable,'-B','-u','-c',CHILD],directory=OUT/'pc-boundary',env=os.environ,inherited_fds=(lock.fileno(),),health=lambda:None,max_runs=4,max_loads=1,expires=time.monotonic()+30)
        assert w.get(5)['type']=='ready'
        def hook(r):
            if r['phase']=='submit' and w.runs==1:w.cancel('PC safe-boundary hook test')
        w.before_permission=hook;w.send(dict(op='generate'))
        deadline=time.monotonic()+5
        while not w.delivery_cancelled and time.monotonic()<deadline:time.sleep(.01)
        assert w.delivery_cancelled and w.runs==1
        try:w.get(5)
        except RuntimeError:pass
        else:raise AssertionError('late result delivered')
        try:w.send(dict(op='generate'))
        except RuntimeError:pass
        else:raise AssertionError('cancelled worker reused')
        assert w.close(timeout=5)
        with path.open('r') as other:
            try:fcntl.flock(other,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:pass
            else:raise AssertionError('parent lock lost')
        permits=[r for r in w.records if r['event']=='PERMISSION']
        assert [r['allow'] for r in permits if r['request']['phase']=='submit']==[True,False]
        assert permits[-1]['request']['phase']=='router_close' and permits[-1]['allow']
    save(OUT/'BOUNDARY_PC.json',dict(status='PASS_PC_EXACT_NEW_HOOK_CANCEL_DENY_LATE_REUSE_NORMAL_CLOSE_FLOCK',submissions=1,worker_exit=0,BOARD='NOT_TESTED',child='CONTROL_DOUBLE_NO_XRT'))
    print('PASS_PC_NEW_BOUNDARY_HOOK_AND_NORMAL_CLOSE')
