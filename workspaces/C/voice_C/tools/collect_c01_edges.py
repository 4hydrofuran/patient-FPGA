"""Preserve real-model outputs on synthetic silence/clipping/short boundary inputs."""
import json
import sys
import wave
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from voicec.client import Client


def main():
    out=ROOT/'evidence/c01/edge_inputs';out.mkdir(parents=True,exist_ok=True)
    results=[]
    cases={'silence':b'\0\0'*16000,'short_clip':b'\xff\x7f'*320,
        'clipped':(b'\xff\x7f'*80+b'\x00\x80'*80)*100}
    with Client(out,asr_config=ROOT/'configs/asr.selected.json') as client:
        hello=client.call('hello')
        for name,pcm in cases.items():
            directory=out/name;directory.mkdir(exist_ok=True)
            path=directory/'in.wav'
            if path.exists(): raise RuntimeError('Preserve existing edge run; never overwrite')
            with wave.open(str(path),'wb') as f:
                f.setparams((1,2,16000,0,'NONE','not compressed'));f.writeframes(pcm)
            result=client.call('transcribe',session_id=name,language='zh',wav_path=name+'/in.wav')
            results.append(dict(input_kind='SYNTHETIC_BOUNDARY_NOT_SPEECH_QUALITY',case=name,response=result))
    (out/'report.json').write_text(json.dumps(dict(hello=hello,cases=results),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Boundary cases preserved:',len(results),'actual decoder used')


if __name__=='__main__': main()
