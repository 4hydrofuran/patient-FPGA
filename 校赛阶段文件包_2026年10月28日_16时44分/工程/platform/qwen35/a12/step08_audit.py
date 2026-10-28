"""Independent full-model diagnostic and development-generation audits."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tarfile
from common import ROOT,sha,save
from step08_common import OUT
from step06_audit import compare

def j(p):return json.loads(p.read_text(encoding='utf-8'))

def extract(folder):
    receipt=j(folder/'readback_01/stdout.txt');archive=folder/'readback-v1.tar.gz'
    assert sha(archive)==receipt['package']['sha256'] and archive.stat().st_size==receipt['package']['bytes']
    dest=folder/'readback-v1';dest.mkdir();files={}
    with tarfile.open(archive) as tar:
        members=tar.getmembers();assert len(members)==len({m.name for m in members})
        for m in members:
            assert m.isfile() and not Path(m.name).is_absolute() and '..' not in Path(m.name).parts
            data=tar.extractfile(m).read();p=dest/m.name;p.parent.mkdir(parents=True,exist_ok=True)
            with p.open('xb') as f:f.write(data)
            files[m.name]=dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
    save(folder/'READBACK_FILES.json',files)
    return dest,receipt

def lifecycle(folder,dest,receipt):
    run=dest/'run-v1';assert j(dest/'manager-exit.json')['exit_code']==0
    for s in ('s1','s2'):assert j(run/s/'exit.json')['exit_code']==0
    assert not (run/'s2/ISOLATED.json').exists()
    records=[json.loads(l) for l in (run/'lifecycle.jsonl').read_text(encoding='utf-8').splitlines()]
    gates=[r for r in records if r['event']=='KERNEL_LOG_GATE'];assert gates and all(r['allowed'] for r in gates)
    for r in gates:
        p=run/r['raw_log_file'];assert sha(p)==r['raw_log_sha256']==r['current_sha256']
    assert all(r['exit_code']==0 for r in records if r['event']=='COMMAND_END')
    health=[r for r in records if r['event']=='LIVE_HEALTH'];assert health
    assert all(r['memory_kib']['CmaFree']>=98304 and r['memory_kib']['MemAvailable']>=1114112 for r in health)
    assert all(all(0<t<55000 for t in r['temperatures_mC']) for r in health)
    sys.path.insert(0,str(ROOT/'platform/qwen35/a10'))
    from kernel_log_gate import KernelLogGate
    gate=KernelLogGate();last=gates[-1]
    assert gate.observe(receipt['boot_id'],(run/last['raw_log_file']).read_bytes().decode(),last['raw_log_sha256'])['allowed']
    assert gate.observe(receipt['boot_id'],receipt['kernel_raw'],receipt['kernel_sha256'])['allowed']
    snapshots=[]
    for name in ('status_final','delayed_01'):
        state=j(folder/name/'stdout.txt');assert j(folder/name/'receipt.json')['exit_code']==0
        assert state['boot_id']==receipt['boot_id'] and state['kernel']=='6.8.12-a10irq2'
        assert state['scans'][-1]['no_users_gate'] and not state['module_present'] and not state['active_lease_exists']
        assert not any(state['locks'].values()) and all(state['known_processes_absent'].values())
        assert state['lease_archived'] and state['gdm_state']=='active' and state['fpga_state']=='operating'
        assert state['overlays']=={'k26-starter-kits_image_1':'applied'}
        k=gate.observe(state['boot_id'],state['kernel_raw'],state['kernel_sha256']);assert k['allowed']
        snapshots.append(dict(name=name,kernel_gate=k,processes_absent=state['known_processes_absent']))
    return dict(manager_exit=0,worker_exits=[0,0],normal_restore=True,postchecks=snapshots,
       min_MemAvailable_kib=min(r['memory_kib']['MemAvailable'] for r in health),
       min_CmaFree_kib=min(r['memory_kib']['CmaFree'] for r in health),
       max_temperature_mC=max(t for r in health for t in r['temperatures_mC']),health_samples=len(health))

def run(variant):
    folder=OUT/variant;dest,receipt=extract(folder);root=dest/'run-v1';left=root/'s1';right=root/'s2'
    spec=j(folder/'bundle-v1/control/window-spec.json')
    for s in (left,right):assert j(s/'identity.json')['binary_sha256']=='18d3d929cafdaa5043be5e4febf6150a938f12be5a1ea2da56d36be893a6c7d4'
    assert j(left/'ready.json')['execution_kind']=='CPU_REFERENCE' and j(right/'ready.json')['execution_kind']=='FPGA_REAL'
    initial=j(right/'ready.json')['bridge']['a12_route'];assert initial['weight_load_count']==72
    spans=list(zip(initial['a11_io_bo_addresses'],initial['a11_io_bo_charged_sizes']))
    assert initial['a11_argument_groups']==[3]*6 and len(initial['a11_live_weights'])==72
    for weight in initial['a11_live_weights']:spans.extend(zip(weight['addresses'],weight['charged_sizes']))
    assert len(spans)==148 and sum(n for a,n in spans)==140591104
    for i,(a,n) in enumerate(spans):
        assert 0<=a and a+n<=2147483648 and n>0 and n%8192==0
        assert all(a+n<=b or b+m<=a for b,m in spans[:i])
    cases=[];all_numeric=True;calls=[]
    requests=j(folder/'bundle-v1/control/requests.json');expected_j=0
    for req in requests:
        one=left/req['id'];two=right/req['id'];s1=j(one/'result.json');s2=j(two/'result.json')
        assert s1['status']==s2['status']=='OK'
        a=j(one/'request.json');b=j(two/'request.json');a.pop('diagnostic_dir',None);b.pop('diagnostic_dir',None);assert a==b
        assert s1['state_cleared_before_response'] and s2['state_cleared_before_response']
        assert s1['state_position_after_clear']==s2['state_position_after_clear']==-1
        route=s2['bridge']['a12_route'];assert route['execution_kind']=='FPGA_REAL' and route['a12_route_scope']=='all'
        assert route['weight_load_count']==72 and route['owned_bo_charged_bytes']==140591104
        assert route['a11_explicit_bo_allocations_host_counter']==148
        assert route['a11_live_weights']==initial['a11_live_weights'] and route['a11_io_bo_addresses']==initial['a11_io_bo_addresses']
        row=dict(id=req['id'],tokens_match=s1['output_tokens']==s2['output_tokens'],text_match=s1['text']==s2['text'],
           EOS_match=s1['eos']==s2['eos'],S1_text=s1['text'],S2_text=s2['text'],EOS=s2['eos'],
           state_fingerprint_match=s1['state_fingerprint']==s2['state_fingerprint'],
           prefill_last_logits_fingerprint_match=s1['last_prompt_logits_fnv64']==s2['last_prompt_logits_fnv64'],
           prompt_tokens=s2['prompt_tokens'],output_tokens=len(s2['output_tokens']),host_completions=route['host_verified_completions'])
        if variant=='diagnostic':
            d1=one/'diag';d2=two/'diag';comparisons={}
            for p in sorted(d1.glob('logits-*.f32')):comparisons[p.name]=compare((d2/p.name).read_bytes(),p.read_bytes(),.002,.0002)
            assert len(comparisons)==10
            m1=j(d1/'manifest.json');m2=j(d2/'manifest.json');index={(r['id'],r['execution']):r for r in m1['projections']}
            assert len(index)==len(m2['projections'])==216
            projections={}
            for r in m2['projections']:
                q=index[r['id'],r['execution']];assert [q[k] for k in ('T','N','K')]==[r[k] for k in ('T','N','K')]
                x=compare((d2/r['input']).read_bytes(),(d1/q['input']).read_bytes(),.002,.0002)
                y=compare((d2/r['output']).read_bytes(),(d1/q['output']).read_bytes(),1e-4,1e-5)
                projections[r['id']+':'+str(r['execution'])]=dict(input=x,output=y)
            state=(d1/'hybrid-state.bin').read_bytes()==(d2/'hybrid-state.bin').read_bytes()
            n1=j(d1/'nodes.json');n2=j(d2/'nodes.json');nodes=[];assert len(n1)==len(n2)
            for x,y in zip(n1,n2):
                assert all(x[k]==y[k] for k in ('name','op','shape','strides'))
                nodes.append(dict(name=x['name'],comparison=compare((d2/y['file']).read_bytes(),(d1/x['file']).read_bytes(),.002,.0002)))
            trace=route['a12_trace'];assert len(trace)==216
            coverage={}
            for i,t in enumerate(trace):
                c=t['backend_completion'];assert t['consumer_verified'] and t['execution_kind']=='FPGA_REAL'
                assert c['a12_observed_ert_state']==4 and c['kernel_build_id']==0xB3030002 and c['output_consumable']
                assert c['job_id']==t['job_id']==i+1 and c['host_verified_completions']==i+1
                raw=bytes.fromhex(c['a12_raw_meta_hex']);le=lambda off,n:int.from_bytes(raw[off:off+n],'little')
                assert len(raw)==64 and le(0,4)==0x57344138 and le(4,4)==0xB3030002 and le(8,8)==i+1
                assert le(16,4)==0 and le(20,4)==1 and le(24,8)==1 and le(32,8)==1835008
                assert c['a11_live_weights']==initial['a11_live_weights'] and c['owned_bo_charged_bytes']==140591104
                r=next(r for r in m2['projections'] if r['id']==f"l{t['layer']:02}_{t['op']}" and r['execution']==t['execution'])
                assert t['row_start']==0 and t['T']==r['T'] and sha(d2/r['output'])==t['output_sha256']
                coverage.setdefault(str(t['layer']),{}).setdefault(t['op'],[]).append(t['T'])
                calls.append(dict(job=t['job_id'],layer=t['layer'],op=t['op'],T=t['T'],ERT=4,
                   output_sha256=t['output_sha256'],input_sha256=sha(d2/r['input']),consumer=t['consumer_name'],consumer_op=t['consumer_op']))
            assert set(coverage)==set(map(str,range(24)))
            assert all(set(v)=={'gate','up','down'} and all(t==[8,1,1] for t in v.values()) for v in coverage.values())
            all_numeric=all(x['failures']==0 for x in comparisons.values()) and all(p[k]['failures']==0 for p in projections.values() for k in ('input','output')) and state and all(n['comparison']['failures']==0 for n in nodes)
            row.update(logits=comparisons,projections=projections,mixed_state_byte_exact=state,
               mixed_state_bytes=(d2/'hybrid-state.bin').stat().st_size,nodes=nodes,coverage=coverage)
        else:
            assert not route['a12_trace']
            assert j(one/'tokenization.json')['tokens']==j(two/'tokenization.json')['tokens']==req['tokens']
            all_numeric &= all(row[k] for k in ('tokens_match','text_match','EOS_match','state_fingerprint_match','prefill_last_logits_fingerprint_match'))
        cases.append(row)
    life=lifecycle(folder,dest,receipt)
    permissions=[json.loads(l) for l in (right/'worker/events.jsonl').read_text().splitlines()]
    submits=[x for x in permissions if x.get('request',{}).get('phase')=='submit']
    assert submits and all(x['allow'] for x in submits)
    loads=[x for x in permissions if x.get('request',{}).get('phase')=='weight_load'];assert len(loads)==72
    assert len(submits)==j(right/'exit.json')['host_permission_runs']==cases[-1]['host_completions']<=spec['max_runs']
    status=('PASS_BOARD_ALL_24_LAYERS_216_REAL_CONSUMED_OUTPUTS' if variant=='diagnostic' else 'PASS_BOARD_ALL_FROZEN_DEV_PAIRED_GENERATION') if all_numeric else 'FAIL_BOARD_'+variant.upper()+'_NUMERICAL_PAIR'
    result=dict(status=status,variant=variant,cases=cases,actual_calls=len(submits),weight_loads=72,
       explicit_BO_count=148,explicit_BO_bytes=140591104,joined_calls=calls,lifecycle=life,
       hardware_global_counter=None,physical_peak_bytes=None,speedup=None,thresholds_unchanged=True,
       natural_per_call_consumption_trace='DISABLED_NORMAL_MODE' if variant=='generation' else 'VERIFIED_ALL_CALLS',
       original_task06_failures='PRESERVED',medical_review='NOT_CLAIMED')
    save(OUT/(variant.upper()+'_AUDIT.json'),result)
    print(json.dumps(dict(status=status,actual_calls=len(submits),cases=len(cases),all_numeric=all_numeric)))
    assert all_numeric

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('variant',choices=['diagnostic','generation']);run(parser.parse_args().variant)
