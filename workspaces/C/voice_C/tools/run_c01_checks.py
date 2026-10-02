"""Run C01 checks sequentially; do not overwrite C00 evidence or prior C01 runs."""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run-id',default='final')
    args=p.parse_args()
    if not args.run_id.replace('-','').isalnum(): raise ValueError('Invalid run ID')
    out=ROOT/'evidence/c01'/args.run_id
    out.mkdir(parents=True,exist_ok=False)
    tasks=[('unittest',[sys.executable,'-m','unittest','discover','-s','tests','-v'],120),
        ('comparison',[sys.executable,'tools/compare_c01_threads.py'],300),
        ('edge_inputs',[sys.executable,'tools/collect_c01_edges.py'],60)]
    records=[]
    for name,command,timeout in tasks:
        print('Running',name,flush=True)
        start=datetime.now(timezone.utc).isoformat()
        with (out/(name+'.log')).open('w',encoding='utf-8') as log:
            process=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,
                encoding='utf-8',timeout=timeout,env=os.environ|{'PYTHONUTF8':'1','PYTHONDONTWRITEBYTECODE':'1'})
        records.append(dict(name=name,argv=command,cwd=str(ROOT),started_at_utc=start,
            finished_at_utc=datetime.now(timezone.utc).isoformat(),exit_code=process.returncode,
            log=str((out/(name+'.log')).relative_to(ROOT))))
        (out/'commands.json').write_text(json.dumps(records,indent=2)+'\n',encoding='utf-8')
        print(name,'exit:',process.returncode,flush=True)
        if process.returncode: raise SystemExit(process.returncode)


if __name__=='__main__': main()
