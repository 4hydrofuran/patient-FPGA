"""Bounded diagnostic reproduction of initial worker timeout; no unrelated process kill."""
import json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'evidence/c02/worker_timeout_probe'
out.mkdir(parents=True,exist_ok=True)
with (out/'stdout.jsonl').open('w',encoding='utf-8') as stdout,(out/'stderr.log').open('w',encoding='utf-8') as stderr:
    command=[sys.executable,'-c',"import faulthandler,runpy; faulthandler.dump_traceback_later(8,repeat=True); runpy.run_module('voicec.worker',run_name='__main__')",
        '--spool',str(out/'spool'),'--tts-config',str(ROOT/'configs/tts.threads1.batch1.json')]
    process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=stdout,stderr=stderr,text=True,encoding='utf-8',env=os.environ|{'PYTHONUTF8':'1'})
    try:
        process.stdin.write(json.dumps(dict(api_version=1,request_id='probe',op='synthesize',session_id='s',output_dir='s/out',text='我没有发热，也没有咳嗽。'),ensure_ascii=False)+'\n')
        process.stdin.flush()
        time.sleep(15)
        process.stdin.write(json.dumps(dict(api_version=1,request_id='shutdown',op='shutdown'))+'\n')
        process.stdin.flush();process.stdin.close()
        try: process.wait(timeout=10)
        except subprocess.TimeoutExpired: process.terminate();process.wait(timeout=5)
        print('Own probe process exit:',process.returncode)
    finally:
        if process.poll() is None: process.terminate();process.wait(timeout=5)
