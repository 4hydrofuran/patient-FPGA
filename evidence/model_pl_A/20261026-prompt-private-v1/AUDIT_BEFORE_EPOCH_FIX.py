"""Independent raw graph/call/token/journal audit for the new private workload."""
import argparse
import hashlib
import math
import os
from pathlib import Path
import stat
from promptpl_evidence import ROOT,OUT,read,save,sha
from promptpl_workload import PromptProbe
from request_journal_verified import digest,ZERO
from request_journal_audit import strict_json
from resource_probe_policy import ordinary_comparison

def audit(relative):
    folder=OUT/relative;meta=read(folder/'RESULT.json');launch=read(folder/'LAUNCH.json');build=read(launch['build_path'])
    assert sha(launch['build_path'])==launch['build_sha256'];probe=PromptProbe(build);requests=probe.requests
    source={r['path']:r for r in launch['source']}
    for name in ('promptpl_manager.py','promptpl_workload.py'):
        key='platform/qwen35/a12/'+name;assert sha(ROOT/key)==source[key]['sha256']
    private=Path(meta['private_directory']);st=private.stat();assert stat.S_ISDIR(st.st_mode) and st.st_uid==os.geteuid() and not st.st_mode&0o022
    for p in folder.rglob('*'):
        if p.is_file() and p.name not in ('LAUNCH.json','RESULT.json','AUDIT.json'):
            original=private/p.relative_to(folder);assert original.is_file() and sha(p)==sha(original),str(p)
    raw=(folder/'native.stdout').read_bytes();assert len(raw)<=1024*1024
    packets=[]
    for line in raw.splitlines():assert len(line)+1<=131072;packets.append(strict_json(line))
    assert len(packets)<=5+sum(r['max_tokens'] for r in requests if r['op']=='generate')
    ready=next(r for r in packets if r['type']=='ready');assert ready==read(folder/'READY.json')
    assert ready['domain']=='PC' and ready['execution_kind']=='PC_MATH_DOUBLE' and ready['physical_ubatch']==8
    assert ready['bridge']['cpu_run_count']==ready['bridge']['weight_count']==0
    route=ready['bridge']['a12_route'];assert route['pc_adapter']=='A12_REAL_MODEL_PLM_CPU_V1' and route['execution_kind']=='CPU_REFERENCE'
    assert route['cpu_run_count']==route['pc_verified_completions']==0 and route['weight_count']==72
    binding=ready['prefix_cache']['binding_sha256'];assert ready['prefix_cache']['identity']['input_workload_sha256']==digest(requests)
    generation=read(folder/'LIVE_SOURCE.json');page=meta['independent_page'];assert meta['independent_pidfd_terminal'] is True
    assert page['worker_pid']==meta['owned_native_pid'] and page['source_slot']['domain']==1 and page['hardware_completions'] is None
    assert page['source_slot']['identity_sha256']==generation['identity_sha256'] and page['source_slot']['epoch_sha256']==hashlib.sha256(generation['epoch'].encode()).hexdigest()
    assert page['revoked'] is True and meta['release_allowed'] is meta['replay_allowed'] is meta['real_PL_results_consumed'] is False
    native={};tokens={}
    for q in packets:
        if q['type']=='token':
            ts=tokens.setdefault(q['id'],[]);assert q['index']==len(ts);ts.append(q['token'])
        elif q['type'] in ('result','cache_created'):
            assert q['id'] not in native;native[q['id']]=q
    rows=[];chain=ZERO
    for line in (folder/'state/control.jsonl').read_bytes().splitlines():
        assert len(line)+1<=8192;row=strict_json(line);value={k:v for k,v in row.items() if k!='sha256'}
        assert row['serial']==len(rows)+1 and row['previous_sha256']==chain and row['epoch']==page['manager_epoch'] and row['sha256']==digest(value)
        chain=row['sha256'];rows.append(row)
    assert len(rows)<=4096
    active=None;last=0;reserved=0;completed=[];grants=0;sequence=1;legacy={'router':0,'backend':0};closed=False;binds=0;resident=0;contexts=0;answers=[]
    normal=meta['error'] is None
    for row in rows:
        event=row['event']
        if event=='WINDOW_OPEN':
            assert row['cap']==launch['cap']==meta['cap'] and row['domain']=='PC_CPU_MODEL' and row['real_device_approval'] is False
            assert row['worker_pid']==page['worker_pid'] and row['worker_start_ticks']==page['worker_start_ticks']
        elif event=='LEGACY_PERMISSION':
            lane=row['lane'];assert row['sequence']==legacy[lane]+1;legacy[lane]+=1
            if row['phase']=='router_close':assert active is None and len(completed)==3
        elif event=='CONTEXT_BIND':
            contexts+=1;assert contexts==1 and row['independent_board_approval'] is False and row['live_approval_pending'] is True
            assert row['context_sha256']==digest(row['facts'])==page['context_sha256']
            assert row['facts']['execution_kind']=='CPU_REFERENCE' and row['facts']['real_device_generation_approval']=='UNBOUND_PC_CPU_ONLY'
            assert not any(k in row['facts'] for k in ('xclbin_uuid','io_addresses','kernel_build_id'))
        elif event=='LIVE_GENERATION_BIND':
            binds+=1;assert binds==1 and row['Board_approval'] is False and row['context_sha256']==page['context_sha256']
            assert row['source_identity_sha256']==generation['identity_sha256'] and row['generation_epoch']==generation['epoch']
        elif event=='READY':assert row['native_sha256']==digest(ready) and row['weights']==72 and row['hardware_completions'] is None
        elif event=='LIVE_GENERATION_RESIDENT':
            resident+=1;assert resident==1 and row['Board_approval'] is False and row['resident_report_sha256']==digest(route)
            assert row['resident_signature']=={k:route[k] for k in row['resident_signature']}
        elif event=='BEGIN':
            assert active is None and len(completed)<3;r=requests[len(completed)]
            wire={k:v for k,v in r.items() if 'application' not in r or k not in ('tokens','application')}
            if r['op']=='cache_create' or r['cache_policy']!='R0':wire['cache_binding_sha256']=binding
            assert row['request']==wire and row['request_sha256']==digest(wire) and row['frozen_request_sha256']==digest(r)
            assert row['base']==last and row['prefix_binding']==binding and row['execution_kind']=='PC_NATIVE_MATH_NOT_FPGA'
            n=len(r['tokens'])-(build['prefix_tokens'] if r['id']=='app_hit' else 0)
            plan=[min(8,n-i) for i in range(0,n,8)]+([1]*(r['max_tokens']-1) if r['op']=='generate' else [])
            assert row['budget']==72*len(plan) and row['base']+row['budget']<=5000
            active=dict(request=r,wire=wire,digest=digest(wire),base=last,plan=plan,new=n);reserved=last
        elif event=='GRANT':
            assert active and row['request_id']==active['request']['id'] and row['request_sha256']==active['digest']
            assert row['sequence']==sequence+1 and row['generation']==len(completed)+2;sequence+=1;grants+=1
            index=(reserved-active['base'])//72;assert index<len(active['plan']) and row['T']==active['plan'][index]
            size=min(meta['cap'],72-(reserved-active['base'])%72)
            assert row['first']==reserved+1 and row['last']==reserved+size<=active['base']+72*len(active['plan']) and row['fresh_sample']>0
            reserved=row['last']
        elif event=='END':
            assert active and row['request_id']==active['request']['id'] and row['request_sha256']==active['digest'];r=active['request'];q=native[r['id']]
            assert row['result_sha256']==digest(q) and q['state_cleared_before_response'] is True and q['state_position_after_clear']==-1 and q['status']=='OK'
            actual=q['bridge']['a12_route'];assert q['bridge']['cpu_run_count']==q['bridge']['weight_count']==0 and q['bridge']['error']==''
            assert actual['execution_kind']=='CPU_REFERENCE' and actual['hardware_done_count'] is actual['kernel_build_id'] is None
            if r['op']=='cache_create':
                assert q['prefix_tokens']==build['prefix_tokens'] and not tokens.get(r['id']);probe.check_warm(q);decode=0;content=None
            else:
                assert q['output_tokens']==tokens[r['id']] and q['eos'] is True and q['teacher_forced'] is False and q['domain']=='PC' and q['gpu_layers']==0
                decode=q['decode_calls'];assert type(decode) is int and decode==len(q['output_tokens'])<r['max_tokens']
                cache=q['prefix_cache_request'];assert cache['hit'] is (r['id']=='app_hit') and cache['new_tokens']==active['new']
                assert cache['reused_tokens']==(build['prefix_tokens'] if r['id']=='app_hit' else 0) and q['prompt_tokens']==len(r['tokens'])
                content=probe.check_answer(r,q)
            count=72*(math.ceil(active['new']/8)+decode);last+=count;private_report=actual['a12_private_control']
            assert last==reserved==row['final_job']==actual['cpu_run_count']==actual['pc_attempted_calls']==actual['pc_started_calls']==actual['pc_verified_completions']
            assert row['verified_backend_calls']==count==row['graph_copy_checks']==private_report['copy_checks'] and row['execution_kind']=='CPU_REFERENCE'
            assert row['graph_checked_bytes']==private_report['checked_copy_bytes']>0 and row['hardware_calls'] is None and row['content']==content
            assert private_report['request_sha256']==active['digest'] and private_report['failed'] is private_report['request_active'] is False
            assert actual['pc_plm']['bound_request_sha256']=='' and actual['pc_plm']['local_generation']==0 and actual['pc_output_consumable'] is True
            if normal:
                record=read(folder/(r['id']+'-MODEL_RESULT.json'));receipt=read(folder/'state'/(r['id']+'-receipt.json'))
                assert record['result']==q and receipt['result_sha256']==digest(q) and receipt['END_sha256']==row['sha256'] and receipt['clinical_review'] is False
                fence=record['delivery_fence'];assert fence['requested_ns']<=fence['started_ns']<=fence['ended_ns']<=fence['authorized_ns'] and fence['authorized_ns']-fence['started_ns']<=250000000
                assert record['summary']['verified_backend_calls']==count and record['summary']['cumulative_backend_calls']==last
                if content is not None:answers.append(dict(id=r['id'],content=content,send_to_verified_answer_s=record['summary']['send_to_validated_result_s'],
                    internal_first_token_s=record['summary']['raw_native_first_token_s'],new_tokens=active['new'],actual_CPU_calls=count))
            completed.append(r['id']);active=None
        elif event=='WINDOW_CLOSE':assert not active and completed==['app_R0','warm_prefix','app_hit'] and row['release_allowed'] is row['replay_allowed'] is False;closed=True
        else:raise AssertionError('unknown private prompt event '+event)
    assert contexts==binds==resident==1
    if normal:
        assert closed and completed==meta['completed']==['app_R0','warm_prefix','app_hit'] and last==page['claims']==meta['claims']
        assert not page['active'] and not page['unknown_io'] and not (private/'state/DIRTY.json').exists() and meta['worker_exit_code']==0 and meta['all_threads_stopped'] is True
        assert grants==last//meta['cap'] and meta['private_messages']==sequence==grants+1 and legacy==meta['legacy_sequences']==dict(router=2,backend=73)
        assert meta['model_result_files']==3 and packets[-1]['type']=='private_closed' and packets[-1]['private_control']['closed'] is True
        assert packets[-1]['private_control']['release_allowed'] is False
        ordinary_comparison(native['app_R0'],native['app_hit'])
    else:
        assert not closed and (private/'state/DIRTY.json').exists() and meta['worker_exit_code']==2 and meta['model_result_files']==0
        assert meta['writer_FD_retained'] is True and meta['control_results']==0 and meta['completed']==[]
        fault=meta['injection'];reason=meta['reason'];text=raw.decode()
        if fault in ('begin_fsync','grant_fsync','end_fsync','receipt_fsync'):assert 'injected' in reason and ('fsync failure' in reason)
        if fault in ('begin_fsync','grant_fsync','request_digest'):assert page['claims']==0
        if fault=='request_digest':assert 'private request bind failed' in text
        if fault=='same_uuid_reload':
            assert 'generation node replaced/unloaded' in reason and page['claims']==5 and page['unknown_io']
            q=packets[-1];r=q['private_CPU_report']['a12_route'];assert r['pc_attempted_calls']==5 and r['pc_started_calls']==r['pc_verified_completions']==4 and q['private_control']['copy_checks']==4
        if fault=='drop_copy':
            assert 'private graph copy differs' in text and page['claims']==1
            q=packets[-1];r=q['private_CPU_report']['a12_route'];assert r['pc_attempted_calls']==r['pc_started_calls']==r['pc_verified_completions']==1 and q['private_control']['copy_checks']==0
        if fault=='end_slow':assert 'foreign/reused/stale health ticket' in reason
    assert not list(folder.rglob('*.bin')) and not list(folder.rglob('*.f32'))
    return dict(folder=relative,status='PASS_NORMAL_PRIVATE_CPU_WINDOW' if normal else 'PASS_SPECIFIC_FAULT_WITHHELD',cohort_id=meta['cohort_id'],cap=meta['cap'],
        actual_CPU_claims=page['claims'],grant_records=grants,answers=answers,source_slot_domain=1,stdout_packets=len(packets),
        full_state_scope='RUNTIME_SHA_DIGESTS_NO_RAW_INTERMEDIATE_FILES',BOARD='NOT_TESTED',actual_PL_results_consumed=False,release_allowed=False)

def main():
    p=argparse.ArgumentParser();p.add_argument('--suite',required=True);a=p.parse_args();suite=read(OUT/(a.suite+'-SUITE.json'))
    results=[audit(r['folder']) for r in suite['windows']]
    save(OUT/(a.suite+'-AUDIT.json'),dict(status='PASS_RAW_PRIVATE_PROMPT_WINDOWS',windows=results,BOARD='NOT_TESTED',actual_PL_results_consumed=False))
    print('PASS_RAW_PRIVATE_PROMPT_WINDOWS',a.suite,len(results))
if __name__=='__main__':main()
