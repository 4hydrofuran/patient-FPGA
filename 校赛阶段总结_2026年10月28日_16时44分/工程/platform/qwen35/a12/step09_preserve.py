"""Verify all eight sealed historical batches byte-for-byte."""
import json
from common import ROOT,sha,save
from step09_common import OUT
from step08_preserve import PINS

if __name__=='__main__':
    pins=dict(PINS);pins['evidence/model_pl_A/20261024-step08-v1']='538b8ebc3450895ffa3f421155b5542b43b78afe347abd64d97ef4d151621f24'
    rows=[]
    for relative,pin in pins.items():
        seal=ROOT/relative/'SEAL.json';assert sha(seal)==pin
        files=json.loads(seal.read_text(encoding='utf-8'))['files']
        for name,row in files.items():
            p=ROOT/name;assert p.stat().st_size==row['bytes'] and sha(p)==row['sha256'],name
        rows.append(dict(seal=seal.relative_to(ROOT).as_posix(),sha256=pin,files=len(files),status='ALL_BYTES_PRESERVED'))
    save(OUT/'HISTORICAL_PRESERVATION.json',rows);print(json.dumps(dict(status='PASS_HISTORICAL_BYTES',files=sum(r['files'] for r in rows))))
