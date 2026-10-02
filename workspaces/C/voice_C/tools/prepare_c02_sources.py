"""Audit C01 immutable baseline and obtain public C02 model provenance only."""
import hashlib
import json
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'evidence/c02'
MODELS=['csukuangfj/matcha-icefall-zh-baker','csukuangfj/vocos-22khz-univ',
        'csukuangfj/icefall-tts-baker-matcha','charactr/vocos-mel-22khz']


def fetch(url):
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'voice-C-C02-public-provenance'}),timeout=40) as response:
        return response.read()


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    baseline=ROOT/'evidence/c01/artifact_manifest.json'
    copied=OUT/'c01_before_changes.json'
    if not copied.exists():
        manifest=json.loads(baseline.read_text(encoding='utf-8'))
        for row in manifest['files']:
            if hashlib.sha256((ROOT.parent/row['path']).read_bytes()).hexdigest()!=row['sha256']:
                raise ValueError('C01 changed before C02: '+row['path'])
        copied.write_bytes(baseline.read_bytes())
        print('C01 baseline verified:',len(manifest['files']),'files',flush=True)
    sources=OUT/'sources';sources.mkdir(exist_ok=True)
    for model in MODELS:
        name=model.replace('/','__')
        try:
            metadata=json.loads(fetch('https://huggingface.co/api/models/'+model+'?blobs=true'))
            (sources/(name+'.json')).write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            (sources/(name+'.card.md')).write_bytes(fetch('https://huggingface.co/'+model+'/resolve/'+metadata['sha']+'/README.md'))
            print('Model',model,'revision',metadata['sha'],'declared license',metadata.get('cardData',{}).get('license'),flush=True)
        except Exception as exc:
            (sources/(name+'.failed.json')).write_text(json.dumps(dict(model=model,error_type=type(exc).__name__,message=str(exc)),indent=2)+'\n',encoding='utf-8')
            print('Source not available:',model,type(exc).__name__,flush=True)


if __name__=='__main__': main()
