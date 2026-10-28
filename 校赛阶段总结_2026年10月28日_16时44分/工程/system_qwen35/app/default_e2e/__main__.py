"""One-command console UI. No microphone starts without a separate workflow."""
import argparse,json,threading
from .service import Service
from .policy import HardwareUnavailable
from .review import ReviewGate

def main():
    p=argparse.ArgumentParser(description='A08 offline simulated-patient PC software demo (teacher review pending)')
    p.add_argument('--output',required=True);p.add_argument('--mode',choices=['cpu_same_math','no_hardware','fpga_required'],default='cpu_same_math')
    p.add_argument('--llm-threads',type=int,default=3);p.add_argument('--tts-threads',type=int,default=2)
    p.add_argument('--prompt-style',choices=['old','facts_v4'],default='facts_v4');p.add_argument('--text');p.add_argument('--wav')
    p.add_argument('--native-manifest',choices=['modules/linear_A/manifest.a08.json','modules/linear_A/manifest.a09.json'],default='modules/linear_A/manifest.a08.json')
    a=p.parse_args()
    try:s=Service(a.output,llm_threads=a.llm_threads,tts_threads=a.tts_threads,mode=a.mode,prompt_style=a.prompt_style,native_manifest=a.native_manifest)
    except HardwareUnavailable as e:print(json.dumps({'status':'HARDWARE_UNAVAILABLE','message':str(e),'actual_backend':None}));return 2
    def turn(**kw):
        try:
            r=s.turn(**kw);print(json.dumps({'status':r['status'],'answer':r.get('application',{}).get('text'),'answer_source':r['answer_source'],
                'actual_backend':r['actual_backend'],'error':r.get('error'),'score':r.get('score'),'trace':str(s.output/'rounds.jsonl')},ensure_ascii=False),flush=True)
            return 0 if r['status']=='COMPLETED' else 3
        except Exception as e:print(json.dumps({'error':str(e)},ensure_ascii=False),flush=True);return 3
    active=None
    review=ReviewGate(lambda event:print(json.dumps({'transcript_review':event,'reply':'/confirm '+event['ticket']+' yes|no'},ensure_ascii=False),flush=True))
    try:
        print('离线软件演示已就绪。教师审核未完成；不是诊疗设备。',flush=True)
        if a.text is not None or a.wav is not None:return turn(text=a.text,wav=a.wav)
        print('输入问诊文本，或 /wav 绝对路径。/case SYN_CP_02 切病例；/cancel 取消；/restart 重启；/status；/quit。不会自动录音。',flush=True)
        while True:
            try:line=input('> ').strip()
            except EOFError:break
            if line=='/quit':break
            try:
                if line=='/cancel':print(s.cancel());continue
                if line.startswith('/confirm '):
                    parts=line.split()
                    if len(parts)!=3:raise ValueError('/confirm <ticket> yes|no')
                    print({'confirmation_accepted':review.confirm(parts[1],parts[2])});continue
                if line=='/status':print({'phase':s.phase,'profile':s.profile,'case':s.session.snapshot()['case_id']});continue
                if line=='/restart':s.restart();continue
                if line.startswith('/case '):s.switch_case(line[6:]);continue
                if active and active.is_alive():print('忙碌中；可 /cancel，下一轮不排队。');continue
                if not line:continue
                kw={'wav':line[5:],'review_gate':review} if line.startswith('/wav ') else {'text':line}
                active=threading.Thread(target=turn,kwargs=kw);active.start()
            except Exception as e:print('错误：'+str(e),flush=True)
    finally:
        if active and active.is_alive():s.cancel();active.join(75)
        s.close()
    return 0
if __name__=='__main__':raise SystemExit(main())
