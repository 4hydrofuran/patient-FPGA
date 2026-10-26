import json,subprocess
p=subprocess.run(['apt-get','--print-uris','-y','--no-install-recommends','install','ibus-libpinyin'],capture_output=True,text=True,timeout=10)
print('__PL_BEGIN__');print(json.dumps(dict(exit=p.returncode,stdout=p.stdout,stderr=p.stderr)));print('__PL_END__')
