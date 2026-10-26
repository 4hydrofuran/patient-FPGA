import json,os,subprocess
from pathlib import Path
root=Path('/var/lib/kv260-a12/manual-web-20261026-v3')
script=root/'install-ime.py'
script.write_text("import json,os,subprocess\nfrom pathlib import Path\nr=Path("+repr(str(root))+")\nwith (r/'ime-install.log').open('x') as f:\n p=subprocess.run(['apt-get','install','-y','--no-install-recommends','ibus-libpinyin'],env=dict(os.environ,DEBIAN_FRONTEND='noninteractive'),stdout=f,stderr=subprocess.STDOUT)\n(r/'ime-install-result.json').write_text(json.dumps(dict(exit=p.returncode)))\n")
p=subprocess.Popen(['/usr/bin/python3','-B','-I',str(script)],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
print('__PL_BEGIN__');print(json.dumps(dict(status='PINYIN_INSTALL_STARTED',pid=p.pid)));print('__PL_END__')
