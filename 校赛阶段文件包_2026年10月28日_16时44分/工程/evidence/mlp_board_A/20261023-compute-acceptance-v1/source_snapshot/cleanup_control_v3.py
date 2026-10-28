"""Local control client. Default PLAN_ONLY; no SSH or automatic resume."""
import argparse
import json
import os
from pathlib import Path
import socket
import stat
import struct

DIRECTORY=Path('/var/lib/kv260-a11/cleanup-v3-20261023/state')


def request(action,authorization_id=None,generation=None):
    assert os.geteuid()==0,'root control only'
    for path in (DIRECTORY.parent,DIRECTORY):
        info=path.lstat()
        assert stat.S_ISDIR(info.st_mode) and info.st_uid==0 and not info.st_mode&0o022
    path=DIRECTORY/'control.sock';info=path.lstat()
    assert stat.S_ISSOCK(info.st_mode) and info.st_uid==0 and not info.st_mode&0o077
    payload={'action':action}
    if action=='resume':payload.update(authorization_id=authorization_id,generation=generation)
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as s:
        s.settimeout(45);s.connect(str(path))
        assert struct.unpack('3i',s.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))[1]==0
        s.sendall(json.dumps(payload).encode()+b'\n')
        data=b''
        while not data.endswith(b'\n') and len(data)<16384:
            part=s.recv(16384-len(data))
            if not part:break
            data+=part
        assert data.endswith(b'\n'),'unknown client reply; query status, do not replay resume'
        return json.loads(data)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    mode=p.add_mutually_exclusive_group()
    mode.add_argument('--status',action='store_true')
    mode.add_argument('--resume-authorized',action='store_true')
    p.add_argument('--authorization-id');p.add_argument('--generation',type=int)
    a=p.parse_args()
    if not a.status and not a.resume_authorized:
        print(json.dumps({'mode':'PLAN_ONLY','BOARD':'NOT_TESTED','no_connection':True}));return 0
    if a.resume_authorized and (not a.authorization_id or a.generation is None):
        p.error('resume requires explicit authorization-id and status generation')
    result=request('status' if a.status else 'resume',a.authorization_id,a.generation)
    print(json.dumps(result));return 2 if 'error' in result else 0


if __name__=='__main__':raise SystemExit(main())
