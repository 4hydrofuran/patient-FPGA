import json,subprocess
commands=[]
for argv in (['dpkg-query','-W','-f=${Package} ${Status}\n','ibus','ibus-libpinyin','maliit-keyboard'],['apt-cache','depends','ibus-libpinyin']):
    p=subprocess.run(argv,capture_output=True,text=True,timeout=8);commands.append(dict(argv=argv,exit=p.returncode,stdout=p.stdout,stderr=p.stderr))
print('__PL_BEGIN__');print(json.dumps(commands));print('__PL_END__')
