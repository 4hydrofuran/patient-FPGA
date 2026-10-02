"""Independent local file client; optionally send raw chunks at original audio rate."""
import argparse,json,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from voicec.audio import read_pcm16
from voicec.client import Client
from tools.benchmark_c03 import replay


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wav',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--paced',action='store_true')
    parser.add_argument('--consent-reference',default=None,help='Local reference for an authorized personal recording, if applicable')
    args=parser.parse_args();info,pcm=read_pcm16(args.wav,asr=True)
    if args.output.exists():raise RuntimeError('Output directory must be new; preserve previous runs')
    args.output.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix='c03-file-') as tmp,(args.output/'trace.jsonl').open('w',encoding='utf-8') as trace:
        spool=Path(tmp)
        def record(item):trace.write(json.dumps(item,ensure_ascii=False)+'\n');trace.flush()
        with Client(spool,asr_config=ROOT/'configs/asr.selected.json',stream_config=ROOT/'configs/stream.selected.json',response_timeout=60,trace_callback=record) as c:
            hello=c.call('hello');result=replay(c,spool,'file',pcm,paced=args.paced)
            (args.output/'report.json').write_text(json.dumps(dict(hello=hello,source_audio=info,
                consent_reference=args.consent_reference,authorization='CALLER_PROVIDED_REFERENCE_NOT_INDEPENDENTLY_VERIFIED' if args.consent_reference else 'NOT_ASSERTED_BY_CLIENT',
                result=result,microphone_opened=False,scope='LOCAL_ENGINEERING_REPLAY_NOT_HUMAN_QUALITY_ACCEPTANCE'),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            (args.output/'stderr.log').write_text(''.join(c.stderr),encoding='utf-8')
            print(json.dumps(dict(text=result['final']['text'],final=True,frames=result['final']['frames'],pacing=result['pacing']),ensure_ascii=False))


if __name__=='__main__':main()
