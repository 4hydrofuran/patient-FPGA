"""Independently reconcile real PC stdout, permit journal and commit receipts."""
import argparse
import hashlib
import json
import os
from pathlib import Path
from collections import deque

from native_cpu_build import OUT,read,sha
from native_request_journal import SCHEMA,DOMAIN,NativeRequestController
from request_journal_verified import FrozenProbe,canonical,digest,require,ZERO
from request_journal_audit import strict_json,is_sha
from offline_diag_handoff import directory,regular
from resource_probe_policy import ordinary_comparison

IDS=('app_R0','warm_prefix','app_hit')


def audit(worker_directory,build_receipt):
    fd=None
    base=dict(domain=DOMAIN,BOARD='NOT_TESTED',PL_calls=0,release_allowed=False,replay_allowed=False,
              hardware_completions=None,scope='PC_NATIVE_BYTES_AND_COUNTERS_NOT_HISTORICAL_FSYNC_OR_BOARD_RELEASE')
    try:
        build=read(build_receipt);frozen=FrozenProbe();known={r['id']:r for r in frozen.requests}
        fd=directory(Path(worker_directory));inventory=set(os.listdir(fd));pins={}
        allowed={'stdout.jsonl','stderr.txt','events.jsonl','NORMAL_CLOSE.json'}|{'COMMIT-'+i+'.json' for i in IDS}
        require(inventory<=allowed,'unlisted native transcript file')
        def load(name,limit):
            source=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=fd)
            try:
                pin=regular(os.fstat(source));require(0<pin[2]<=limit,'native transcript size bound')
                blocks=[];total=0
                while True:
                    block=os.read(source,min(65536,limit+1-total))
                    if not block:break
                    blocks.append(block);total+=len(block);require(total<=limit,'native transcript grew')
                require(total==pin[2] and regular(os.fstat(source))==pin and
                    regular(os.stat(name,dir_fd=fd,follow_symlinks=False))==pin,'native transcript changed')
                pins[name]=pin;return b''.join(blocks)
            finally:os.close(source)
        raw=load('stdout.jsonl',4*1024**2);require(raw.endswith(b'\n'),'torn stdout')
        messages=[]
        for line in raw.splitlines():
            require(len(line)<=262144,'oversize native stdout line');messages.append(strict_json(line))
        require(messages and messages[0].get('type')=='ready','missing native ready');ready=messages[0]
        require(ready.get('domain')=='PC' and ready.get('execution_kind')=='PC_MATH_DOUBLE' and
                'fixture_domain' not in ready,'not authentic PC mode')
        route=ready['bridge']['a12_route'];NativeRequestController._cpu_route(route)
        require(route['pc_verified_completions']==0 and route['pc_loads']==72,'invalid native ready counters')
        loaded=ready['prefix_cache']['identity']['verified_loaded_libraries']
        require(loaded['liba12_native_cpu_control.so']==build['library_sha256'] and
            loaded['libsp_linear_cpu.so']==build['existing_cpu_library_sha256'] and
            ready['prefix_cache']['identity']['executable_sha256']==build['existing_native_sha256'],
            'native program/library identity differs')
        binding=ready['prefix_cache']['binding_sha256'];ready_sha=digest(ready)
        work=Path(build['workspace']);identity=dict(adapter_sha256=build['library_sha256'],
            cpu_library_sha256=build['existing_cpu_library_sha256'],native_sha256=build['existing_native_sha256'],
            route_config_sha256=sha(work/'route-config.json'),prefix_config_sha256=sha(work/'native-prefix-config.json'))
        resident={k:route[k] for k in ('weight_load_count','weight_count','owned_weight_bytes',
            'workspace_capacity_bytes','partial_sums_capacity_bytes','partial_sums_capture_enabled')}
        terminals={};tokens={};order=[]
        for r in messages[1:]:
            name=r.get('id');require(name in IDS,'foreign native stdout request')
            if r.get('type')=='token':
                require(name not in terminals and r['index']==len(tokens.setdefault(name,[])),'token order differs')
                tokens[name].append(r['token']);require(len(tokens[name])<=8,'token bound exceeded')
            else:
                require(name not in terminals,'duplicate terminal');terminals[name]=r;order.append(name)
        require(order==list(IDS),'native request order/incomplete terminal')
        total=0;summaries={}
        for name in IDS:
            r=terminals[name];request=known[name]
            require(r.get('status')=='OK' and r.get('type')==('cache_created' if name=='warm_prefix' else 'result')
                and r.get('state_cleared_before_response') is True and r.get('state_position_after_clear')==-1
                and r['prefix_cache']['binding_sha256']==binding,'native terminal status/state differs')
            cpu=r['bridge']['a12_route'];NativeRequestController._cpu_route(cpu)
            require(r['bridge']['cpu_run_count']==0 and r['bridge']['weight_count']==0 and r['bridge']['error']=='',
                    'unselected CPU math fallback')
            require(digest({k:cpu[k] for k in resident})==digest(resident),'native residency differs')
            new={'app_R0':107,'warm_prefix':70,'app_hit':37}[name]
            if name=='warm_prefix':
                require(r['prefix_tokens']==70 and len(r['prefix_cache']['entries'])==1 and
                    r['prefix_cache']['entries'][0]['tokens']==70 and not tokens.get(name),'native warm mismatch')
                decode=0;content=None
            else:
                cache=r['prefix_cache_request'];hit=name=='app_hit';decode=r['decode_calls']
                require(cache['hit'] is hit and cache['new_tokens']==new and cache['reused_tokens']==(70 if hit else 0)
                    and r['eos'] is True and r['teacher_forced'] is False and r['gpu_layers']==0 and
                    r['prompt_tokens']==107 and r['output_tokens']==tokens[name],'native generation/cache mismatch')
                require(type(decode) is int and 0<=decode<=7,'native decode bound')
                content=frozen.check_answer(request,r)
            count=72*((new+7)//8+decode);total+=count
            require(cpu['pc_verified_completions']==total and cpu['pc_last_job']==cpu['job_id']==total
                and cpu['pc_output_consumable'] is True and cpu['last_status_code']==0,'actual CPU work differs')
            summaries[name]=dict(domain=DOMAIN,content=content,new_prefill_tokens=new,decode_calls=decode,
                actual_cpu_calls=count,cumulative_cpu_calls=total,hardware_completions=None,state_cleared=True,
                native_resident_sha256=digest(resident))
        ordinary_comparison(terminals['app_R0'],terminals['app_hit'])
        raw=load('events.jsonl',16*1024**2);require(raw.endswith(b'\n'),'torn native journal')
        lines=raw.splitlines();require(0<len(lines)<=6000,'native journal row bound')
        chain=ZERO;window=None;mode=None;pid=None;backend=0;router=0;weights=0;job=0;closed=False;normal=False
        active=None;completed=[];cumulative=0;strict_submits=0;request_hash=None
        for serial,line in enumerate(lines,1):
            require(len(line)<=32768,'native journal record bound');r=strict_json(line)
            require(r['schema']==SCHEMA and r['domain']==DOMAIN and r['record_serial']==serial and
                r['previous_record_sha256']==chain,'native journal identity/order differs')
            require(digest({k:v for k,v in r.items() if k not in ('monotonic_ns','record_sha256')})==r['record_sha256'],
                    'native journal semantic SHA mismatch')
            chain=r['record_sha256'];window=window or r['window_id'];mode=mode or r['journal_mode']
            require(r['window_id']==window and r['journal_mode']==mode and mode in ('strict','request') and not normal,
                    'mixed mode/window or row after exit')
            event=r['event']
            if event=='PERMISSION':
                q=r['request'];pid=pid or q['pid'];require(q['pid']==pid and r['allow'] is True,'foreign/denied permission')
                phase=q['phase'];lane='router' if phase.startswith('router_') else 'backend'
                require(q['sequence']==(router if lane=='router' else backend)+1,'native per-lane sequence differs')
                if lane=='router':router=q['sequence']
                else:backend=q['sequence']
                if phase=='router_open':require(router==1 and weights==0 and q['job']==0,'native router open differs')
                elif phase=='device_open':require(router==1 and backend==1 and q['job']==0,'native CPU open differs')
                elif phase=='weight_load':
                    require(weights<72 and q['job']==weights+1 and active is None,'native load order differs');weights+=1
                elif phase=='submit':
                    require(mode=='strict' and active is not None and q['job']==job+1,'strict native submit order differs')
                    job=q['job'];strict_submits+=1
                    request_hash.update(canonical(dict(sequence=q['sequence'],job=q['job'],pid=pid))+b'\n')
                elif phase=='router_close':
                    require(completed==list(IDS) and active is None and q['job']==0,'native close before complete')
                    closed=True
                else:raise ValueError('unexpected native phase')
            elif event=='REQUEST_BEGIN_PC_CANDIDATE':
                name=r['request_id'];require(active is None and len(completed)<3 and name==IDS[len(completed)] and
                    weights==72 and r['base_permits']==cumulative,'native BEGIN differs')
                meta=r['verified_request'];f=known[name];wire={k:v for k,v in f.items() if 'application' not in f or k not in ('application','tokens')}
                if name!='app_R0':wire['cache_binding_sha256']=binding
                require(meta==dict(request_sha256=digest(wire),frozen_request_sha256=digest(f),ready_sha256=ready_sha,
                    binding_sha256=binding,base_completions=cumulative,native_identity_sha256=digest(identity)) and
                    r['max_submits']=={'app_R0':1512,'warm_prefix':648,'app_hit':864}[name],'native BEGIN binding differs')
                active=r;request_hash=hashlib.sha256()
            elif event=='REQUEST_END_PC_CANDIDATE':
                require(active is not None and r['request_id']==active['request_id'],'orphan native END');name=r['request_id']
                summary=summaries[name];count=summary['actual_cpu_calls'];end=summary['cumulative_cpu_calls']
                expected_hash=hashlib.sha256();recent=deque(maxlen=64)
                for j in range(cumulative+1,end+1):
                    item=dict(sequence=j+73,job=j,pid=pid);recent.append(item);expected_hash.update(canonical(item)+b'\n')
                require(r['permit_count']==count and r['cumulative_permits']==r['native_cpu_verified_completions']==end
                    and r['pending']==0 and r['state_cleared'] is True and r['completion_domain']==DOMAIN and
                    r['permit_sha256']==expected_hash.hexdigest() and r['recent_submits']==list(recent) and
                    r['overwritten_submits']==max(0,count-64),'native END accounting differs')
                if mode=='strict':require(job==end and request_hash.hexdigest()==r['permit_sha256'],'strict native permit digest differs')
                else:job=end;backend=end+73
                meta=dict(active['verified_request'],result_sha256=digest(terminals[name]),validation_sha256=digest(summary))
                require(r['verified_request']==meta,'native END result/verification SHA differs')
                receipt=strict_json(load('COMMIT-'+name+'.json',8192))
                require(digest(receipt)==digest(dict(schema=SCHEMA,window_id=window,request_id=name,end_record_sha256=chain,
                    verified_request=meta,replay_allowed=False,release_allowed=False,scope='PC_FORMAT_RECEIPT_NOT_RELEASE_PROOF')),
                    'native commit receipt differs')
                cumulative=end;completed.append(name);active=None
            elif event=='WORKER_EXITED_NORMALLY':
                require(closed and completed==list(IDS) and r['exit_code']==0 and r['release_platform_lease'] is False,
                    'normal native exit lacks close');normal=True
            else:raise ValueError('native fault/incomplete event: '+str(event))
        require(normal and active is None and cumulative==total,'native journal incomplete')
        require((mode=='request' and len(lines)<=256 and len(raw)<=512*1024 and strict_submits==0) or
                (mode=='strict' and strict_submits==total),'native logging mode/cap differs')
        receipt=strict_json(load('NORMAL_CLOSE.json',8192))
        require(digest(receipt)==digest(dict(schema=SCHEMA,window_id=window,last_record_sha256=chain,exit_code=0,
            request_ids=list(IDS),cumulative_permits=total,release_allowed=False,replay_allowed=False)),
            'native close receipt differs')
        require(set(os.listdir(fd))==inventory,'native inventory changed')
        for name,pin in pins.items():require(regular(os.stat(name,dir_fd=fd,follow_symlinks=False))==pin,'native evidence changed after read')
        return dict(base,status='COMPLETE_ACTUAL_PC_NATIVE_TRANSCRIPT',journal_mode=mode,actual_cpu_calls=total,
                    journal_rows=len(lines),strict_submit_records=strict_submits,application_content='PASS_FROZEN_CHECKER')
    except BaseException as exc:
        return dict(base,status='REJECTED_OR_INCOMPLETE_RETAIN_OWNER',reason=(type(exc).__name__+': '+str(exc))[:360])
    finally:
        if fd is not None:os.close(fd)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('worker',type=Path);p.add_argument('--build',type=Path,default=OUT/'BUILD.json')
    p.add_argument('--report',required=True,type=Path);a=p.parse_args();r=audit(a.worker,a.build)
    with a.report.open('x',encoding='utf-8') as f:json.dump(r,f,indent=2);f.write('\n')
    print(json.dumps(r,indent=2));raise SystemExit(0 if r['status']=='COMPLETE_ACTUAL_PC_NATIVE_TRANSCRIPT' else 2)
