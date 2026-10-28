"""Independent raw-native / actual-CPU / graph-copy / journal audit, never Board acceptance."""
import argparse
from pathlib import Path
from modelpl_evidence import ROOT,OUT,read,save,sha
from request_journal_verified import FrozenProbe,canonical,digest,ZERO
from request_journal_audit import strict_json
from resource_probe_policy import ordinary_comparison

def wire(request,binding):
    import copy
    result={k:copy.deepcopy(v) for k,v in request.items() if 'application' not in request or k not in ('application','tokens')}
    if result['op']=='cache_create' or result['cache_policy']!='R0':result['cache_binding_sha256']=binding
    return result
def audit(tag):
    folder=OUT/tag;meta=read(folder/'RESULT.json');normal=meta['status']=='PASS_ACTUAL_QWEN_PLM_CPU_WINDOW_NOT_BOARD'
    launch=read(folder/'LAUNCH.json');directory=Path(meta['private_directory']);frozen=FrozenProbe();requests=frozen.requests
    for p in folder.rglob('*'):
        relative=p.relative_to(folder)
        if p.is_file() and relative.as_posix() not in ('RESULT.json','LAUNCH.json'):
            assert (directory/relative).is_file() and sha(p)==sha(directory/relative),str(p)
    data=(folder/'native.stdout').read_bytes();assert len(data)<=1024*1024
    raw=[]
    for line in data.splitlines():assert len(line)+1<=131072;raw.append(strict_json(line))
    assert len(raw)<=32
    ready=next(q for q in raw if q['type']=='ready');assert ready==read(folder/'READY.json')
    assert ready['execution_kind']=='PC_MATH_DOUBLE' and ready['domain']=='PC' and ready['physical_ubatch']==8
    binding=ready['prefix_cache']['binding_sha256'];assert ready['bridge']['cpu_run_count']==ready['bridge']['weight_count']==0
    r=ready['bridge']['a12_route'];assert r['execution_kind']=='CPU_REFERENCE' and r['hardware_done_count'] is None and r['kernel_build_id'] is None
    assert r['pc_adapter']=='A12_REAL_MODEL_PLM_CPU_V1' and r['cpu_run_count']==r['pc_verified_completions']==0 and r['weight_count']==72
    packets={q['id']:q for q in raw if q['type'] in ('result','cache_created')};tokens={}
    for q in raw:
        if q['type']=='token':
            ts=tokens.setdefault(q['id'],[]);assert q['index']==len(ts);ts.append(q['token'])
    chain=ZERO;rows=[]
    for line in (folder/'state/control.jsonl').read_bytes().splitlines():
        assert len(line)+1<=8192;q=strict_json(line);h=q.pop('sha256')
        assert q['serial']==len(rows)+1 and q['previous_sha256']==chain and digest(q)==h;q['sha256']=h;chain=h;rows.append(q)
    assert len(rows)<=4096
    current=None;completed=[];last=0;reserved=0;sequence=1;grants=0;legacy={'router':0,'backend':0};contexts=0;closed=False;comparisons=[]
    for row in rows:
        event=row['event']
        if event=='WINDOW_OPEN':assert row['domain']=='PC_REAL_MODEL_CPU_REFERENCE' and not row['real_device_approval'] and row['cap']==launch['cap']
        elif event=='LEGACY_PERMISSION':
            lane=row['lane'];assert row['sequence']==legacy[lane]+1;legacy[lane]+=1
            if row['phase']=='router_close':assert current is None and len(completed)==3
        elif event=='CONTEXT_BIND':
            contexts+=1;assert contexts==1 and digest(row['facts'])==row['context_sha256'] and not row['independent_board_approval']
            assert row['facts']['schema']=='A12_MODEL_PLM_CPU_CONTEXT_V1' and row['facts']['execution_kind']=='CPU_REFERENCE' and row['facts']['real_device_generation_approval']=='UNBOUND_PC_CPU_ONLY'
            assert not any(k in row['facts'] for k in ('io_addresses','xclbin_uuid','kernel_build_id'))
        elif event=='READY':assert row['native_sha256']==digest(ready) and row['weights']==72 and row['execution_kind']=='CPU_REFERENCE'
        elif event=='BEGIN':
            assert current is None and len(completed)<3;request=requests[len(completed)];expected=wire(request,binding)
            assert row['request']==expected and row['request_sha256']==digest(expected) and row['frozen_request_sha256']==digest(request) and row['base']==last
            assert row['prefix_binding']==binding and 'diagnostic_dir' not in expected and expected['profile'] is False and expected['diagnostic_report'] is False
            n=len(request['tokens'])-(70 if request['id']=='app_hit' else 0);plan=[min(8,n-i) for i in range(0,n,8)]+([1]*(request['max_tokens']-1) if request['op']!='cache_create' else [])
            assert row['budget']==len(plan)*72;current=dict(request=request,wire=expected,digest=digest(expected),base=last,plan=plan);reserved=last
        elif event=='GRANT':
            assert current and row['request_id']==current['request']['id'] and row['request_sha256']==current['digest']
            assert row['sequence']==sequence+1 and row['generation']==len(completed)+2;sequence+=1;grants+=1
            index=(reserved-current['base'])//72;assert index<len(current['plan']) and row['T']==current['plan'][index]
            size=min(launch['cap'],72-(reserved-current['base'])%72);assert row['first']==reserved+1 and row['last']==reserved+size<=current['base']+len(current['plan'])*72;reserved=row['last']
        elif event=='END':
            assert current and row['request_id']==current['request']['id'] and row['request_sha256']==current['digest'];request=current['request'];native=packets[request['id']]
            assert row['result_sha256']==digest(native) and native['status']=='OK' and native['state_cleared_before_response'] is True and native['state_position_after_clear']==-1
            route=native['bridge']['a12_route'];assert native['bridge']['cpu_run_count']==native['bridge']['weight_count']==0 and native['bridge']['error']==''
            assert route['execution_kind']=='CPU_REFERENCE' and route['hardware_done_count'] is None and route['kernel_build_id'] is None and route['pc_output_consumable'] is True
            if request['op']=='cache_create':
                assert not tokens.get(request['id']);count=648;entry=native['prefix_cache']['entries'][0]
                old=read(ROOT/'evidence/model_pl_A/20261025-resource-probe-v1/native-PC-02/warm_prefix/result.json')['prefix_cache']['entries'][0]
                keys=('tokens','position','state_bytes','state_sha256','sequence_sha256','logits_bytes','logits_sha256')
                assert {k:entry[k] for k in keys}=={k:old[k] for k in keys}
                comparisons.append(dict(request_id=request['id'],runtime_reported_snapshot_fields_equal=True,fields=list(keys),full_intermediate_state='NOT_TESTED'))
            else:
                assert native['output_tokens']==tokens[request['id']] and native['teacher_forced'] is False and native['eos'] is True and native['gpu_layers']==0
                n=37 if request['id']=='app_hit' else 107;count=72*((n+7)//8+native['decode_calls'])
                check=frozen.check_answer(request,native);assert check['status']=='pass'
                comparison=ordinary_comparison(read(ROOT/'evidence/model_pl_A/20261025-resource-probe-v1/native-PC-02'/request['id']/'result.json'),native)
                comparisons.append(dict(request_id=request['id'],comparison=comparison))
            total=last+count;private=route['a12_private_control']
            assert row['actual_CPU_calls']==count and row['final_job']==reserved==total==route['cpu_run_count']==route['pc_verified_completions']==route['pc_started_calls']==route['pc_attempted_calls']
            assert private['copy_checks']==count==row['graph_copy_checks'] and private['checked_copy_bytes']==row['graph_checked_bytes']>0
            assert private['request_sha256']==current['digest'] and private['failed'] is False and private['request_active'] is False and route['pc_plm']['bound_request_sha256']==''
            # END bytes alone cannot prove receipt/delivery; enforce those only for accepted normal windows.
            if normal:
                record=read(folder/(request['id']+'-MODEL_RESULT.json'));assert record['result']==native
                receipt=read(folder/'state'/(request['id']+'-receipt.json'));assert receipt['result_sha256']==digest(native) and receipt['END_sha256']==row['sha256']
                fence=record['delivery_fence'];assert fence['requested_ns']<=fence['started_ns']<=fence['ended_ns']<=fence['authorized_ns'] and fence['authorized_ns']-fence['started_ns']<=250000000
            completed.append(request['id']);last=total;current=None
        elif event=='WINDOW_CLOSE':assert completed==['app_R0','warm_prefix','app_hit'] and current is None and not row['release_allowed'];closed=True
        else:raise AssertionError('unlisted model journal event '+event)
    if normal:
        assert closed and contexts==1 and not (folder/'state/DIRTY.json').exists() and meta['claims']==2880 and meta['validated_answers']==2 and meta['worker_exit_code']==0 and meta['all_threads_stopped']
        assert grants==(2880 if launch['cap']==1 else 40) and sequence==meta['private_messages'] and legacy==meta['legacy_sequences']==dict(router=2,backend=73)
        assert raw[-1]['type']=='private_closed' and raw[-1]['private_control']['closed'] is True and raw[-1]['private_control']['release_allowed'] is False
        assert meta['page']['revoked'] and not meta['page']['active'] and not meta['page']['unknown_io']
    else:
        assert not closed and (folder/'state/DIRTY.json').exists() and meta['fault_expectation']['intended_fault_verified'] and meta['control_results']==0
        assert meta['page']['revoked'] and meta['writer_FD_retained'] and meta['owned_pidfd_terminal'] and meta['worker_exit_code']==2
        assert not meta['release_allowed'] and not meta['replay_allowed']
    assert not list(folder.rglob('*.bin')) and not list(folder.rglob('*.f32'))
    return dict(tag=tag,status='ACCEPTED_PC_MODEL_ORDINARY_WINDOW' if normal else 'INTENDED_MODEL_FAULT_REJECTED_DIRTY',
        actual_CPU_claims=meta['page']['claims'],grant_records=grants,normal_comparisons=comparisons,
        BOARD='NOT_TESTED',real_PL_results_consumed=False,full_intermediate_state='NOT_TESTED',release_allowed=False)
def main():
    p=argparse.ArgumentParser();p.add_argument('--suite',required=True);a=p.parse_args();suite=read(OUT/(a.suite+'-SUITE.json'))
    results=[audit(tag) for tag in suite['windows']];assert len(results)==11 and sum(r['status']=='ACCEPTED_PC_MODEL_ORDINARY_WINDOW' for r in results)==2
    save(OUT/(a.suite+'-AUDIT.json'),dict(status='PASS_ACTUAL_CPU_FRONT_ROUTE_ORDINARY_AND_SPECIFIC_FAILURE_GATES',windows=results,
        actual_FPGA_calls=None,BOARD='NOT_TESTED',release_allowed=False,production_enabled=False))
    print('PASS_ACTUAL_CPU_FRONT_ROUTE_ORDINARY_AND_SPECIFIC_FAILURE_GATES')
if __name__=='__main__':main()
