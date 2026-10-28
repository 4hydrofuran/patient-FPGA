"""Pinned OpenSSH; reviewed gzip sent only after privileged payload-ready marker.

SSH and sudo credentials come only from hidden GUI input and never enter argv,
environment values, files or receipts. No timeout kills or automatic retries.
"""
import argparse
import datetime
import base64
import gzip
import hashlib
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'platform/qwen35/a10'))
from fetch_single_result import plan


def require_fresh_uart(capture,now=None):
    now=now or datetime.datetime.now(datetime.timezone.utc)
    armed=[e for e in capture['events'] if e['kind']=='armed']
    assert len(armed)==1,'One UART arm required'
    age=(now-datetime.datetime.fromisoformat(armed[0]['utc'].replace('Z','+00:00'))).total_seconds()
    assert capture['schema']=='A10_ONE_MANUAL_COLD_IRQ2_BOOT_V1'
    assert capture['closed'] is False and capture['status']=='ARMED_PASSIVE_WAIT_FOR_USER_POWER'
    assert capture['boot_commands_sent']==0 and capture['autoboot_stop_bytes_sent']==0
    assert 0<=age<=180,'UART arm expired before authenticated delivery'
    return age


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--script',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--uart-capture',type=Path,help='Require a fresh live passive UART reservation immediately before payload delivery')
    ap.add_argument('--session-auth-helper',type=Path,help='Generic same-user memory-pipe askpass client; no credential on command line')
    a=ap.parse_args();code=a.script.read_bytes();blob=gzip.compress(code);pin=hashlib.sha256(blob).hexdigest()
    auth=a.session_auth_helper.resolve() if a.session_auth_helper else ROOT/'evidence/model_pl_A/20261024-ttft10-01-v1/tt10_01_askpass.exe';assert auth.is_file()
    prompt=b'__TT10_01_VERIFIED_SUDO_AUTH__:';marker=b'__TT10_01_REVIEWED_PAYLOAD_READY__\n'
    remote="import sys,gzip,hashlib; print('__TT10_01_REVIEWED_PAYLOAD_READY__',flush=True); b=sys.stdin.buffer.read(%d); assert len(b)==%d and hashlib.sha256(b).hexdigest()==%r; exec(compile(gzip.decompress(b),'tt10_00_pinned_reviewed','exec'))"%(len(blob),len(blob),pin)
    argv,_=plan();argv[-1]='sudo -S -p '+prompt.decode()+' /usr/bin/python3 -B -I -c "'+remote+'"'
    a.output.mkdir(parents=True,exist_ok=False)
    (a.output/'reservation.json').write_text(json.dumps(dict(argv=argv,script_sha256=hashlib.sha256(code).hexdigest(),
         authentication_mode='USER_AUTHORIZED_SESSION_MEMORY_PIPE' if a.session_auth_helper else 'USER_HIDDEN_GUI',auth_helper_sha256=hashlib.sha256(auth.read_bytes()).hexdigest(),
         scope='EXACT_REVIEWED_TT10_00_SCRIPT; no retries or power actions',gzip_bytes=len(blob),gzip_sha256=pin),indent=2),encoding='utf-8')
    env=dict(os.environ,SSH_ASKPASS=str(auth),SSH_ASKPASS_REQUIRE='force',DISPLAY='tt10-hidden-auth')
    proc=subprocess.Popen(argv,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,
                          creationflags=subprocess.CREATE_NO_WINDOW)
    events=queue.Queue()
    def reader(which,stream):
        if which=='out':
            for line in iter(stream.readline,b''):events.put((which,line))
        else:
            for c in iter(lambda:stream.read(1),b''):events.put((which,c))
        events.put((which,None))
    threading.Thread(target=reader,args=('out',proc.stdout),daemon=True).start()
    threading.Thread(target=reader,args=('err',proc.stderr),daemon=True).start()
    ended=set();err=bytearray();answered=False;sent=False
    with (a.output/'stdout.txt').open('xb') as stream:
        while len(ended)<2:
            try:which,part=events.get(timeout=15)
            except queue.Empty:print('Pinned board operation running; ownership retained.',flush=True);continue
            if part is None:ended.add(which);continue
            if which=='out':
                if part==marker:
                    assert not sent
                    if a.uart_capture:
                        try:
                            capture=json.loads(a.uart_capture.read_text())
                            require_fresh_uart(capture)
                        except Exception as exc:
                            (a.output/'uart-delivery-refused.json').write_text(json.dumps(dict(error=type(exc).__name__+': '+str(exc),payload_sent=False),indent=2))
                            proc.stdin.close()
                            continue
                    proc.stdin.write(blob);proc.stdin.flush();sent=True
                else:stream.write(part);stream.flush()
            else:
                err.extend(part)
                if err.endswith(prompt):
                    assert not answered,'repeated authentication refused'
                    secret=subprocess.check_output([str(auth),'Verified board sudo'],creationflags=subprocess.CREATE_NO_WINDOW).strip()
                    assert secret and b'\n' not in secret and b'\r' not in secret
                    proc.stdin.write(secret+b'\n');proc.stdin.flush();secret=None;answered=True
    rc=proc.wait()
    if not proc.stdin.closed:proc.stdin.close()
    (a.output/'receipt.json').write_text(json.dumps(dict(exit_code=rc,stderr=err.decode(errors='replace'),
          script_sha256=hashlib.sha256(code).hexdigest(),payload_sent=sent,scope='TT10_01_REVIEWED_SCRIPT'),indent=2),encoding='utf-8')
    print(json.dumps(dict(exit_code=rc,output=str(a.output))));return rc

if __name__=='__main__':raise SystemExit(main())
