import json,subprocess
from pathlib import Path
rows=[]
for args in (['scripts/release/check_contracts.py'],['scripts/release/qwen35_config.py'],['-m','unittest','discover','-s','bench/qwen35/web','-v']):
    argv=['wsl','-d','KV260-A-2204','--cd','/mnt/c/Patientqwen','python3']+args
    p=subprocess.run(argv,capture_output=True,text=True,encoding='utf-8',errors='replace')
    rows.append(dict(argv=argv,exit=p.returncode,stdout=p.stdout,stderr=p.stderr))
Path(__file__).with_name('PC_CHECKS.json').write_text(json.dumps(rows,indent=2))
print(json.dumps([dict(command=r['argv'][6:],exit=r['exit']) for r in rows]))
assert all(r['exit']==0 for r in rows)
