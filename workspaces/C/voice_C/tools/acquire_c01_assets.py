"""Fetch pinned public model files and Windows wheels into this workspace only."""
import hashlib
import json
import os
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
EVIDENCE=ROOT/'evidence/c01'
SOURCES=EVIDENCE/'sources'
REPO='csukuangfj/sherpa-onnx-streaming-zipformer-small-ctc-zh-int8-2025-04-01'


def get(url):
    return urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'voice-C-C01-public-assets'}),timeout=40)


def main():
    info=json.loads((SOURCES/'hf_onnx.json').read_text(encoding='utf-8'))
    revision=info['sha']
    with get(f'https://huggingface.co/api/models/{REPO}/revision/{revision}?blobs=true') as response:
        metadata=json.load(response)
    (SOURCES/'hf_onnx_pinned_blobs.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    blobs={r['rfilename']:r for r in metadata['siblings']}
    model_dir=ROOT/'assets/asr/zipformer-small-ctc-zh-int8-2025-04-01'
    model_dir.mkdir(parents=True,exist_ok=True)
    files=[]
    for name in ['README.md','tokens.txt','bbpe.model','model.int8.onnx']:
        url=f'https://huggingface.co/{REPO}/resolve/{revision}/{name}'
        dest=model_dir/name
        expected=blobs[name].get('lfs',{}).get('sha256')
        if not dest.exists():
            tmp=dest.with_suffix(dest.suffix+'.download')
            with get(url) as response, tmp.open('wb') as target:
                size=0
                while True:
                    chunk=response.read(1024*1024)
                    if not chunk: break
                    target.write(chunk);size+=len(chunk)
                    if size%(8*1024*1024)<1024*1024:
                        print('Downloading',name,'bytes:',size,flush=True)
            if expected and hashlib.sha256(tmp.read_bytes()).hexdigest()!=expected:
                raise RuntimeError('Publisher LFS hash mismatch: '+name)
            tmp.replace(dest)
        digest=hashlib.sha256(dest.read_bytes()).hexdigest()
        if expected and digest!=expected:
            raise RuntimeError('Existing file does not match publisher hash: '+name)
        files.append(dict(path=dest.relative_to(ROOT).as_posix(),sha256=digest,bytes=dest.stat().st_size,
                          source_url=url,publisher_lfs_sha256=expected))
        print('Acquired',name,'bytes:',dest.stat().st_size,flush=True)
    upstream=json.loads((SOURCES/'hf_checkpoint.json').read_text(encoding='utf-8'))
    with get(f'https://huggingface.co/{upstream["id"]}/resolve/{upstream["sha"]}/README.md') as response:
        (SOURCES/'upstream_model_card.md').write_bytes(response.read())
    lock=dict(model_id=REPO,revision=revision,files=files,
              downloaded_at_utc=datetime.now(timezone.utc).isoformat(),
              upstream_checkpoint=upstream['id'],upstream_revision=upstream['sha'],
              upstream_declared_license=upstream.get('cardData',{}).get('license'),
              onnx_repo_declared_license=metadata.get('cardData',{}).get('license'),
              sample_audio_downloaded=False,redistribution='NOT_AUTHORIZED_BY_THIS_AUDIT')
    (ROOT/'assets/asr/model.lock.json').write_text(json.dumps(lock,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    wheels=ROOT/'assets/wheels';wheels.mkdir(parents=True,exist_ok=True)
    base=Path(r'C:\Users\quq\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe')
    pinned=['sherpa-onnx==1.13.8','numpy==2.5.3']
    command=[str(base),'-m','pip','download','--disable-pip-version-check','--retries','0',
             '--only-binary=:all:','--dest',str(wheels),*pinned]
    proc=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',timeout=120,
                        env=os.environ|{'PYTHONUTF8':'1'})
    (EVIDENCE/'wheel_download.log').write_text(proc.stdout+proc.stderr,encoding='utf-8')
    (EVIDENCE/'wheel_download_command.json').write_text(json.dumps(dict(argv=command,exit_code=proc.returncode),indent=2)+'\n',encoding='utf-8')
    print('Wheel download exit:',proc.returncode,flush=True)
    if proc.returncode: raise SystemExit(proc.returncode)
    entries=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,
                  sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(wheels.glob('*.whl'))]
    (ROOT/'assets/wheels/wheels.lock.json').write_text(json.dumps(entries,indent=2)+'\n',encoding='utf-8')
    print('Pinned model files:',len(files),'offline wheels:',len(entries),flush=True)


if __name__=='__main__':
    main()
