"""Read-only comparison of old/new actual ARM feature settings."""
import json
from pathlib import Path
from common import ROOT,save
from step10_common import OUT
def cache(p):
    result={}
    for s in p.read_text().splitlines():
        if '=' in s and ':' in s and not s.startswith(('#','//')):
            k,v=s.split('=',1);k=k.split(':',1)[0]
            if k.startswith(('GGML_','CMAKE_C_FLAGS','CMAKE_CXX_FLAGS','CMAKE_BUILD_TYPE')):result[k]=v
    return result
if __name__=='__main__':
    old=json.loads((ROOT/'evidence/model_pl_A/20261023-preboard-v1/ARM_BUILD_FINAL.json').read_text())
    oldroot=Path(old['files']['libllama.so']['path']).parent.parent
    new=json.loads((OUT/'BUILD-v1.json').read_text())
    a=cache(oldroot/'CMakeCache.txt');b=cache(Path(new['workspace'])/'arm-llama/CMakeCache.txt')
    diff={k:dict(before=a.get(k),after=b.get(k)) for k in sorted(a.keys()|b.keys()) if a.get(k)!=b.get(k)}
    save(OUT/'ARM_CACHE_COMPARISON.json',diff);print(json.dumps(diff,indent=2))
