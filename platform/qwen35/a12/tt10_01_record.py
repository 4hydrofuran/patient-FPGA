"""Record exact local validation argv, exit status and output without shell parsing."""
import datetime,json,os,subprocess,sys,time
from tt10_01_common import ROOT,OUT,save


def main():
    name=sys.argv[1];argv=sys.argv[2:]
    assert name.replace('_','').isalnum() and argv
    dest=OUT/'logs'/(name+'.json');assert not dest.exists()
    begin=time.monotonic();started=datetime.datetime.now(datetime.timezone.utc).isoformat()
    env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1')
    p=subprocess.run(argv,cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    save(dest,dict(argv=argv,cwd=str(ROOT),started_utc=started,elapsed_s=time.monotonic()-begin,
        exit_code=p.returncode,stdout=p.stdout.decode('utf-8',errors='replace'),stderr=p.stderr.decode('utf-8',errors='replace')))
    print(json.dumps(dict(log=str(dest),exit_code=p.returncode,stdout=p.stdout.decode('utf-8',errors='replace')[-2500:],stderr=p.stderr.decode('utf-8',errors='replace')[-2500:])))
    return p.returncode


if __name__=='__main__':raise SystemExit(main())
