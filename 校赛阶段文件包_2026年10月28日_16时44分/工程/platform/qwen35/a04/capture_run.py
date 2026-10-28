"""Sequential high-precision then S0 observations; reuse pinned token fixture."""
import hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'eval/qwen35/a04/captures-v1'
def main():
    OUT.mkdir(exist_ok=False)
    lines=[json.loads(s) for s in (ROOT/'eval/qwen35/a01/f16-v1/main.jsonl').read_text().splitlines()]
    request=next(x['request'] for x in lines if x.get('request',{}).get('id')=='context-256')
    assert len(request['tokens'])==256
    with (OUT/'tokens.json').open('x') as f:json.dump({'tokens':request['tokens'],'provenance':'Reused A01 exact256 fixture; no new clinical/patient input'},f)
    for kind,file in [('H0_F16','qwen35-text-f16.gguf'),('S0_Q4','qwen35-text-Q4_K_M.gguf')]:
        argv=['/home/member-a/qwen35-a04/build-v1/capture',str(ROOT/'artifacts/qwen35-0.8b'/file),str(OUT/'tokens.json'),str(OUT/kind)]
        r=subprocess.run(argv,capture_output=True,text=True)
        with (OUT/(kind+'-command.json')).open('x') as f:json.dump({'argv':argv,'exit_code':r.returncode,'stdout':r.stdout,'stderr':r.stderr},f,indent=2)
        if r.returncode:return r.returncode
        cap=json.loads((OUT/kind/'capture.json').read_text())
        for rec in cap['records']:
            for field in ('input','output'):
                p=OUT/kind/rec[field]['file'];rec[field]['sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
        cap['source_revision']='2fc06364715b967f1860aea9cf38778875588b17'
        cap['runtime_commit']='81e39ad34368329b5db77620721510fd91107e80'
        cap['model_sha256']=json.loads((ROOT/'models/model.lock.json').read_text())['converted_files'][file]['sha256']
        cap['capture_binary_sha256']=hashlib.sha256(Path(argv[0]).read_bytes()).hexdigest()
        with (OUT/kind/'manifest.json').open('x') as f:json.dump(cap,f,indent=2)
        print(kind+': '+str(len(cap['records']))+' actual records',flush=True)
    return 0
if __name__=='__main__':raise SystemExit(main())
