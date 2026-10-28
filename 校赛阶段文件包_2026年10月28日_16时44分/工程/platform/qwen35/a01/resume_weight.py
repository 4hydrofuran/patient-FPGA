"""Recover interrupted public weight using validated HTTP range; preserve original partial."""
import json
import shutil
import urllib.request
from fetch import DEST, REV, digest

name="model.safetensors-00001-of-00001.safetensors"
api=json.loads((DEST/"upstream_api.json").read_text())
item=next(x for x in api["siblings"] if x["rfilename"]==name)
partial=DEST/(name+".partial");start=partial.stat().st_size;total=item["size"]
url=f"https://huggingface.co/Qwen/Qwen3.5-0.8B/resolve/{REV}/{name}?a01_range={start}"
req=urllib.request.Request(url,headers={"Range":f"bytes={start}-{total-1}","User-Agent":"KV260-A01-public-audit"})
tail=DEST/(name+".tail")
with urllib.request.urlopen(req,timeout=120) as r:
    if r.status!=206 or r.headers.get("Content-Range")!=f"bytes {start}-{total-1}/{total}":
        raise ValueError("Server did not honor exact range")
    with tail.open("xb") as f:
        shutil.copyfileobj(r,f,1024*1024)
assert tail.stat().st_size==total-start
recovered=DEST/(name+".recovered")
with recovered.open("xb") as out:
    for p in [partial,tail]:
        with p.open("rb") as src:shutil.copyfileobj(src,out,1024*1024)
assert recovered.stat().st_size==total
actual=digest(recovered);assert actual==item["lfs"]["sha256"]
recovered.rename(DEST/name)
print(json.dumps({"resumed_from":start,"bytes":total,"sha256":actual,"partial_preserved":True,"status":"PASS"}))
