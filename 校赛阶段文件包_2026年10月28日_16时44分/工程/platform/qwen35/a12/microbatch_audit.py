"""Independent range-journal reconciliation, reusing frozen native-only checks."""
import ast
from collections import deque
import hashlib
import os
from pathlib import Path
import types

import native_request_audit as old
from microbatch_evidence import ROOT,read,sha
from request_journal_verified import canonical,digest,require,ZERO
from request_journal_audit import strict_json
from offline_diag_handoff import regular

SCHEMA='PC_NATIVE_MICROBATCH_JOURNAL_V1'
SEMANTICS='MANAGER_RESERVED_JOB_RANGES_NOT_PER_PROJECTION_IPC_OR_HARDWARE'
IDS=('app_R0','warm_prefix','app_hit')


class NativeOnlyChecker:
    @staticmethod
    def _cpu_route(route):
        require(route['pc_adapter']=='A12_NATIVE_CPU_MICROBATCH_V1','wrong native batch adapter')
        b=route['pc_batch'];require(b['schema'] in ('PC_MICROBATCH_LOCAL_BUDGET_V1','PC_MICROBATCH_LOCAL_BUDGET_V2','PC_MICROBATCH_LOCAL_BUDGET_V3') and
            b['revoked'] is False and b['hardware_completions'] is None and
            b['local_claims']==b['shared_claims']==route['pc_started_calls'],'native batch claim counters differ')
        if b['schema']=='PC_MICROBATCH_LOCAL_BUDGET_V3':require(b['inflight_or_unknown'] is False,'native CPU in-flight/unknown')
        old.NativeRequestController._cpu_route(dict(route,pc_adapter='A12_NATIVE_CPU_CONTROL_V1'))


