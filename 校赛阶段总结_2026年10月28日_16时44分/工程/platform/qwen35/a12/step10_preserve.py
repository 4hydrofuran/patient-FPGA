"""Check every file in the nine historical seals without modifying those batches."""
import json
from common import ROOT,sha,save
from step10_common import OUT
from step08_preserve import PINS
if __name__=='__main__':
    pins=dict(PINS)
    pins['evidence/model_pl_A/20261024-step08-v1']='538b8ebc3450895ffa3f421155b5542b43b78afe347abd64d97ef4d151621f24'
    pins['evidence/model_pl_A/20261024-step09-v1']='3eb2cb192e0ccf66db74cefef99421f2d6e217f349dcdb7b91ccc880d71704b9'
    rows=[]
    for name,pin in pins.items():
        seal=ROOT/name/'SEAL.json';assert sha(seal)==pin
        files=json.loads(seal.read_text(encoding='utf-8'))['files']
        for relative,row in files.items():
            p=ROOT/relative;assert p.stat().st_size==row['bytes'] and sha(p)==row['sha256'],relative
        rows.append(dict(seal=seal.relative_to(ROOT).as_posix(),sha256=pin,files=len(files),status='ALL_BYTES_PRESERVED'))
    save(OUT/'HISTORICAL_PRESERVATION.json',rows)
    print(json.dumps(dict(status='PASS_ALL_HISTORICAL_FILES',files=sum(r['files'] for r in rows))))
