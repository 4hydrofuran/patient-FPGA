"""Fetch public publisher metadata only; do not print credentials or license text."""
import json
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'evidence/c01/sources'
SOURCES={
    'pypi_sherpa_onnx':'https://pypi.org/pypi/sherpa-onnx/json',
    'pypi_numpy':'https://pypi.org/pypi/numpy/json',
    'hf_checkpoint':'https://huggingface.co/api/models/csukuangfj/icefall-streaming-zipformer-small-ctc-zh-2025-04-01',
    'hf_onnx':'https://huggingface.co/api/models/csukuangfj/sherpa-onnx-streaming-zipformer-small-ctc-zh-int8-2025-04-01',
    'github_release':'https://api.github.com/repos/k2-fsa/sherpa-onnx/releases/tags/asr-models',
}


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    for name,url in SOURCES.items():
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'voice-C-C01-public-assets'})
            with urllib.request.urlopen(req,timeout=25) as response:
                data=json.load(response)
            (OUT/(name+'.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            if name.startswith('pypi'):
                print(name,'version:',data['info']['version'])
                for f in data['urls']:
                    if 'cp312' in f['filename'] and 'win_amd64' in f['filename']:
                        print('wheel:',f['filename'],'bytes:',f['size'])
            elif name.startswith('hf'):
                print(name,'revision:',data.get('sha'),'license:',data.get('cardData',{}).get('license'))
                print('files:',[x['rfilename'] for x in data.get('siblings',[])])
            else:
                assets=[a for a in data['assets'] if a['name']=='sherpa-onnx-streaming-zipformer-small-ctc-zh-int8-2025-04-01.tar.bz2']
                (OUT/'selected_release_asset.json').write_text(json.dumps(assets,indent=2)+'\n',encoding='utf-8')
                print('selected_release_assets:',[{k:a.get(k) for k in ('id','name','size','digest','updated_at')} for a in assets])
        except Exception as exc:
            record={'url':url,'exception':type(exc).__name__,'message':str(exc)}
            (OUT/(name+'.failed.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            print(name,'FAILED:',type(exc).__name__)


if __name__=='__main__':
    main()
