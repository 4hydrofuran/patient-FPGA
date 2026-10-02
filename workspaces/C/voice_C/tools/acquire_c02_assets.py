"""Acquire specified Matcha/Vocos assets and pinned implementation evidence locally."""
import hashlib
import json
import urllib.request
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCES=ROOT/'evidence/c02/sources'
OUT=ROOT/'assets/tts'
REPO='csukuangfj/matcha-icefall-zh-baker'
REVISION='75e64a57a80fb370abb18a4e4d86bb090ed46e93'
VOCODER_URL='https://github.com/k2-fsa/sherpa-onnx/releases/download/vocoder-models/vocos-22khz-univ.onnx'


def open_url(url):
    return urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'voice-C-C02-public-assets'}),timeout=40)


def acquire(url,path,expected=None):
    if not path.exists():
        path.parent.mkdir(parents=True,exist_ok=True)
        temporary=path.with_suffix(path.suffix+'.download')
        with open_url(url) as response,temporary.open('wb') as target:
            size=0
            while chunk:=response.read(1024*1024):
                target.write(chunk);size+=len(chunk)
                if size%(16*1024*1024)<1024*1024: print('Downloading',path.name,'bytes',size,flush=True)
        if expected and hashlib.sha256(temporary.read_bytes()).hexdigest()!=expected:
            raise ValueError('Publisher hash mismatch: '+path.name)
        temporary.replace(path)
    actual=hashlib.sha256(path.read_bytes()).hexdigest()
    if expected and actual!=expected: raise ValueError('Existing asset hash mismatch')
    print('Acquired',path.name,'bytes',path.stat().st_size,flush=True)
    return dict(path=path.relative_to(ROOT).as_posix(),source_url=url,bytes=path.stat().st_size,
        sha256=actual,publisher_sha256=expected)


def main():
    metadata=json.loads((SOURCES/'csukuangfj__matcha-icefall-zh-baker.json').read_text(encoding='utf-8'))
    if metadata['sha']!=REVISION: raise ValueError('Baker revision changed')
    files=[]
    blobs={r['rfilename']:r for r in metadata['siblings']}
    for name in ['README.md','tokens.txt','lexicon.txt','phone.fst','date.fst','number.fst','model-steps-3.onnx']:
        files.append(acquire(f'https://huggingface.co/{REPO}/resolve/{REVISION}/{name}',OUT/'matcha-icefall-zh-baker'/name,
            blobs[name].get('lfs',{}).get('sha256')))
    files.append(acquire(VOCODER_URL,OUT/'vocos-22khz-univ.onnx'))
    for filename in ['offline-tts-matcha-impl.h','offline-tts-character-frontend.cc','offline-tts-matcha-model.cc']:
        try:
            acquire('https://raw.githubusercontent.com/k2-fsa/sherpa-onnx/v1.13.8/sherpa-onnx/csrc/'+filename,SOURCES/filename)
        except Exception as exc:
            (SOURCES/(filename+'.failed.json')).write_text(json.dumps(dict(error_type=type(exc).__name__,message=str(exc)),indent=2)+'\n',encoding='utf-8')
    try:
        with open_url('https://api.github.com/repos/gemelo-ai/vocos') as response:
            upstream=json.load(response)
        upstream_license=upstream.get('license',{}).get('spdx_id')
        (SOURCES/'vocos_upstream_repo.json').write_text(json.dumps(upstream,indent=2)+'\n',encoding='utf-8')
    except Exception as exc:
        upstream_license=None
        (SOURCES/'vocos_upstream_repo.failed.json').write_text(json.dumps(dict(error_type=type(exc).__name__,message=str(exc)),indent=2)+'\n',encoding='utf-8')
    lock=dict(acoustic_model=REPO,revision=REVISION,files=files,
        acquired_at_utc=datetime.now(timezone.utc).isoformat(),declared_weight_license=metadata.get('cardData',{}).get('license'),
        training_data_restriction='NON_COMMERCIAL_ONLY_PER_MODEL_CARD',
        vocoder_source=VOCODER_URL,vocoder_upstream_repo='https://github.com/gemelo-ai/vocos',
        vocoder_upstream_code_license=upstream_license,
        vocoder_export_weight_license='REVIEW_PENDING',baker_export_weight_license='REVIEW_PENDING',
        external_distribution='NOT_APPROVED_BY_THIS_AUDIT',
        dict_directory='NOT_DOWNLOADED_OR_USED; CURRENT_CHARACTER_FRONTEND_DOES_NOT_REQUIRE_OLD_JIEBA_DICT',
        runtime_assets=['model-steps-3.onnx','vocos-22khz-univ.onnx','tokens.txt','lexicon.txt','phone.fst','date.fst','number.fst'])
    (OUT/'model.lock.json').write_text(json.dumps(lock,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('C02 assets locked:',len(files),'training data non-commercial; export license pending',flush=True)


if __name__=='__main__': main()
