import hashlib,json
from pathlib import Path
root=Path('/var/lib/kv260-a12/manual-web-20261026-v1')
assert not Path('/var/lock/kv260-a1/active').exists()
assert not (root/'bundle/run-v1').exists()
p=root/'interactive_entry.py';source=p.read_text()
anchor='from board_entry import prepared_main'
assert source.count(anchor)==1 and 'sys.path.insert(0,str(Path(__file__).resolve().parent))' not in source
old=hashlib.sha256(p.read_bytes()).hexdigest()
p.rename(root/'interactive_entry.attempt1.py')
source=source.replace(anchor,'sys.path.insert(0,str(Path(__file__).resolve().parent))\n'+anchor)
compile(source,str(p),'exec');p.write_text(source)
history=root/'setup-failure-01';history.mkdir()
for name in ('started.json','manager.stdout','manager.stderr'):(root/name).rename(history/name)
print('__PL_BEGIN__');print(json.dumps({'status':'ISOLATED_IMPORT_PATH_FIXED_BEFORE_OWNER','old_sha':old,'new_sha':hashlib.sha256(p.read_bytes()).hexdigest()}));print('__PL_END__')
