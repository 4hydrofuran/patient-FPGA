"""Explicit interactive microphone authorization gate; not run by unattended tests."""
import argparse,json,select,sys,tempfile,threading
from pathlib import Path
from .voice_loop import VoiceLoop

def stop_enter_pending(stream=None):
    """One synchronous stdin owner; no stale input thread after time limit."""
    stream=sys.stdin if stream is None else stream
    if not select.select([stream],[],[],0)[0]:return False
    line=stream.readline()
    if line=='':raise EOFError('Recording cancelled: terminal input closed')
    return True
def main():
    p=argparse.ArgumentParser();p.add_argument('--record-authorized',action='store_true');p.add_argument('--output',type=Path,required=True)
    p.add_argument('--model-backend',choices=('s0','s1'),default='s0')
    a=p.parse_args()
    if not a.record_authorized:raise PermissionError('Obtain explicit user recording consent before using --record-authorized')
    print('仅朗读合成句，不录其他人或真实病例。按Enter准备，等“现在开始说话”再读；读完按Enter停止，最长15秒；录音只存在临时目录。',flush=True)
    with tempfile.TemporaryDirectory(prefix='sp_voice_A_',dir='/dev/shm') as tmp:
        loop=VoiceLoop(a.output,spool=tmp,model_backend=a.model_backend)
        try:
            input('准备好后按Enter打开录音设备：');stop=threading.Event()
            print('正在打开设备，请先不要说话……',flush=True)
            wav=Path(tmp)/'authorized.wav'
            receipt=loop.player.record_push_to_talk(wav,stop,recording_authorized=True,
                on_ready=lambda:print('已收到音频数据，现在开始说话；读完按Enter停止：',flush=True),
                stop_requested=stop_enter_pending)
            print('录音已停止（'+receipt['stop_reason']+'），正在识别。',flush=True)
            # Persist numeric capture diagnostics before downstream ASR/model work.
            # No waveform or guessed transcript is saved in this receipt.
            with (a.output/'capture-receipt.json').open('x',encoding='utf-8') as f:json.dump(receipt,f,ensure_ascii=False,indent=2)
            # Host/operator action outside the student transcript protocol. Never
            # rewrite the recognized words or invent an ASR confidence.
            def confirm(text):
                print('原始转录：'+text)
                return input('只有原句准确时输入 YES；否则回车保持待审核/澄清：').strip()=='YES'
            result=loop.turn(wav,confirm_transcript=confirm)
            with (a.output/'microphone-result.json').open('x',encoding='utf-8') as f:json.dump({'recording':receipt,'result':result},f,ensure_ascii=False,indent=2)
            print(json.dumps({'asr':result['asr']['text'],'reply':result['application']['text'],'human_review_required':True},ensure_ascii=False))
        finally:loop.close()
if __name__=='__main__':main()
