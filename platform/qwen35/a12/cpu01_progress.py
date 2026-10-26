"""Read local transport progress, redacting the large readback payload from output."""
import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
import tarfile

OUT=Path(__file__).resolve().parents[3]/'evidence/model_pl_A/20261024-cpu-opt-01-integrated-v1'


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--save-old',action='store_true');args=parser.parse_args()
    rows=[]
    for line in (OUT/'board_01/stdout.txt').open(encoding='utf-8'):
        if not line.endswith('\n'):continue
        event=json.loads(line)
        if event['event']=='READBACK' and event['mode']=='old' and args.save_old:
            raw=base64.b64decode(event['base64'],validate=True)
            assert len(raw)==event['bytes'] and hashlib.sha256(raw).hexdigest()==event['sha256']
            with tarfile.open(fileobj=io.BytesIO(raw),mode='r:gz') as tar:
                def read(name):return json.loads(tar.extractfile(name).read())
                summary=dict(manager=read('manager-exit.json'),rows=[])
                for side in ('s1','s2'):
                    for name in ('diag_exact','short_plain','short_profile','natural_plain','natural_profile'):
                        result=read('run-v1/'+side+'/'+name+'/result.json');clock=read('run-v1/'+side+'/'+name+'/client-timing.json')
                        summary['rows'].append(dict(side=side,id=name,status=result['status'],complete_s=clock['result_wall_ms']/1000,first_token_s=clock['first_token_wall_ms']/1000))
                summary['old_S1_S2_numerical_gate']=read('run-v1/s2/diag_exact/numerical-gate.json')
                summary['independent_postcheck']=read('independent-postcheck.json')
                summary['delayed_postcheck']=read('delayed-postcheck.json')
            with (OUT/'OLD_WINDOW_SUMMARY.json').open('x',encoding='utf-8') as stream:json.dump(summary,stream,indent=2);stream.write('\n')
        rows.append({k:v for k,v in event.items() if k!='base64'})
    print(json.dumps(rows[-4:]))
