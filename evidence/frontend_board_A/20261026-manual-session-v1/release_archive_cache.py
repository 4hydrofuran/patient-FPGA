import json,os,time
from pathlib import Path
def memory():return {s.split(':')[0]:int(s.split()[1]) for s in Path('/proc/meminfo').read_text().splitlines() if s.startswith(('MemAvailable:','CmaFree:'))}
r={'before':memory(),'files':[],'model_pages_touched':False,'files_deleted':False}
paths=list(Path('/home/ubuntu').glob('a12-*.tar*'))
paths += [Path('/var/lib/kv260-a12/pl-authfix-20261026-v2/bundle-fixed.zip'),Path('/var/lib/kv260-a12/web-20261026-v1/receipt.zip')]
for p in paths:
    if p.is_symlink() or not p.is_file():continue
    before=p.stat();fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        os.fsync(fd);os.posix_fadvise(fd,0,0,os.POSIX_FADV_DONTNEED)
    finally:os.close(fd)
    after=p.stat();assert (before.st_ino,before.st_size,before.st_mtime_ns)==(after.st_ino,after.st_size,after.st_mtime_ns)
    r['files'].append({'path':str(p),'bytes':before.st_size})
time.sleep(1);r['after']=memory()
print('__PL_BEGIN__');print(json.dumps(r));print('__PL_END__')
