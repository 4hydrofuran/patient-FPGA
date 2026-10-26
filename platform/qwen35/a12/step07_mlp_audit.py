"""Independent BOARD same-input numeric/consumer audit, retaining closeout failure."""
import hashlib
import json
from pathlib import Path
import tarfile
import sys
from common import ROOT,sha,save
from step06_audit import compare
from step07_mlp_prepare import OUT


def main():
    receipt=json.loads((OUT/'readback_01/stdout.txt').read_text(encoding='utf-8'))
    package=OUT/'readback-v1.tar.gz'
    assert package.stat().st_size==receipt['package']['bytes'] and sha(package)==receipt['package']['sha256']
    dest=OUT/'readback-v1';reuse=dest.exists()
    if not reuse:dest.mkdir()
    files={}
    with tarfile.open(package) as tar:
        members=tar.getmembers();assert len(members)==len({m.name for m in members})
        for m in members:
            assert m.isfile() and not Path(m.name).is_absolute() and '..' not in Path(m.name).parts
            data=tar.extractfile(m).read();p=dest/m.name;p.parent.mkdir(parents=True,exist_ok=True)
            if reuse:assert p.read_bytes()==data
            else:
                with p.open('xb') as f:f.write(data)
            files[m.name]=dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
    if (OUT/'READBACK_FILES.json').exists():assert json.loads((OUT/'READBACK_FILES.json').read_text(encoding='utf-8'))==files
    else:save(OUT/'READBACK_FILES.json',files)
    def j(p):return json.loads(p.read_text(encoding='utf-8'))
    run=dest/'run-v1';s1=run/'s1';s2=run/'s2';r1=j(s1/'result.json');r2=j(s2/'result.json')
    assert r1['status']==r2['status']=='OK'
    assert j(s1/'ready.json')['execution_kind']=='CPU_REFERENCE' and j(s2/'ready.json')['execution_kind']=='FPGA_REAL'
    assert r2['bridge']['a12_route']['execution_kind']=='FPGA_REAL'
    assert r1['gpu_layers']==r2['gpu_layers']==0
    for r in (r1,r2):assert r['state_cleared_before_response'] and r['state_position_after_clear']==-1
    for folder in (s1,s2):assert j(folder/'exit.json')['exit_code']==0
    req1=j(s1/'request.json');req2=j(s2/'request.json')
    req1.pop('diagnostic_dir');req2.pop('diagnostic_dir');assert req1==req2
    assert j(s1/'identity.json')['binary_sha256']==j(s2/'identity.json')['binary_sha256']==j(OUT.parent/'20261023-step07-single-v1/BUILD.json')['files']['qwen35-a12']['sha256']
    a=s1/'diag';b=s2/'diag';comparisons={};numeric=True
    for p in sorted(a.glob('logits-*.f32')):
        c=compare((b/p.name).read_bytes(),p.read_bytes(),.002,.0002);numeric &= c['failures']==0;comparisons[p.name]=c
    assert len(comparisons)==10
    m1=j(a/'manifest.json');m2=j(b/'manifest.json')
    index={(p['id'],p['execution']):p for p in m1['projections']};projections={}
    assert set(index)=={(p['id'],p['execution']) for p in m2['projections']}
    for p in m2['projections']:
        q=index[p['id'],p['execution']];assert [p[k] for k in ('T','N','K')]==[q[k] for k in ('T','N','K')]
        x=compare((b/p['input']).read_bytes(),(a/q['input']).read_bytes(),.002,.0002)
        y=compare((b/p['output']).read_bytes(),(a/q['output']).read_bytes(),1e-4,1e-5)
        numeric &= x['failures']==y['failures']==0
        projections[p['id']+':'+str(p['execution'])]=dict(input=x,output=y,T=p['T'],N=p['N'],K=p['K'])
    identical=(b/'hybrid-state.bin').read_bytes()==(a/'hybrid-state.bin').read_bytes()
    state=dict(bit_exact=identical,failures=0 if identical else 1,bytes=(b/'hybrid-state.bin').stat().st_size,
               S1_sha256=sha(a/'hybrid-state.bin'),S2_sha256=sha(b/'hybrid-state.bin'))
    numeric &= state['failures']==0
    nodes1=j(a/'nodes.json');nodes2=j(b/'nodes.json');assert len(nodes1)==len(nodes2)
    nodes=[]
    for x,y in zip(nodes1,nodes2):
        assert all(x[k]==y[k] for k in ('name','op','shape','strides'))
        c=compare((b/y['file']).read_bytes(),(a/x['file']).read_bytes(),.002,.0002)
        numeric &= c['failures']==0;nodes.append(dict(name=x['name'],op=x['op'],comparison=c))
    route=r2['bridge']['a12_route'];trace=route['a12_trace'];assert len(trace)==9
    joined=[]
    for i,t in enumerate(trace):
        assert t['consumer_verified'] and t['layer']==0 and t['op'] in ('gate','up','down') and t['execution_kind']=='FPGA_REAL'
        c=t['backend_completion'];assert c['output_consumable'] and c['status']=='READY' and c['last_status_code']==0
        assert c['a12_observed_ert_state']==4 and c['job_id']==t['job_id'] and c['kernel_build_id']==0xB3030002
        assert c['host_verified_completions']==i+1 and c['weight_load_count']==3 and c['owned_bo_charged_bytes']==6062080
        raw=bytes.fromhex(c['a12_raw_meta_hex']);assert len(raw)==64
        le=lambda offset,width:int.from_bytes(raw[offset:offset+width],'little')
        assert le(0,4)==0x57344138 and le(4,4)==0xB3030002 and le(8,8)==t['job_id']
        assert le(16,4)==0 and le(20,4)==1 and le(24,8)==1 and le(32,8)==1835008
        assert c['a11_argument_groups']==[3]*6 and c['a11_explicit_bo_allocations_host_counter']==10
        spans=list(zip(c['a11_io_bo_addresses'],c['a11_io_bo_charged_sizes']))
        for w in c['a11_live_weights']:spans+=list(zip(w['addresses'],w['charged_sizes']))
        assert len(spans)==10 and sum(size for addr,size in spans)==6062080
        for k,(addr,size) in enumerate(spans):
            assert addr>=0 and addr+size<=2147483648 and size%8192==0
            assert all(addr+size<=a0 or a0+s0<=addr for a0,s0 in spans[:k])
        records=[p for p in m2['projections'] if p['id']=='l00_'+t['op'] and p['execution']==t['execution']]
        assert len(records)==1;p=records[0]
        assert t['T']==p['T'] and t['N']==p['N'] and sha(b/p['output'])==t['output_sha256']
        joined.append(dict(job_id=t['job_id'],T=t['T'],N=t['N'],K=p['K'],epoch=t['epoch'],execution=t['execution'],
             input_sha256=sha(b/p['input']),output_sha256=t['output_sha256'],consumer=t['consumer_name'],
             consumer_op=t['consumer_op'],ERT_state=c['a12_observed_ert_state'],metadata_hex=c['a12_raw_meta_hex']))
    assert [t['T'] for t in trace]==[8,8,8,1,1,1,1,1,1] and route['a12_hardware_global_count'] is None
    assert [t['op'] for t in trace]==['gate','up','down']*3
    assert [t['job_id'] for t in trace]==[1,2,3,73,74,75,145,146,147]
    weights=trace[0]['backend_completion']['a11_live_weights']
    for t in trace:assert t['backend_completion']['a11_live_weights']==weights
    assert len(weights)==3
    # Offline refusal on a saved real Y: no additional hardware calculation.
    sample=next(p for p in m2['projections'] if p['id']=='l00_down')
    raw=(b/sample['output']).read_bytes();mutated=bytearray(raw);mutated[0]^=1
    match=next(t for t in trace if t['op']=='down' and t['execution']==sample['execution'])
    assert hashlib.sha256(mutated).hexdigest()!=match['output_sha256']
    save(OUT/'REAL_Y_REJECTION.json',dict(status='PASS_OFFLINE_REAL_BOARD_OUTPUT_TAMPER_REJECTED',
       domain='PC_VALIDATION_OF_SAVED_BOARD_OUTPUT',projection='l00_down',job=match['job_id'],
       actual_sha256=hashlib.sha256(raw).hexdigest(),mutated_sha256=hashlib.sha256(mutated).hexdigest(),
       actual_matches_graph_trace=hashlib.sha256(raw).hexdigest()==match['output_sha256'],new_hardware_calls=0))
    stopped=j(run/'independent-readback.json')
    assert j(dest/'manager-exit.json')['exit_code']==0
    assert stopped['scans'][-1]['scan_complete'] and stopped['scans'][-1]['no_users_gate']
    assert not stopped['scans'][-1]['device_holders'] and not stopped['scans'][-1]['device_mappings']
    assert not stopped['active_lease_exists'] and not any(stopped['locks'].values())
    assert not stopped['module_present'] and stopped['gdm_state']=='active' and stopped['fpga_state']=='operating'
    assert stopped['overlays']=={'k26-starter-kits_image_1':'applied'}
    assert not (s2/'ISOLATED.json').exists()
    finalize=[json.loads(l) for l in (s2/'finalization-events.jsonl').read_text().splitlines()]
    assert finalize[-1]['event']=='FINALIZATION_PREPARED_FOR_ATOMIC_ARCHIVE'
    assert (s2/'final-resource-scan-0001.json').is_file()
    lifecycle=[json.loads(l) for l in (run/'lifecycle.jsonl').read_text(encoding='utf-8').splitlines()]
    commands=[l for l in lifecycle if l['event']=='COMMAND_END']
    assert all(l['exit_code']==0 for l in commands)
    gates=[l for l in lifecycle if l['event']=='KERNEL_LOG_GATE'];assert gates and all(l['allowed'] for l in gates)
    sys.path.insert(0,str(ROOT/'platform/qwen35/a10'))
    from kernel_log_gate import KernelLogGate
    kernel_gate=KernelLogGate()
    assert kernel_gate.observe(stopped['boot_id'],gates[-1]['raw_log'],gates[-1]['current_sha256'])['allowed']
    post_kernel=kernel_gate.observe(stopped['boot_id'],stopped['kernel_raw'])
    assert post_kernel['allowed'],'new unreviewed diagnostic after final observed gate'
    readbacks=[l for l in lifecycle if l['event']=='READBACK']
    temp=max(v for l in readbacks for v in l['temperatures_mC'])
    available=min(l['memory_kib']['MemAvailable'] for l in readbacks);cma=min(l['memory_kib']['CmaFree'] for l in readbacks)
    prior=ROOT/'evidence/model_pl_A/20261023-step06-v1/readback-v1/run-v1/diag-teacher_T8'
    same_previous_S1=all(sha(p)==sha(prior/p.name) for p in a.glob('logits-*.f32')) and sha(a/'hybrid-state.bin')==sha(prior/'hybrid-state.bin')
    audit=dict(status='PASS_BOARD_L00_MLP_REAL_CONSUMPTION_AND_NORMAL_CLOSEOUT' if numeric else 'FAIL_BOARD_L00_MLP_NUMERIC',
        physical_domain='BOARD',scope='l0',same_input_config=True,logits=comparisons,projections=projections,
        hybrid_state=state,downstream_nodes=nodes,joined_actual_calls=joined,same_previous_S1=same_previous_S1,
        explicit_BO_peak_bytes=6062080,explicit_BO_count=10,weight_loads=3,actual_calls=9,
        hardware_global_count=None,board_speedup=None,full_model_PL='NOT_TESTED',MLP_three_projections='PASS' if numeric else 'FAIL',
        resource=dict(min_MemAvailable_kib=available,min_CmaFree_kib=cma,max_temperature_mC=temp,
          sampled_board_readbacks=len(readbacks),S1_RSS_HWM_kib=r1['peak_rss_kib'],S2_RSS_HWM_kib=r2['peak_rss_kib'],
          full_physical_peak_bytes=None),
        lifecycle=dict(status='NORMAL_EXIT_AND_RESTORE_PASS',worker_exit_codes=[0,0],manager_exit_code=0,
          active_lease=False,dual_locks_held=False,default_PL_restored=True,GDM_active=True,ZOCL_absent=True,
          no_device_users=True,finalization_events=finalize,forced_signals=0),
        deferred_failures=['Step06 PC/ARM whole graph FAIL','Step06 first full-range conservative capacity FAIL'],
        independent_kernel_gate=post_kernel,thresholds_unchanged=True)
    save(OUT/'AUDIT.json',audit)
    print(json.dumps(dict(status=audit['status'],calls=joined,logits_bit_exact=all(c['bit_exact'] for c in comparisons.values()),
        state_bit_exact=state['bit_exact'],same_previous_S1=same_previous_S1,resource=audit['resource'],manager_exit_code=0)))
    assert numeric


if __name__=='__main__':main()
