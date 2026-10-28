"""Local synthetic software-test terminal; no HTTP, microphone or TTS service."""
import argparse
import json
from pathlib import Path
import sys
from .session import Session
from .domain import CASE_IDS
from .natural_prompt import prompt_messages as natural_prompt

def public_response(r):
    # Student-facing output excludes the case, prompt, candidate and score rubric.
    keys=('type','request_id','text','answer_source','fallback_reason','tts_ready','medical_review','message')
    return {k:r[k] for k in keys if k in r}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--case',choices=CASE_IDS,required=True)
    p.add_argument('--mode',choices=['training','exam'],default='training')
    p.add_argument('--software-test',action='store_true',help='Synthetic drafts only; not a teacher approval')
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--model-backend',choices=('s0','s1'),default='s0',help='Explicit W4A8 experimental S1; never automatic fallback')
    args=p.parse_args()
    session=Session(args.case,args.mode,software_test=args.software_test,prompt_builder=natural_prompt)
    args.output.mkdir(parents=True,exist_ok=False)
    from .native import NativeCPU
    from .native_w4a8 import NativeW4A8
    native=(NativeW4A8 if args.model_backend=='s1' else NativeCPU)(args.output/'native')
    try:
        with (args.output/'application.jsonl').open('x',encoding='utf-8') as audit:
            for line in sys.stdin:
                try:r=session.submit(json.loads(line),native)
                except (ValueError,RuntimeError) as exc:r={'type':'request_error','message':str(exc),'tts_ready':False}
                audit.write(json.dumps(r,ensure_ascii=False)+'\n');audit.flush()
                print(json.dumps(public_response(r),ensure_ascii=False),flush=True)
                if r.get('tts_ready'):
                    session.trusted_delivery(r['request_id'],r['epoch'],kind='PC_TEXT_TEST_ACK')
            session.finish()
            # Operator audit file, not a student message or model self-assessment.
            with (args.output/'score.json').open('x',encoding='utf-8') as f:
                json.dump(session.recompute_score_for_host(),f,ensure_ascii=False,indent=2)
    finally:native.close()
    return 0
if __name__=='__main__':raise SystemExit(main())
