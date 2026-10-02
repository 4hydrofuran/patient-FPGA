"""One real JSONL synthesis; copy evidence before shutdown removes spool output."""
import json
import shutil
import sys
import tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from voicec.client import Client

out=ROOT/'evidence/c02/smoke_final'
out.mkdir(parents=True,exist_ok=True)
if (out/'response.json').exists(): raise RuntimeError('Use a new evidence directory')
with tempfile.TemporaryDirectory(prefix='c02-smoke-') as tmp:
    with Client(Path(tmp),tts_config=ROOT/'configs/tts.threads1.batch1.json',response_timeout=60) as c:
        hello=c.call('hello')
        (out/'hello.json').write_text(json.dumps(hello,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        response=c.call('synthesize',session_id='smoke',text='我没有发热，也没有咳嗽。',output_dir='smoke/out')
        (out/'response.json').write_text(json.dumps(response,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        if response['type']!='result': raise RuntimeError(response)
        shutil.copyfile(Path(tmp)/response['wav_path'],out/'speech.wav')
        (out/'stderr.log').write_text(''.join(c.stderr),encoding='utf-8')
        print(json.dumps(response,ensure_ascii=False))
