import json,subprocess
r={}
for args in (['ip','-j','address'],['ip','-j','route']):
    p=subprocess.run(args,capture_output=True,text=True,timeout=5);r[' '.join(args)]=json.loads(p.stdout)
print('__PL_BEGIN__');print(json.dumps(r));print('__PL_END__')