def journal(c):
    load=c['load'];fd=c['fd'];ready=c['ready'];known=c['known'];build=c['build'];terminals=c['terminals']
    batch=ready['bridge']['a12_route']['pc_batch'];config=read(Path(build['workspace'])/'adapter-config.json')
    require(batch['context_sha256']==config['context_sha256'] and batch['schema']==
        ('PC_MICROBATCH_LOCAL_BUDGET_V3' if build['revision']>=5 else 'PC_MICROBATCH_LOCAL_BUDGET_V2' if build['revision']>=3 else 'PC_MICROBATCH_LOCAL_BUDGET_V1'),
        'batch build/context/schema binding differs')
    for terminal in terminals.values():
        value=terminal['bridge']['a12_route']['pc_batch']
        require(all(value[k]==batch[k] for k in ('schema','worker_epoch','manager_epoch','context_sha256')),
            'batch terminal instance/context changed')
    raw=load('events.jsonl',16*1024**2);require(raw.endswith(b'\n'),'torn batch journal')
    lines=raw.splitlines();require(0<len(lines)<=6000,'batch journal count bound')
    chain=ZERO;window=None;cap=None;mode=None;pid=None;router=0;backend=0;weights=0;closed=False;normal=False
    active=None;completed=[];allocated=0;grants=0;deadline=None
    for serial,line in enumerate(lines,1):
        require(len(line)<=32768,'batch record byte bound');r=strict_json(line)
        require(r['schema']==SCHEMA and r['domain']==old.DOMAIN and r['record_serial']==serial and
            r['previous_record_sha256']==chain and r['counter_semantics']==SEMANTICS,'batch journal identity/chain differs')
        require(digest({k:v for k,v in r.items() if k not in ('monotonic_ns','record_sha256')})==r['record_sha256'],
            'batch journal SHA differs')
        chain=r['record_sha256'];window=window or r['window_id'];cap=cap or r['batch_size'];mode=mode or r['journal_mode']
        require(r['window_id']==window and r['batch_size']==cap and cap in (1,72) and r['journal_mode']==mode and
            mode==('strict' if cap==1 else 'request') and not normal,'mixed/invalid batch mode/window')
        event=r['event']
        if event in ('PERMISSION','MICROBATCH_GRANT'):
            q=r['request'];pid=pid or q['pid'];lane='router' if q['phase'].startswith('router_') else 'backend'
            require(type(q['pid']) is int and q['pid']==pid and q['sequence']==(router if lane=='router' else backend)+1 and
                q['batch_protocol']==1 and q['worker_epoch']==batch['worker_epoch'] and
                q['manager_epoch']==batch['manager_epoch'] and q['context_sha256']==config['context_sha256'],
                'batch request peer/epoch/sequence differs')
            if batch['schema']!='PC_MICROBATCH_LOCAL_BUDGET_V1':
                require(batch['bound_worker_pid']==pid and q['process_start_ticks']==batch['bound_worker_start_ticks']>0,
                    'batch process binding differs')
            if lane=='router':router=q['sequence']
            else:backend=q['sequence']
            health=r['health_observation'];require(health['domain']=='PC_LOCAL_MEMORY_ONLY' and
                health['memory_kib']['MemAvailable']>=1114112 and health['board_CMA']=='NOT_AVAILABLE_PC',
                'PC batch memory observation invalid')
            if event=='PERMISSION':
                require(r['allow'] is True,'denied lifecycle permission')
                if q['phase']=='router_open':require(router==1 and weights==0 and q['job']==0,'router open differs')
                elif q['phase']=='device_open':require(router==1 and backend==1 and q['job']==0,'CPU open differs')
                elif q['phase']=='weight_load':
                    require(weights<72 and q['job']==weights+1 and active is None,'batch weight order differs');weights+=1
                elif q['phase']=='router_close':
                    require(active is None and completed==list(IDS) and q['job']==0,'early router close');closed=True
                else:raise ValueError('unexpected lifecycle phase')
            else:
                require(active is not None and q['phase']=='batch' and r['request_id']==active['request_id'],'orphan grant')
                name=active['request_id'];base=active['base_permits'];f=known[name]
                new={'app_R0':107,'warm_prefix':70,'app_hit':37}[name]
                plan=[min(8,new-i) for i in range(0,new,8)]+([1]*(f['max_tokens']-1) if name!='warm_prefix' else [])
                index=(allocated-base)//72;require(index<len(plan),'batch plan overflow')
                count=min(cap,72-(allocated-base)%72);first=allocated+1;last=allocated+count
                require(q['job']==first and q['T']==plan[index] and type(q['T']) is int and
                    q['request_generation']==len(completed)+1 and q['request_sha256']==active['verified_request']['request_sha256'] and
                    last<=base+active['max_submits'],'grant work/range/request differs')
                expected={k:q[k] for k in ('sequence','worker_epoch','manager_epoch','context_sha256')}
                expected.update(allow=True,first_job=first,last_job=last,count=count,T=q['T'],
                    request_generation=q['request_generation'],request_sha256=q['request_sha256'])
                if build['revision']>=4:
                    value=r['grant']['deadline_monotonic_ns'];deadline=deadline or value
                    require(value==deadline and 0<value-r['monotonic_ns']<=900_000_000_000,'grant deadline differs/expired')
                    expected['deadline_monotonic_ns']=value
                require(digest(r['grant'])==digest(expected) and r['cumulative_reserved_jobs']==last,'grant payload/counters differ')
                for job in range(first,last+1):
                    item=dict(sequence=q['sequence'],job=job,pid=pid);recent.append(item);h.update(canonical(item)+b'\n')
                allocated=last;grants+=1
        elif event=='REQUEST_BEGIN_PC_CANDIDATE':
            name=r['request_id'];require(active is None and len(completed)<3 and name==IDS[len(completed)] and
                weights==72 and r['base_permits']==allocated,'batch BEGIN order differs')
            f=known[name];wire={k:v for k,v in f.items() if 'application' not in f or k not in ('application','tokens')}
            if name!='app_R0':wire['cache_binding_sha256']=c['binding']
            expected=dict(request_sha256=digest(wire),frozen_request_sha256=digest(f),ready_sha256=c['ready_sha'],
                binding_sha256=c['binding'],base_completions=allocated,native_identity_sha256=digest(c['identity']))
            require(r['verified_request']==expected and r['max_submits']=={'app_R0':1512,'warm_prefix':648,'app_hit':864}[name],
                'batch BEGIN identity/budget differs')
            active=r;h=hashlib.sha256();recent=deque(maxlen=64)
        elif event=='REQUEST_END_PC_CANDIDATE':
            require(active is not None and r['request_id']==active['request_id'],'orphan batch END')
            name=r['request_id'];summary=c['summaries'][name];end=summary['cumulative_cpu_calls'];count=summary['actual_cpu_calls']
            require(allocated==end and r['permit_count']==count and r['cumulative_permits']==r['native_cpu_verified_completions']==end
                and r['pending']==0 and r['state_cleared'] is True and r['completion_domain']==old.DOMAIN and
                r['permit_sha256']==h.hexdigest() and r['recent_submits']==list(recent) and
                r['overwritten_submits']==max(0,count-64),'batch END allocation/actual CPU accounting differs')
            native=terminals[name]['bridge']['a12_route']['pc_batch']
            require(native['grant_requests']==grants and native['request_generation']==len(completed)+1 and
                native['unused_local_credit']==0,'native grant count/generation/unused differs')
            meta=dict(active['verified_request'],result_sha256=digest(terminals[name]),validation_sha256=digest(summary))
            require(r['verified_request']==meta,'batch END result hashes differ')
            receipt=strict_json(load('COMMIT-'+name+'.json',8192))
            require(digest(receipt)==digest(dict(schema=SCHEMA,window_id=window,request_id=name,end_record_sha256=chain,
                verified_request=meta,replay_allowed=False,release_allowed=False,scope='PC_FORMAT_RECEIPT_NOT_RELEASE_PROOF')),
                'batch COMMIT differs')
            completed.append(name);active=None
        elif event=='WORKER_EXITED_NORMALLY':
            require(closed and completed==list(IDS) and r['exit_code']==0 and r['release_platform_lease'] is False,
                'batch exit lacks normal close');normal=True
        else:raise ValueError('batch fault/incomplete event: '+str(event))
    require(normal and active is None and allocated==c['total']==2880,'batch journal incomplete')
    require((cap==1 and grants==2880) or (cap==72 and grants==40),'batch grant total differs')
    require(len(lines)==82+grants and (cap==1 or len(raw)<=512*1024),'batch journal size/count differs')
    receipt=strict_json(load('NORMAL_CLOSE.json',8192))
    require(digest(receipt)==digest(dict(schema=SCHEMA,window_id=window,last_record_sha256=chain,exit_code=0,
        request_ids=list(IDS),cumulative_permits=allocated,release_allowed=False,replay_allowed=False)), 'batch close receipt differs')
    require(set(os.listdir(fd))==c['inventory'],'batch inventory changed')
    for name,p in c['pins'].items():require(regular(os.stat(name,dir_fd=fd,follow_symlinks=False))==p,'batch evidence changed')
    return dict(c['base'],status='COMPLETE_ACTUAL_PC_MICROBATCH_TRANSCRIPT',actual_cpu_calls=allocated,
        journal_rows=len(lines),batch_grants=grants,grant_size=cap,application_content='PASS_FROZEN_CHECKER',
        private_batch_schema=SCHEMA,trusted_controlled_worker_required=True)


def compile_audit():
    path=ROOT/'platform/qwen35/a12/native_request_audit.py'
    require(sha(path)=='c78ab9ab400722b7e2cf9607f378d0aaa6b0a05e6e72d600113e75a7185d2f8a','frozen native auditor differs')
    node=next(n for n in ast.parse(path.read_bytes()).body if isinstance(n,ast.FunctionDef) and n.name=='audit')
    trial=next(n for n in node.body if isinstance(n,ast.Try))
    index=next(i for i,n in enumerate(trial.body) if isinstance(n,ast.Assign) and isinstance(n.value,ast.Call)
        and isinstance(n.value.func,ast.Name) and n.value.func.id=='load' and n.value.args[0].value=='events.jsonl')
    trial.body=trial.body[:index]+ast.parse('return reconcile_batch(locals())').body
    scope=dict(old.__dict__,NativeRequestController=NativeOnlyChecker,reconcile_batch=journal)
    exec(compile(ast.Module(body=[node],type_ignores=[]),'frozen_native_checks_plus_private_batch_journal','exec'),scope)
    return scope['audit']

audit=compile_audit()
