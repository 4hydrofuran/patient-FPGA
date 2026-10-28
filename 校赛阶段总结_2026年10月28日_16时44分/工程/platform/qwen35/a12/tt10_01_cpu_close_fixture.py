"""Synthetic Linux CPU child for close fault injection; no devices or model math."""
import json
import os
from pathlib import Path
import signal
import socket
import sys
import time

mode=sys.argv[1];release=Path(sys.argv[2]);cancelled=False
def emit(r):print(json.dumps(r),flush=True)
def cancel(sig,frame):
    global cancelled
    cancelled=True
signal.signal(signal.SIGUSR1,cancel)
device=open('/dev/zero','rb') if mode=='device' else None
emit(dict(type='ready',synthetic_fixture=True))
if mode=='permission':
    sock=socket.socket(fileno=int(os.environ['SP_A12_CONTROL_FD']))
    sock.sendall((json.dumps(dict(sequence=1,pid=os.getpid(),phase='device_open',job=0))+'\n').encode())
    reply=json.loads(sock.makefile('r').readline());emit(dict(type='denied',allow=reply['allow']))
    for line in sys.stdin:
        if json.loads(line)['op']=='shutdown':break
    sys.exit(0)
for line in sys.stdin:
    req=json.loads(line)
    if req['op']=='shutdown':
        if mode=='bad_exit':sys.exit(7)
        if mode=='timeout':
            while not release.exists():time.sleep(.01)
        break
    if req['op']=='generate':
        emit(dict(type='token',id=req['id'],index=0,token=10,synthetic_fixture=True))
        while not cancelled:time.sleep(.01)
        emit(dict(type='result',id=req['id'],status='CANCELLED',partial_output_usable=False,state_cleared_before_response=True,state_position_after_clear=-1,synthetic_fixture=True))
emit(dict(type='shutdown_complete',synthetic_fixture=True))
