"""Independent local raw-output/state/resource audit of the BOARD CPU-only run."""
from array import array
import hashlib
import json
import math
from pathlib import Path
import sys
import tarfile
from common import ROOT,sha,save
from step06_prepare import OUT


def compare(a,b,atol,rtol):
    assert len(a)==len(b) and len(a)%4==0
    if a==b:return dict(bit_exact=True,max_abs=0.,max_rel=0.,NRMSE=0.,failures=0,elements=len(a)//4)
    x=array('f');x.frombytes(a);y=array('f');y.frombytes(b)
    assert sys.byteorder=='little'
    maximum=relative=square=scale=0.;failures=0;first=None
    for i,(u,v) in enumerate(zip(x,y)):
        diff=abs(float(u)-v)
        if not math.isfinite(u) or not math.isfinite(v) or diff>atol+rtol*abs(v):
            failures+=1
            if first is None:first=dict(index=i,actual=u,reference=v)
        maximum=max(maximum,diff);relative=max(relative,diff/max(abs(v),1e-30));square+=diff*diff;scale+=float(v)*v
    return dict(bit_exact=False,max_abs=maximum,max_rel=relative,NRMSE=math.sqrt(square/max(scale,1e-300)),
                failures=failures,elements=len(x),first_failure=first,atol=atol,rtol=rtol)


def fields(text):
    result={}
    for line in text.splitlines():
        if ':' not in line:continue
        k,v=line.split(':',1)
        try:result[k]=int(v.strip().split()[0])
        except (ValueError,IndexError):pass
    return result


def main():
    readback=json.loads((OUT/'readback_01/stdout.txt').read_text(encoding='utf-8'))
    archive=OUT/'readback-v1.tar.gz';assert archive.stat().st_size==readback['package']['bytes'] and sha(archive)==readback['package']['sha256']
    extracted=OUT/'readback-v1';reuse=extracted.exists()
    if not reuse:extracted.mkdir(exist_ok=False)
    files={}
    with tarfile.open(archive,'r:gz') as tar:
        members=tar.getmembers();assert len({m.name for m in members})==len(members)
        for m in members:
            assert m.isfile() and not Path(m.name).is_absolute() and '..' not in Path(m.name).parts
            data=tar.extractfile(m).read();p=extracted/m.name;p.parent.mkdir(parents=True,exist_ok=True)
            if reuse:assert p.read_bytes()==data
            else:
                with p.open('xb') as f:f.write(data)
            files[m.name]=dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
    if (OUT/'READBACK_FILES.json').exists():assert json.loads((OUT/'READBACK_FILES.json').read_text(encoding='utf-8'))==files
    else:save(OUT/'READBACK_FILES.json',files)
    run=extracted/'run-v1';r=json.loads((run/'result.json').read_text(encoding='utf-8'));exitrow=json.loads((extracted/'manager-exit.json').read_text(encoding='utf-8'))
    assert r['worker_exit_code']==exitrow['exit_code']==0 and r['hardware_submissions']==0
    assert not readback['active_lease_exists'] and not readback['module_present'] and not any(readback['locks'].values())
    assert readback['scans'][-1]['no_users_gate'] and readback['gdm_state']=='active' and readback['fpga_state']=='operating'
    sys.path.insert(0,str(ROOT/'platform/qwen35/a10'));from kernel_log_gate import KernelLogGate
    old=json.loads((OUT/'preflight_02/stdout.txt').read_text(encoding='utf-8'));gate=KernelLogGate()
    assert gate.observe(old['boot_id'],old['kernel_raw'],old['kernel_sha256'])['allowed']
    kernel=gate.observe(readback['boot_id'],readback['kernel_raw']);assert kernel['allowed']
    results={name:json.loads((run/(name+'-result.json')).read_text(encoding='utf-8')) for name in ('teacher_T8','teacher_T1','natural')}
    for row in results.values():
        assert row['status']=='OK' and row['state_cleared_before_response'] and row['state_position_after_clear']==-1
        assert row['bridge']['weight_load_count']==72 and row['bridge']['hardware_done_count'] is None
    d8=run/'diag-teacher_T8';d1=run/'diag-teacher_T1'
    logits={}
    for p in sorted(d8.glob('logits-*.f32')):
        q=d1/p.name;assert q.exists();c=compare(p.read_bytes(),q.read_bytes(),.002,.0002);assert c['failures']==0
        logits[p.name]=c
    assert len(logits)==10
    # Cross-ISA CPU reference is a separate numerical comparison, never PL error.
    pc=ROOT/'evidence/model_pl_A/20261023-preboard-v1/canonical-a05-v8/diag'
    cross={}
    for p in sorted(d8.glob('logits-*.f32')):
        c=compare(p.read_bytes(),(pc/p.name).read_bytes(),.002,.0002);cross[p.name]=c
    cross_pass=all(c['failures']==0 for c in cross.values())
    if not cross_pass:
        # Step06 requires the actual SAME-BOARD S1 baseline. Preserve the added
        # cross-ISA failure separately; never relabel it a hardware/math PASS.
        independent=json.loads((OUT/'SAME_INPUT_REFERENCE.json').read_text(encoding='utf-8'))
        assert all(r['scalar_same_input']['failures']==0 for r in independent['comparisons'])
    def grouped(folder):
        m=json.loads((folder/'manifest.json').read_text(encoding='utf-8'));out={}
        for record in m['projections']:
            key=record['id'];row=out.setdefault(key,dict(input=b'',output=b'',T=0,N=record['N'],K=record['K']))
            row['input']+=(folder/record['input']).read_bytes();row['output']+=(folder/record['output']).read_bytes();row['T']+=record['T']
        return out
    a=grouped(d8);b=grouped(d1);assert set(a)==set(b) and len(a)==12
    projections={}
    for name,row in a.items():
        assert row['T']==b[name]['T']==10
        x=compare(row['input'],b[name]['input'],.002,.0002)
        y=compare(row['output'],b[name]['output'],1e-4,1e-5)
        assert x['failures']==y['failures']==0
        projections[name]=dict(input=x,output=y,N=row['N'],K=row['K'],T_total=row['T'])
    state8=d8/'hybrid-state.bin';state1=d1/'hybrid-state.bin'
    assert state8.read_bytes()==state1.read_bytes(),'same-board mixed states differ between chunks'
    observations=json.loads((run/'observations.json').read_text(encoding='utf-8'));health=json.loads((run/'health.json').read_text(encoding='utf-8'))
    ready=json.loads((run/'ready.json').read_text(encoding='utf-8'))
    rss=[fields(x['status']).get('VmRSS',0) for x in observations]
    pss=[fields(x['smaps_rollup']).get('Pss',0) for x in observations]
    high=[fields(x['status']).get('VmHWM',0) for x in observations]+[ready['peak_rss_kib']]+[x['peak_rss_kib'] for x in results.values()]
    available=min(x['memory_kib']['MemAvailable'] for x in health);cma=min(x['memory_kib']['CmaFree'] for x in health)
    temperature=max(t for x in health for t in x['temperatures_mC'])
    budget=json.loads((ROOT/'evidence/model_pl_A/20261023-preboard-v1/RESOURCE_CALL_BUDGET.json').read_text(encoding='utf-8'))
    admission={}
    for p in budget['profiles']:
        extra=(p['explicit_bo_limit_bytes']+1023)//1024
        admission[p['scope']]=dict(explicit_BO_charge_bytes=p['explicit_bo_limit_bytes'],
            available_after_conservative_extra_kib=available-extra,cma_after_extra_kib=cma-extra,
            reserve_check=(available-extra>=1048576+65536 and cma-extra>=32768+65536),
            status='OBSERVATION_CAPACITY_ONLY_REQUIRE_FRESH_BO_ADDRESS_ALLOCATION_GATES',actual_BO_allocation='NOT_TESTED')
    # Keep the initial failed capacity scenario; never erase its low-CMA sample.
    initial_admission=admission
    rb2=json.loads((OUT/'resource_readback_01/stdout.txt').read_text(encoding='utf-8'))
    tar2=OUT/'readback-v2.tar.gz'
    assert sha(tar2)==rb2['package']['sha256'] and tar2.stat().st_size==rb2['package']['bytes']
    with tarfile.open(tar2,'r:gz') as t:
        members=t.getmembers();assert len({m.name for m in members})==len(members)
        data={}
        for m in members:
            assert m.isfile() and not Path(m.name).is_absolute() and '..' not in Path(m.name).parts
            data[m.name]=t.extractfile(m).read()
    def j2(n):return json.loads(data[n])
    assert j2('manager-v2-exit.json')['exit_code']==j2('run-v2/result.json')['worker_exit_code']==0
    assert j2('run-v2/result.json')['hardware_submissions']==0
    assert j2('run-v2/worker-identity.json')['binary_sha256']==json.loads((run/'worker-identity.json').read_text(encoding='utf-8'))['binary_sha256']
    assert j2('run-v2/worker-identity.json')['argv']==json.loads((run/'worker-identity.json').read_text(encoding='utf-8'))['argv']
    case2=j2('run-v2/teacher_T8-result.json')
    assert case2['status']=='OK' and case2['state_cleared_before_response'] and case2['state_position_after_clear']==-1
    assert case2['bridge']['weight_load_count']==72
    assert not rb2['active_lease_exists'] and not rb2['module_present'] and not any(rb2['locks'].values())
    assert rb2['scans'][-1]['no_users_gate'] and rb2['gdm_state']=='active' and rb2['fpga_state']=='operating'
    kernel2=gate.observe(rb2['boot_id'],rb2['kernel_raw']);assert kernel2['allowed']
    h2=j2('run-v2/health.json');a2=min(x['memory_kib']['MemAvailable'] for x in h2);c2=min(x['memory_kib']['CmaFree'] for x in h2)
    admission={}
    for p in budget['profiles']:
        extra=(p['explicit_bo_limit_bytes']+1023)//1024
        admission[p['scope']]=dict(explicit_BO_charge_bytes=p['explicit_bo_limit_bytes'],
            available_after_conservative_extra_kib=a2-extra,cma_after_extra_kib=c2-extra,
            reserve_check=(a2-extra>=1048576+65536 and c2-extra>=32768+65536),actual_BO_allocation='NOT_TESTED',
            status='CONDITIONAL_CAPACITY_ONLY_FRESH_BO_ADDRESS_AND_LIVE_RESOURCE_GATES_REQUIRED')
    assert all(x['reserve_check'] for x in admission.values())
    resource_v2=dict(min_MemAvailable_kib=a2,min_CmaFree_kib=c2,health_samples=len(h2),
        max_temperature_mC=max(z for x in h2 for z in x['temperatures_mC']),
        archive_cache_review=j2('archive-cache-review-v2.json'),kernel_gate=kernel2,
        scope='Same binary and args, teacher_T8 only, diagnostic dumps disabled; not a repeat of all v1 cases or PL allocation')
    audit=dict(status='PASS_STEP06_BOARD_S1_WITH_CROSS_ISA_LIMITATION',physical_domain='BOARD',
        boot_id=readback['boot_id'],kernel=readback['kernel'],worker_exit_code=0,manager_exit_code=0,
        model='Qwen/Qwen3.5-0.8B',CPU_math='S1_W4A8_ALL_72_OTHER_OPS_CPU',
        same_board_logits=logits,same_board_projections=projections,
        mixed_state=dict(bit_exact=True,bytes=state8.stat().st_size,sha256=sha(state8)),
        cross_PC_ARM_logits=cross,cross_ISA_graph_status='PASS' if cross_pass else 'FAIL_RETAINED_DIFFERENT_CPU_INPUTS_QUANTIZATION_SENSITIVE',
        cross_ISA_not_a_PL_implementation_comparison=True,
        natural=dict(text=results['natural']['text'],eos=results['natural']['eos'],
            prompt_tokens=results['natural']['prompt_tokens'],output_tokens=results['natural']['output_tokens'],
            note='one synthetic functional sample; not clinical or statistical quality acceptance'),
        resource=dict(observed_RSS_peak_kib=max(rss),RSS_high_water_kib=max(high),observed_PSS_peak_kib=max(pss),
            min_MemAvailable_kib=available,min_CmaFree_kib=cma,max_temperature_mC=temperature,
            explicit_model_PL_BO_bytes=None,implicit_XRT_bytes=None,physical_peak_bytes=None,
            accounting='RSS/PSS, CMA and hypothetical additional BO are separate views; do not sum overlapping memory'),
        initial_admission=initial_admission,resource_v2=resource_v2,admission=admission,
        capacity_condition='Task deployment archive cache released; fresh resource gate mandatory; full PL BO allocation NOT_TESTED',
        hardware_submissions=0,hardware_global_count=None,PL_numeric='NOT_TESTED',board_speedup=None,
        independent_postcheck=dict(no_devices=True,no_lease=True,no_locks=True,default_PL_operating=True,GDM_active=True,kernel_gate=kernel),
        tolerances=dict(operator_atol=1e-4,operator_rtol=1e-5,graph_atol=.002,graph_rtol=.0002))
    save(OUT/'AUDIT.json',audit)
    print(json.dumps(dict(status=audit['status'],T8_T1_logits_bit_exact=all(c['bit_exact'] for c in logits.values()),
        RSS_HWM_kib=max(high),min_available_kib=available,min_cma_kib=cma,max_temp_mC=temperature,natural=audit['natural'])))


if __name__=='__main__':main()
