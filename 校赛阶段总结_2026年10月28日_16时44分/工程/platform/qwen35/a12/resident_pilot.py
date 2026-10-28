"""Actual CPU open -> vocab-only -> one warm -> normal close, no user answer."""
import argparse
import os
import select
import shutil
import time
from resident_evidence import ROOT,OUT,WORK,read,save,pin
from resident_manager import Manager
from livegen_binding import ReadOnlyPage

def main():
    p=argparse.ArgumentParser();p.add_argument('--tag',required=True);p.add_argument('--revision',type=int,default=2);a=p.parse_args();assert a.tag.isalnum();os.umask(0o077)
    folder=OUT/a.tag;folder.mkdir();directory=WORK/a.tag;build=OUT/('SERVICE_BUILD-v'+str(a.revision)+'.json');b=read(build)
    save(folder/'LAUNCH.json',dict(source=[pin(p) for p in sorted((ROOT/'platform/qwen35/a12').glob('resident_*.py'))],BOARD='NOT_TESTED'))
    m=Manager.__new__(Manager);m.page=m.p=None;m.fault=None;observer=None;fd=None;error=None;start=time.monotonic()
    try:
        m.__init__(build,directory);fd=os.dup(m.pidfd);observer=ReadOnlyPage(m.page,b['observer_library'],b['observer_sha256'])
        m.ready();warm=m.run_warm();result=m.normal_close()
    except BaseException as exc:
        error=type(exc).__name__+': '+str(exc);result=m.failed_observation(error) if getattr(m,'monitor',None) else dict(status='CONSTRUCTOR_FAILED')
    done=False
    if fd is not None:
        poll=select.poll();poll.register(fd,select.POLLIN);done=bool(poll.poll(0))
    result.update(error=error,private_directory=str(directory),owned_pidfd_terminal=done,independent_page=observer() if observer else None,elapsed_s=time.monotonic()-start)
    if m.p is not None and not done:save(folder/'LIVE_WAIT.json',result);raise RuntimeError('native live: retain and observe, no restart')
    for path in directory.rglob('*'):
        if path.is_file():
            target=folder/path.relative_to(directory);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target)
    save(folder/'RESULT.json',result)
    if observer:observer.close()
    if fd is not None:os.close(fd)
    print('PASS_RESIDENT_WARM_ONCE_PILOT' if error is None else error,flush=True)
    if error:raise SystemExit(1)
if __name__=='__main__':main()
