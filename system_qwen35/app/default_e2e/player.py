"""Owned playback subprocess: deadlines cannot hang the application thread.

No recording or acoustic loopback. Pulse drain is NOT measured audible output.
"""
import argparse,json,signal,threading
from pathlib import Path
from ..pc_audio import PulseAudio

def main():
    p=argparse.ArgumentParser();p.add_argument('wav');p.add_argument('--receipt',required=True);a=p.parse_args()
    cancel=threading.Event();signal.signal(signal.SIGUSR1,lambda *_:cancel.set())
    try:
        r=PulseAudio().play(Path(a.wav),cancel)
        Path(a.receipt).write_text(json.dumps(r),encoding='utf-8')
        return 0
    except Exception as e:
        Path(a.receipt).write_text(json.dumps({'error':repr(e),'playback_api_completed':False}),encoding='utf-8');return 2
if __name__=='__main__':raise SystemExit(main())
