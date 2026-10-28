"""Local-only progress; read verified restored-window records without raw payload output."""
import base64
import hashlib
import io
import json
from pathlib import Path
import tarfile
from tt10_00_prepare import OUT,save


def main():
    tail=[];summaries=[]
    log=OUT/('board_02' if (OUT/'board_02/stdout.txt').exists() else 'board_01')/'stdout.txt'
    for line in log.open(encoding='utf-8'):
        if not line.endswith('\n'):continue
        e=json.loads(line);tail.append({k:v for k,v in e.items() if k!='base64'})
        if e['event']!='READBACK':continue
        raw=base64.b64decode(e['base64'],validate=True)
        assert len(raw)==e['bytes'] and hashlib.sha256(raw).hexdigest()==e['sha256']
        with tarfile.open(fileobj=io.BytesIO(raw),mode='r:gz') as t:
            def read(name):return json.loads(t.extractfile(name).read())
            if not any(m.name=='independent-postcheck.json' for m in t.getmembers()):continue
            assert read('manager-exit.json')['exit_code']==0
            summary=dict(mode=e['mode'],manager_exit=0,restored_postcheck=read('delayed-postcheck.json')['scans'][-1]['no_users_gate'],rows=[])
            for side in ('s1','s2'):
                for name in ('app_plain_1','app_plain_2','app_profile'):
                    clock=read('run-v1/'+side+'/'+name+'/application-timing.json')
                    summary['rows'].append(dict(side=side,id=name,app_TTFT_s=clock['TTFT_app_ms']/1000,complete_s=clock['complete_app_ms']/1000))
        target=OUT/('PROGRESS_'+e['mode']+'.json')
        if not target.exists():save(target,summary)
        summaries.append(summary)
    print(json.dumps(dict(tail=tail[-2:],restored_windows=summaries)))

if __name__=='__main__':main()
