"""Auxiliary ASR on synthetic development audio; cannot replace a human listening test."""
import hashlib,json,sys,wave
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import numpy as np
from voicec.audio import read_pcm16
from voicec.asr import Asr
from voicec.metrics import cer


def convert(pcm):
    samples=np.frombuffer(pcm,dtype='<i2').astype(np.float64)
    count=round(len(samples)*16000/22050);output=np.empty(count)
    radius=32;cutoff=(8000/22050)*.95;offsets=np.arange(-radius,radius+1)
    for begin in range(0,count,8192):
        positions=np.arange(begin,min(begin+8192,count))*(22050/16000)
        indexes=np.floor(positions).astype(np.int64)[:,None]+offsets
        delta=positions[:,None]-indexes
        window=np.where(np.abs(delta)<=radius,.5+.5*np.cos(np.pi*delta/radius),0)
        kernel=2*cutoff*np.sinc(2*cutoff*delta)*window;kernel/=kernel.sum(axis=1)[:,None]
        output[begin:begin+len(positions)]=(samples[np.clip(indexes,0,len(samples)-1)]*kernel).sum(axis=1)
    return np.clip(np.rint(output),-32768,32767).astype('<i2').tobytes()


def main():
    out=ROOT/'evidence/c02/aux_asr';out.mkdir(parents=True,exist_ok=True)
    if (out/'report.json').exists():raise RuntimeError('Preserve auxiliary run')
    key=json.loads((ROOT/'listening/c02/reviewer_key.json').read_text(encoding='utf-8'))
    asr=Asr(ROOT/'configs/asr.selected.json');rows=[]
    for row in key:
        source=ROOT/'listening/c02/audio'/f"{row['listening_item_id']}.wav"
        info,pcm=read_pcm16(source)
        if info['sample_rate']!=22050:raise RuntimeError('Expected native TTS input')
        converted=convert(pcm);path=out/f"{row['listening_item_id']}.16k.wav"
        with wave.open(str(path),'wb') as f:
            f.setparams((1,2,16000,0,'NONE','not compressed'));f.writeframes(converted)
        result=asr.transcribe(path)
        rows.append(dict(listening_item_id=row['listening_item_id'],category=row['category'],
            expected_text=row['text'],asr_text=result['text'],source_sha256=info['audio_sha256'],
            resampled_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            diagnostic_cer=cer(row['text'],result['text']),result=result,
            human_judgment=None,scope='SYNTHETIC_TTS_THROUGH_ASR_ENGINEERING_ONLY'))
    (out/'report.json').write_text(json.dumps(dict(status='AUXILIARY_NOT_QUALITY_ACCEPTANCE',
        asr=asr.metadata,rows=rows,human_reviewed=0,student_cer=None,tts_intelligibility=None,
        warning='ASR and TTS errors are confounded. Digits vs Chinese spelling inflate literal CER. Does not prove correct pronunciation.',
        resampling='OFFLINE_AUXILIARY_ONLY_22050_TO_16000_WINDOWED_SINC_RADIUS32_CUTOFF7600HZ'),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('14 auxiliary synthetic-audio ASR results; human judgments remain null')


if __name__=='__main__':main()
