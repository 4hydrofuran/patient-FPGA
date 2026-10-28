"""Independent offline comparison of board Y, complete service timing and release."""
import argparse,hashlib,json,statistics,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_bytes())
def need(ok,reason):
    if not ok:raise RuntimeError(reason)
def main(bundle,capture,out):
    sys.path.insert(0,str(bundle))
    from mlp_engine import comparison,resources
    from mlp_policy import verify_bundle
    from compute_result import validate_result
    from kernel_log_gate import diagnostics
    man=verify_bundle(bundle,sha(bundle/'manifest.json'));plan=read(bundle/'vectors/manifest.json')
    result=read(capture/'worker-result.json');state=read(capture/'state.json')
    keys=('boot_id','window_id','manager_pid','lease_sha256','request_sha256','plan_sha256','worker_baseline_sha256','protocol','inherited_device_lock_fd','manager_start_ticks')
    validate_result(result,{k:result[k] for k in keys},result['worker_pid'])
    need(result['status']=='NORMAL_CLOSED_A11_MINIMAL','board matrix failed; preserve partial result')
    need(read(capture/'host-exit.json')['exit_code']==0,'manager did not exit normally')
    need(sha(bundle/'manifest.json')==read(capture/'review.json')['bundle_sha256'],'executed package differs')
    need(sha(capture/'review.json')==result['request_sha256'] and
         sha(capture/'worker-baseline.json')==result['worker_baseline_sha256'] and
         result['plan_sha256']==sha(bundle/'vectors/manifest.json'),'identity hash chain differs')
    need(read(capture/'launcher-pid.json')['pid']==result['manager_pid'],'manager PID differs')
    need(read(capture/'trial-profile.json')['bo_charge_alignment']==8192,'allocation profile differs')
    need(read(capture/'fetch_receipt.json')['exit_code']==0,'capture failed')
    need(state['boot_id']==result['boot_id'] and state['kernel']=='6.8.12-a10irq2','platform differs')
    scan=state['scan']
    need(scan['scan_complete'] and not scan['scan_issues'] and not scan['device_holders'] and not scan['device_mappings'],'fresh release scan failed')
    need(not state['zocl'] and not state['active_lease_exists'] and not any(state['locks'].values()),'resources retained')
    need(state['overlays']=={'k26-starter-kits_image_1':'applied'} and state['fpga']=='operating' and state['gdm']=='active','default environment differs')
    need(not {result['worker_pid'],result['manager_pid']} & {p['pid'] for p in scan['inspected_processes']},'process not exited')
    life=[json.loads(s) for s in (capture/'lifecycle.jsonl').read_text().splitlines()]
    reaped=[r for r in life if r['event']=='WORKER_REAPED']
    release=[r for r in life if r['event']=='RELEASE_PRECHECK_PASSED_NOT_UNLOADED']
    need(len(reaped)==len(release)==1 and reaped[0]['worker_pid']==result['worker_pid'] and
         reaped[0]['exit_code']==0 and release[0]['module_refcount']==0,'normal release proof absent')
    need(reaped[0]['monotonic_ns']<release[0]['monotonic_ns'],'release preceded exit')
    gates=[r for r in life if r['event']=='KERNEL_LOG_GATE'];need(gates and all(g['allowed'] for g in gates),'kernel gate rejected')
    kernel=(capture/'kernel.raw.txt').read_bytes().decode();previous=gates[-1]['raw_log']
    need(kernel.startswith(previous) and not diagnostics(kernel[len(previous):]),'post-window kernel diagnostic')
    worker=[json.loads(s) for s in (capture/'worker.stdout.jsonl').read_text().splitlines()]
    invalid=[r for r in worker if r['event']=='INVALID_PARAMETERS_REJECTED_NO_SUBMISSION']
    need(len(invalid)==1 and invalid[0]['status_code']==1 and invalid[0]['report']['output_consumable'] is False,'invalid parameter evidence missing')
    comparisons=[];max_explicit=0;first_io=None
    for expected,row in zip(plan['schedule'],result['calls']):
        need(all(row[k]==v for k,v in expected.items()),'schedule changed')
        p=capture/f"actual-job-{row['job_id']:02}.f32";need(sha(p)==row['actual_output_sha256'],'actual Y hash differs')
        case=plan['cases'][row['case']];gold=bundle/'vectors/pc_reference'/row['case']/'y.bin'
        need(sha(gold)==case['golden']['y.bin']['sha256'],'reference changed')
        cmp=comparison(p.read_bytes(),gold.read_bytes(),case['N'],case['T']);need(cmp['numeric_pass'],'independent Y comparison failed')
        comparisons.append(dict(job_id=row['job_id'],case=row['case'],**cmp))
        r=row['native_report'];need(r['execution_kind']=='FPGA_REAL' and r['no_silent_fallback'] is True and
                                  r['xclbin_sha256']==man['files']['w4a8.xclbin']['sha256'],'backend provenance differs')
        loads=next(i+1 for i,e in enumerate(result['loads']) if e['weight']==row['weight'])
        first_io=resources(r,loads,first_io);max_explicit=max(max_explicit,r['owned_bo_charged_bytes'])
    need(len(comparisons)==23 and len(list(capture.glob('actual-job-*.f32')))==23,'actual output inventory differs')
    groups=[]
    for op in ('gate','up','down'):
        weight='l00_'+op;rows=[r for r in result['calls'] if r['weight']==weight]
        load=next(r for r in result['loads'] if r['weight']==weight)
        for t in (1,8,3):
            chosen=[r for r in rows if r['T']==t];warm=[r for r in chosen if r is not rows[0]]
            groups.append(dict(operator=op,T=t,N=plan['cases'][chosen[0]['case']]['N'],K=plan['cases'][chosen[0]['case']]['K'],
                samples=len(chosen),service_ms=[r['service_ms'] for r in chosen],
                median_service_ms=statistics.median(r['service_ms'] for r in chosen),
                min_service_ms=min(r['service_ms'] for r in chosen),max_service_ms=max(r['service_ms'] for r in chosen),
                warm_samples=len(warm),warm_median_service_ms=statistics.median(r['service_ms'] for r in warm) if warm else None,
                weight_cold_total_ms=load['cold_total_ms'],weight_api_load_ms=load['api_load_ms'],
                input_quant_ms=[r['input_quant_ms'] for r in chosen],
                native_segments=[{k:v for k,v in r['native_report'].items() if k.startswith('a11_') and k.endswith('_ms')} for r in chosen]))
    result_audit=dict(status='PASS_A11_REAL_MLP_NUMERIC_SERVICE_AND_NORMAL_RELEASE_WITH_LIMITATIONS',
        A11='PASS_WITH_LIMITATIONS',A12='NOT_STARTED',boot_id=state['boot_id'],kernel=state['kernel'],window_id=result['window_id'],
        manifest_sha256=sha(bundle/'manifest.json'),contract_sha256=plan['contract_sha256'],
        real_submissions=23,real_shape_submissions=21,weights_loaded=5,invalid_T_rejected=1,
        all_fp32_numeric_pass=True,all_bit_exact=all(r['bit_exact'] for r in comparisons),
        max_abs_error=max(r['max_abs_error'] for r in comparisons),max_rel_error=max(r['max_rel_error'] for r in comparisons),
        tolerance=dict(atol=1e-4,rtol=1e-5),comparisons=comparisons,performance=groups,
        service_scope='activation quantization + native input copy/sync + submit/poll + metadata/output sync/validation + caller output copies; excludes golden/diagnostics/permits',
        explicit_bo_peak_charged_bytes=max_explicit,explicit_bo_allocations_host_counter=14,physical_bo_peak_bytes=None,
        repeated_weight_uploads=0,warm_IO_workspace_reused=True,hardware_cycles=None,measured_AXI_bytes=None,
        pure_kernel_ms=None,hardware_integer_debug='NOT_TESTED_INTERFACE_ABSENT',
        effective_PL_DDR_bandwidth=None,speedup=None,performance_p95=None,
        limitations=['No hardware integer-debug interface; FPGA FP32 Y compared independently, integer internal sums not observable.',
                     '2-3 warm repeats per shape; descriptive timing only, no p95 or long-run claim.',
                     'Submit-to-completion includes host polling; no hardware cycles or measured AXI bytes.',
                     'Timeout isolation validated on PC; deliberately hung DMA/reset not injected on board.',
                     'Current irq2 boot accepted for this window; no cold reboot/recovery or full model PL execution in this test.'],
        default_restored=True,gdm_active=True,zocl_absent=True,device_FD_VMA=[0,0],locks_held=0,active_lease_absent=True,
        worker_exit_code=0,manager_exit_code=0,post_window_new_diagnostics=0,
        readback_delay_seconds=(state['read_monotonic_ns']-life[-1]['monotonic_ns'])/1e9,
        peak_temperature_mC=max(t for r in life for t in r.get('temperatures_mC',[])))
    with out.open('x',encoding='utf-8') as f:json.dump(result_audit,f,indent=2)
    print(json.dumps({k:v for k,v in result_audit.items() if k not in ('comparisons','performance')},ensure_ascii=False))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,required=True);p.add_argument('--capture',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();main(a.bundle.resolve(),a.capture.resolve(),a.out.resolve())
