"""Rehash every prior accepted evidence byte without editing old failures."""
import json
from common import ROOT,sha,save
from step08_common import OUT

PINS={
'evidence/mlp_board_A/20261023-compute-acceptance-v1':'4e817a8add532e941c8628c2aef180f1099d4b2090f29cf7925d1723641e9a80',
'evidence/model_pl_A/20261023-preboard-v1':'46ca1282e0c8a6b4a25f350a86cdbe6de10170c128f9a642417793ba1893b2b5',
'evidence/model_pl_A/20261023-step06-v1':'e7ac919285b05f711ba36a72ee3950e3aad21a909fbe116794efbe33699d4c58',
'evidence/model_pl_A/20261023-step07-single-v1':'6d95749df4b9f6876614f9a16caa88b8c175f9caf6cf6978027cab9843edf3d0',
'evidence/model_pl_A/20261024-step07-finalize-v1':'7d7d06d266ed20e9ee7e367307d3771b05049903c1d07b9ffecfdeffeec32a46',
'evidence/model_pl_A/20261024-step07-mlp-v1':'0de8070d60124ba726c58be3389029d0bd3a751d32e133ac14a9e351855c8856',
'evidence/model_pl_A/20261024-step06-review-v1':'d3e9dd73870becef4788a87b82d96b84889561b1badb8383e1ad349e51b1ccdb'}

if __name__=='__main__':
    results=[]
    for relative,pin in PINS.items():
        p=ROOT/relative/'SEAL.json'
        assert sha(p)==pin,relative
        files=json.loads(p.read_text())['files']
        for name,row in files.items():
            q=ROOT/name;assert q.is_file() and q.stat().st_size==row['bytes'] and sha(q)==row['sha256'],name
        item=dict(seal=p.relative_to(ROOT).as_posix(),sha256=pin,files=len(files),status='ALL_BYTES_PRESERVED')
        results.append(item);print(json.dumps(item),flush=True)
    save(OUT/'HISTORICAL_PRESERVATION.json',results)
