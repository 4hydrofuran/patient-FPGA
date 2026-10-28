"""Sequential fresh services and actual Windows Edge timings; no answer cache loaded."""
import argparse
from datetime import datetime,timezone,timedelta
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[3]
VENV='/home/member-a/kv260-build/a12-fast-response-20261027-venv/bin/python'
REC='bench/qwen35/web/run_recorded.py'


def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def stamp():return datetime.now(timezone(timedelta(hours=8))).isoformat()


def run(a):
    evidence=a.output.resolve();evidence.mkdir(parents=True,exist_ok=True)
    baseline=ROOT/'release/a12_realtime_model_draft_20261027_v1/realtime34-threads3-out32'
    windows=([('baseline',baseline)] if a.baseline else [])+[(f'candidate{i:02d}',a.parent.resolve()) for i in range(1,a.windows+1)]
    rows=[]
    for index,(label,parent) in enumerate(windows):
        out=evidence/(label+'-serve');browser=evidence/(label+'-browser');port=a.port+index
        rel=lambda p:p.resolve().relative_to(ROOT).as_posix()
        # The baseline also uses current host telemetry; its original single-prefix profile is unchanged.
        script=(ROOT/'platform/qwen35/web/answer_cache_serve_pc.py') if label=='baseline' else parent/'continuous/answer_cache_serve_pc.py'
        serve=['wsl','-d','KV260-A-2204','--cd','/mnt/c/Patientqwen','--',VENV,'-B',REC,
               '--output',rel(evidence/(label+'-serve-command')),'--',VENV,'-B',rel(script),
               '--mode','realtime','--parent',rel(parent),'--output',rel(out),'--port',str(port),'--compact']
        begin=stamp()
        with (evidence/(label+'-launcher.txt')).open('xb') as log:
            process=subprocess.Popen(serve,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
            try:
                deadline=time.monotonic()+150
                while not (out/'HTTP_READY.json').is_file():
                    if process.poll() is not None:raise RuntimeError(label+' service exited before ready')
                    if time.monotonic()>deadline:raise TimeoutError(label+' service startup')
                    time.sleep(.25)
                command=[sys.executable,REC,'--output',str(evidence/(label+'-browser-command')),'--',sys.executable,
                    str(parent/'continuous/answer_cache_browser.py'),'--mode','realtime','--cohort',str(parent/'COHORT.json'),
                    '--url',f'http://127.0.0.1:{port}/','--output',str(browser)]
                subprocess.run(command,cwd=ROOT,check=True)
            finally:
                if out.is_dir():save(out/'stop-request.json',dict(requested_at=stamp(),reason='completed actual browser window'))
                process.wait(timeout=210)
            if process.returncode:raise RuntimeError(label+' service failed normal close')
        result=json.loads((browser/'RESULT.json').read_text(encoding='utf-8'))
        times=[r['timing']['submit_to_paint_ms'] for r in result['rows']]
        receipt=json.loads((out/'RESULT.json').read_text(encoding='utf-8'))
        assert receipt['native_count']==25 and receipt['cache'] is None and receipt['worker_exit']==0
        row=dict(window=label,start=begin,end=stamp(),questions=len(times),under_1000=sum(t<1000 for t in times),
                 min_ms=min(times),median_ms=sorted(times)[len(times)//2],max_ms=max(times),actual_model_calls=receipt['native_count'])
        rows.append(row);save(evidence/'WINDOW_PROGRESS.json',rows);print(json.dumps(row),flush=True)
    save(evidence/'WINDOWS.json',dict(status='PASS_ACTUAL_BROWSER_WINDOWS',rows=rows,BOARD='NOT_TESTED'))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--parent',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--windows',type=int,default=3)
    p.add_argument('--baseline',action='store_true');p.add_argument('--port',type=int,default=18860)
    run(p.parse_args())
