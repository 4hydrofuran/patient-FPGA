import hashlib,io,json,os,signal,subprocess,time,urllib.request,zipfile
from pathlib import Path
root=Path('/var/lib/kv260-a12/manual-web-20261026-v4')
b=urllib.request.urlopen('http://192.168.2.1:8766/collect.py',timeout=20).read(20_000_000)
assert hashlib.sha256(b).hexdigest()=='21e1d4bfc21d83657f4432ad762c30c35454773922730ea3eaea9a9b8b48e7fa'
with zipfile.ZipFile(io.BytesIO(b)) as z:z.extractall('/var/cache/apt/archives')
old=Path('/var/lib/kv260-a12/manual-web-20261026-v3/install-ime.py')
for p in Path('/proc').iterdir():
    if not p.name.isdigit():continue
    try:
        if (p/'cmdline').read_bytes().split(b'\0')[:-1]!=[b'/usr/bin/python3',b'-B',b'-I',str(old).encode()]:continue
        for pid in (p/'task'/p.name/'children').read_text().split():
            child=Path('/proc')/pid
            if (child/'cmdline').read_bytes().split(b'\0')[:-1]==[b'apt-get',b'install',b'-y',b'--no-install-recommends',b'ibus-libpinyin']:
                os.kill(int(pid),signal.SIGINT)
                for _ in range(100):
                    if not child.exists():break
                    time.sleep(.1)
                assert not child.exists()
    except FileNotFoundError:pass
script=root/'install-ime.py'
script.write_text("import json,os,subprocess\nfrom pathlib import Path\nr=Path("+repr(str(root))+")\nwith (r/'ime-install.log').open('x') as f:\n p=subprocess.run(['apt-get','install','-y','--no-install-recommends','--no-download','ibus-libpinyin'],env=dict(os.environ,DEBIAN_FRONTEND='noninteractive'),stdout=f,stderr=subprocess.STDOUT)\n(r/'ime-install-result.json').write_text(json.dumps(dict(exit=p.returncode)))\n")
p=subprocess.Popen(['/usr/bin/python3','-B','-I',str(script)],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
print('__PL_BEGIN__');print(json.dumps(dict(status='CACHED_PINYIN_INSTALL_STARTED',pid=p.pid)));print('__PL_END__')
