import subprocess,json
code="import json,os; from pathlib import Path; r=[]; names=['/lib/firmware/a11-mlp.bit.bin','/lib/firmware/a11-mlp.dtbo']; [(r.append(dict(path=n,lexists=os.path.lexists(n),exists=Path(n).exists(),symlink=Path(n).is_symlink(),link=os.readlink(n) if Path(n).is_symlink() else None))) for n in names]; print(json.dumps(r))"
r=subprocess.run(['sudo','-n','python3','-B','-I','-c',code],capture_output=True,text=True,timeout=10)
print('__A12_UPLOAD_BEGIN__',flush=True);print(json.dumps(dict(exit_code=r.returncode,stdout=r.stdout,stderr=r.stderr)),flush=True);print('__A12_UPLOAD_END__',flush=True)
