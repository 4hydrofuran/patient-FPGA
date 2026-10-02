"""First real incremental PCM request trace, not paced and not microphone capture."""
import json,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from voicec.client import Client
from voicec.audio import read_pcm16

out=ROOT/'evidence/c03/smoke';out.mkdir(parents=True,exist_ok=True)
if (out/'result.json').exists():raise RuntimeError('Preserve previous evidence')
row=json.loads((ROOT/'data/c01_public/manifest.jsonl').read_text(encoding='utf-8').splitlines()[0])
info,pcm=read_pcm16(ROOT/'data/c01_public'/row['audio_path'],asr=True)
with tempfile.TemporaryDirectory(prefix='c03-smoke-') as tmp,(out/'trace.jsonl').open('w',encoding='utf-8') as trace:
    root=Path(tmp);(root/'s').mkdir()
    def record(item):trace.write(json.dumps(item,ensure_ascii=False)+'\n');trace.flush()
    with Client(root,asr_config=ROOT/'configs/asr.selected.json',stream_config=ROOT/'configs/stream.selected.json',response_timeout=60,trace_callback=record) as c:
        hello=c.call('hello')
        begin=c.call('asr_begin',session_id='s',sample_rate=16000,channels=1,format='pcm_s16le')
        if begin['type']!='result':raise RuntimeError(begin)
        stream=begin['stream_id'];chunks=[]
        for seq,offset in enumerate(range(0,len(pcm),6400)):
            path=root/'s/chunk.pcm';path.write_bytes(pcm[offset:offset+6400])
            result=c.call('asr_push',stream_id=stream,seq=seq,pcm_path='s/chunk.pcm',final=offset+6400>=len(pcm))
            chunks.append(result)
            if result['type']!='result':raise RuntimeError(result)
            path.unlink()
        final=c.call('asr_finish',stream_id=stream)
        duplicate=c.call('asr_finish',stream_id=stream)
        (out/'result.json').write_text(json.dumps(dict(hello=hello,begin=begin,chunk_count=len(chunks),final=final,
            duplicate_final=duplicate,source_audio_sha256=info['audio_sha256'],scope='UNPACED_INCREMENTAL_ENGINEERING_NOT_LIVE_AUDIO'),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        (out/'stderr.log').write_text(''.join(c.stderr),encoding='utf-8')
        print(json.dumps(dict(streaming_enabled=hello['capabilities']['streaming_asr'],chunks=len(chunks),final=final,duplicate_final=duplicate),ensure_ascii=False))
