"""Extract exact preserved driver readback into a fresh local directory."""
import base64,hashlib,io,json,tarfile
from pathlib import Path
from tt10_01_common import OUT,save
def main():
    e=OUT/'window-20261025-v2/execution-01';events=[]
    with (e/'board-01/stdout.txt').open(encoding='utf-8') as f:
        for line in f:
            x=json.loads(line)
            if x.get('event')=='READBACK':events.append(x)
    assert len(events)==1 and events[0]['mode']=='prefix'
    x=events[0];raw=base64.b64decode(x['base64'],validate=True)
    assert len(raw)==x['bytes'] and hashlib.sha256(raw).hexdigest()==x['sha256']
    dest=e/'readback-01';dest.mkdir(exist_ok=False)
    with (e/'readback-01.tar.gz').open('xb') as f:f.write(raw)
    files={}
    with tarfile.open(fileobj=io.BytesIO(raw),mode='r:gz') as archive:
        members=archive.getmembers();assert len(members)<=10000 and sum(m.size for m in members)<=2147483648
        for m in members:
            assert not m.issym() and not m.islnk() and (m.isdir() or m.isfile())
            assert '\\' not in m.name and ':' not in m.name
            p=(dest/m.name).resolve();assert p.is_relative_to(dest.resolve())
        for m in members:
            p=dest/m.name
            if m.isdir():p.mkdir(parents=True,exist_ok=True);continue
            p.parent.mkdir(parents=True,exist_ok=True);h=hashlib.sha256();count=0
            with archive.extractfile(m) as source,p.open('xb') as target:
                for block in iter(lambda:source.read(1048576),b''):target.write(block);h.update(block);count+=len(block)
            assert count==m.size
            files[m.name]=dict(bytes=count,sha256=h.hexdigest())
    save(e/'READBACK_FILES.json',dict(archive_sha256=x['sha256'],archive_bytes=len(raw),files=files))
    print(json.dumps(dict(status='EXACT_READBACK_SAVED_NO_RESULT_PROMOTION',files=len(files),archive_sha256=x['sha256'])))
if __name__=='__main__':main()
