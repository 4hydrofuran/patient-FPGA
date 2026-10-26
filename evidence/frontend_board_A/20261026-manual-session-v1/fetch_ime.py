import concurrent.futures,hashlib,json,re,urllib.request,zipfile
from pathlib import Path
out=Path(__file__).parent
raw=json.loads((out/'ime-uris-uart.json').read_text(encoding='utf-8-sig'))['output']
data=json.loads(raw.rsplit('__PL_BEGIN__',1)[1].split('__PL_END__')[0])
rows=re.findall(r"'(http[^']+)' (\S+) (\d+) MD5Sum:([0-9a-f]+)",data['stdout'])
folder=out/'ime-packages';folder.mkdir(exist_ok=True)
def fetch(row):
    url,name,size,md5=row
    request=urllib.request.Request(url.replace('http:','https:',1))
    with urllib.request.urlopen(request,timeout=25) as f:b=f.read()
    assert len(b)==int(size) and hashlib.md5(b).hexdigest()==md5
    (folder/name).write_bytes(b)
    return dict(name=name,bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:results=list(pool.map(fetch,rows))
(out/'ime-packages.json').write_text(json.dumps(results,indent=2))
with zipfile.ZipFile(out/'ime-packages.zip','x',zipfile.ZIP_STORED) as z:
    for row in results:z.write(folder/row['name'],row['name'])
print(json.dumps(dict(downloaded=len(results),bytes=sum(r['bytes'] for r in results))))
