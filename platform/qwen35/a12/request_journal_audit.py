"""Read-only PC transcript audit. Never grants replay, cleanup or release."""
import argparse
import json
import os
from pathlib import Path
import re

from offline_diag_handoff import directory, regular
from request_journal_verified import (SCHEMA, MAX_LOG, MAX_RECORD, MAX_RECORDS, ZERO,
                                      FrozenProbe, digest, require)

IDS=('app_R0','warm_prefix','app_hit')


def strict_json(raw):
    def pairs(items):
        out={}
        for key,value in items:
            require(key not in out,'duplicate JSON field');out[key]=value
        return out
    def bad(value):raise ValueError('nonfinite JSON: '+value)
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=bad)


def is_sha(value):return type(value) is str and re.fullmatch('[0-9a-f]{64}',value) is not None


def audit(folder):
    fd=None
    base=dict(domain='PC_TRANSCRIPT_FORMAT_ONLY_NOT_HARDWARE',BOARD='NOT_TESTED',
              replay_allowed=False,release_allowed=False,hardware_completions=None)
    try:
        fd=directory(Path(folder));inventory=set(os.listdir(fd))
        read_pins={}
        allowed={'events.jsonl','stderr.txt','stdout.jsonl','NORMAL_CLOSE.json'}|{'COMMIT-'+i+'.json' for i in IDS}
        require(inventory<=allowed and 'events.jsonl' in inventory,'unknown/missing transcript file')
        def read(name,maximum):
            rawfd=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=fd)
            try:
                before=regular(os.fstat(rawfd));require(0<before[2]<=maximum,'transcript size outside bound')
                pieces=[];total=0
                while True:
                    block=os.read(rawfd,min(65536,maximum+1-total))
                    if not block:break
                    total+=len(block);require(total<=maximum,'transcript grew');pieces.append(block)
                require(regular(os.fstat(rawfd))==before and
                    regular(os.stat(name,dir_fd=fd,follow_symlinks=False))==before and total==before[2],
                    'transcript changed while reading')
                read_pins[name]=before
                return b''.join(pieces)
            finally:os.close(rawfd)
        raw=read('events.jsonl',MAX_LOG)
        require(raw.endswith(b'\n'),'torn final journal row')
        lines=raw.splitlines();require(0<len(lines)<=MAX_RECORDS,'journal row bound')
        frozen=FrozenProbe();known={r['id']:r for r in frozen.requests}
        chain=ZERO;window=None;active=None;completed=[];total=0;normal=False;ready_sha=None;binding=None
        phase='new';weights=0;last_backend=0;last_router=0
        for serial,line in enumerate(lines,1):
            require(0<len(line)<=MAX_RECORD,'journal row too large');row=strict_json(line)
            require(type(row) is dict and row.get('schema')==SCHEMA and row.get('domain')=='PC_CONTROL_FIXTURE_NOT_HARDWARE',
                    'unknown journal schema/domain')
            require(type(row.get('record_serial')) is int and row['record_serial']==serial and
                    row.get('previous_record_sha256')==chain,'journal chain/order differs')
            require(type(row.get('monotonic_ns')) is int and row['monotonic_ns']>0,'missing monotonic stamp')
            body={k:v for k,v in row.items() if k not in ('monotonic_ns','record_sha256')}
            require(is_sha(row.get('record_sha256')) and digest(body)==row['record_sha256'],'journal row digest differs')
            require(type(row.get('window_id')) is str and re.fullmatch('[0-9a-f]{32}',row['window_id']), 'invalid window ID')
            window=window or row['window_id'];require(row['window_id']==window,'mixed windows')
            chain=row['record_sha256'];event=row.get('event')
            require(not normal,'row after normal exit')
            if event=='PERMISSION':
                request=row['request'];p=request['phase'];seq=request['sequence']
                require(row['allow'] is True and type(seq) is int,'denied/invalid permission record')
                if p=='router_open':
                    require(phase=='new' and seq==1 and request['job']==0,'bad router startup')
                    phase='router';last_router=1
                elif p=='device_open':
                    require(phase=='router' and seq==1 and request['job']==0,'bad device startup')
                    phase='weights';last_backend=1
                elif p=='weight_load':
                    require(phase=='weights' and weights<72 and seq==last_backend+1 and request['job']==weights+1,
                            'bad weight order')
                    weights+=1;last_backend=seq
                elif p=='router_close':
                    require(active is None and completed==list(IDS) and seq==last_router+1 and request['job']==0,
                            'close before complete window')
                    phase='closed';last_router=seq
                else:raise ValueError('unexpected durable per-submit/unknown permit')
            elif event=='REQUEST_BEGIN_PC_CANDIDATE':
                require(phase=='weights' and weights==72 and active is None and len(completed)<3 and
                    row['request_id']==IDS[len(completed)] and type(row['base_permits']) is int and row['base_permits']==total and
                    type(row['max_submits']) is int and 1<=row['max_submits']<=5000 and
                    row.get('production_default') is False,'invalid request BEGIN')
                meta=row['verified_request']
                require(all(is_sha(meta.get(k)) for k in ('request_sha256','frozen_request_sha256','ready_sha256','binding_sha256'))
                    and type(meta.get('base_completions')) is int and meta['base_completions']==total,'invalid request identity')
                ready_sha=ready_sha or meta['ready_sha256'];binding=binding or meta['binding_sha256']
                request=known[row['request_id']];wire={k:v for k,v in request.items() if k not in ('tokens','application')}
                if wire['op']=='cache_create' or wire['cache_policy']!='R0':wire['cache_binding_sha256']=binding
                require(meta['ready_sha256']==ready_sha and meta['binding_sha256']==binding and
                    meta['frozen_request_sha256']==digest(request) and meta['request_sha256']==digest(wire) and
                    row['max_submits']=={'app_R0':1512,'warm_prefix':648,'app_hit':864}[row['request_id']],
                    'BEGIN does not bind frozen workload/budget/ready')
                active=row
            elif event=='REQUEST_END_PC_CANDIDATE':
                require(active is not None and row['request_id']==active['request_id'],'orphan/stale END')
                count=row['permit_count'];require(type(count) is int and 1<=count<=active['max_submits'],'END budget differs')
                total+=count
                require(type(row['cumulative_permits']) is int and row['cumulative_permits']==total<=5000 and
                    type(row['caller_asserted_cumulative_completions']) is int and
                    row['caller_asserted_cumulative_completions']==total and type(row['pending']) is int and
                    row['pending']==0 and row['state_cleared'] is True and is_sha(row['permit_sha256']), 'END accounting differs')
                meta=row['verified_request']
                require(all(meta.get(k)==v for k,v in active['verified_request'].items()) and
                    is_sha(meta.get('result_sha256')) and is_sha(meta.get('validation_sha256')),'END identity differs')
                ring=row['recent_submits'];require(type(ring) is list and len(ring)==min(count,64) and
                    row['overwritten_submits']==max(0,count-64),'ring not bounded/accounted')
                for offset,item in enumerate(ring,total-len(ring)+1):
                    require(type(item['job']) is int and item['job']==offset and item['sequence']==offset+73,
                            'recent submit sequence differs')
                name='COMMIT-'+row['request_id']+'.json'
                if name not in inventory:
                    return dict(base,status='INCOMPLETE_UNKNOWN_RETAIN_OWNER',reason='END has no commit receipt',
                                completed_request_ids=completed,uncommitted_request_id=row['request_id'])
                receipt=strict_json(read(name,8192))
                require(digest(receipt)==digest(dict(schema=SCHEMA,window_id=window,request_id=row['request_id'],
                    end_record_sha256=chain,verified_request=meta,replay_allowed=False,release_allowed=False,
                    scope='PC_FORMAT_RECEIPT_NOT_RELEASE_PROOF')),'commit receipt does not bind exact END/result')
                completed.append(row['request_id']);active=None
            elif event=='WORKER_EXITED_NORMALLY':
                require(phase=='closed' and active is None and completed==list(IDS) and row['exit_code']==0
                    and row['release_platform_lease'] is False,'normal exit not proven')
                normal=True
            else:raise ValueError('fault/unknown event requires retained owner: '+str(event))
        if active is not None or not normal or completed!=list(IDS) or 'NORMAL_CLOSE.json' not in inventory:
            return dict(base,status='INCOMPLETE_UNKNOWN_RETAIN_OWNER',reason='missing END or complete normal close',
                        completed_request_ids=completed,active_request_id=active['request_id'] if active else None)
        close=strict_json(read('NORMAL_CLOSE.json',8192))
        require(digest(close)==digest(dict(schema=SCHEMA,window_id=window,last_record_sha256=chain,exit_code=0,
            request_ids=list(IDS),cumulative_permits=total,release_allowed=False,replay_allowed=False)),
            'normal close receipt differs')
        require(inventory==set(os.listdir(fd)),'transcript inventory changed')
        for name,pin in read_pins.items():
            require(regular(os.stat(name,dir_fd=fd,follow_symlinks=False))==pin,
                    'previously read transcript changed before audit completion')
        return dict(base,status='COMPLETE_PC_TRANSCRIPT_REQUIRES_INDEPENDENT_RELEASE',
                    completed_request_ids=completed,simulated_submit_permits=total,rows=len(lines),
                    scope='HASH_AND_STRUCTURE_ONLY_NO_FSYNC_OR_HARDWARE_RELEASE_PROOF')
    except BaseException as exc:
        return dict(base,status='REJECTED_OR_TORN_RETAIN_OWNER',reason=(type(exc).__name__+': '+str(exc))[:360])
    finally:
        if fd is not None:os.close(fd)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('folder',type=Path)
    p.add_argument('--report',required=True,type=Path);args=p.parse_args();result=audit(args.folder)
    with args.report.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps(result,indent=2))
    return 0 if result['status'].startswith('COMPLETE_PC_') else 2


if __name__=='__main__':raise SystemExit(main())
