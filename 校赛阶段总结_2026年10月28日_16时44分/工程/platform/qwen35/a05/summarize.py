"""Evidence aggregation only; no test result is inferred from a report title."""
import hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'eval/qwen35/a05'
def read(p):return json.loads((ROOT/p).read_text(encoding='utf-8'))
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()
abi=read('eval/qwen35/a05/abi-v4/summary.json');state=read('eval/qwen35/a05/state-v2/numerics.json');checks=read('eval/qwen35/a05/state-v2/checks.json');native=read('eval/qwen35/a05/final-native-v1/summary.json');app=read('eval/qwen35/a05/app-dev-v3/S1-summary.json');voice=read('eval/qwen35/a05/voice-s1-v1/summary.json');quality=read('eval/qwen35/a05/quality-v1/quality.json')
assert abi['passed'] and native['passed'] and all(v['passed'] for v in state.values()) and all(v['passed'] for v in checks)
assert app['functional_pass'] and not app['warnings'] and app['source_counts']=={'MODEL':17,'TEMPLATE':7} and voice['passed']
logs=[]
for p in sorted((ROOT/'platform/qwen35/a05/evidence').glob('*.json')):
    v=json.loads(p.read_text())
    if v.get('status')=='RESERVED_NOT_COMPLETED' and any(str(x).endswith('/summarize.py') for x in v.get('argv',[])):continue
    assert v.get('status')!='RESERVED_NOT_COMPLETED',str(p)
    logs.append({'file':str(p.relative_to(ROOT)),'argv':v.get('argv'),'exit_code':v.get('exit_code'),'sha256':sha(p)})
with (OUT/'commands.json').open('x') as f:json.dump(logs,f,ensure_ascii=False,indent=2)
ready=native['ready'];sample=native['rows'][0];br=sample['bridge']
known_hwm=[sample['peak_rss_kib'],ready['peak_rss_kib']]
for group in sample['memory'].values():
    for line in group:
        if line.startswith(('VmHWM:','VmRSS:','Rss:')):known_hwm.append(int(line.split()[1]))
r={'stage':'A05','status':'PARTIAL_PC_S1_WORKING_PHYSICAL_T2_T4_T8_NOT_ACCEPTED','default_cpu_path_ready':True,'full_physical_batch_acceptance':False,
   'domains':{'PC':'PASS_CANONICAL_T1_BASELINE_WITH_PHYSICAL_BATCH_LIMITATION','Csim':'NOT_TESTED','Cosim':'NOT_TESTED','synthesis':'NOT_TESTED','implementation':'NOT_TESTED','aarch64_build':'NOT_TESTED','BOARD':'NOT_TESTED'},
   'model_revision':'2fc06364715b967f1860aea9cf38778875588b17','llama_commit':'81e39ad34368329b5db77620721510fd91107e80','base_commit':'ed9df6c7152c908d512ecd1f871583182823e1eb','new_commit':None,
   'abi_checks':len(abi['checks']),'abi_pass':abi['passed'],'native_checks':native['checks'],'state_checks':len(checks),'scalar_optimized_full_model_bit_exact':all(x['bit_equal'] for x in state['scalar']['logits'].values()),
   'external_chunk_schedule':[1,2,4,8,256],'physical_ubatch':1,'state_arrays_compared_per_variant':len(state['scalar']['state_arrays']),'teacher_forced_logits_positions':len(state['scalar']['logits']),
   'all_72_projection_calls_verified':True,'operator_simd_evidence':'platform/qwen35/a05/evidence/simd-real-v2.json','R0':'CLEAR_ALL_REPLAY_AND_CLEAR_BEFORE_RETURN','R1':'OPTIONAL_DISABLED_NOT_VERIFIED',
   'sidecar_bytes':br['owned_weight_bytes'],'sidecar_manifest_sha256':'cdb2a04dbd95d426ea8967cda0adb219a769d3630107a2af72d6ddf2d5285688',
   'memory':{'protected_old_mlp_bytes':br['protected_gguf_vma_bytes'],'protected_old_mlp_rss_kib':br['protected_gguf_rss_kib'],'old_mlp_boundary_bytes':sum(x['boundary_bytes_not_discarded'] for x in br['gguf_target_ranges'].values()),'native_workspace_capacity':br['workspace_capacity_bytes'],'bridge_workspace_capacity':br['runtime_buffer_capacity_bytes'],'other_cpu_repack_mib_from_log':90.88,'max_observed_process_kib':max(known_hwm),'startup_transient_old_pages':'NOT_ZERO; peak includes load transient','system_file_cache':'NOT_CLEARED_NOT_PROCESS_RESIDENCY','board_BO_budget':None},
   'example_pc_timing':{k:ready[k] for k in ('model_load_ms','sidecar_load_ms','worker_ready_ms')},'example_pc_timing_note':'PC smoke with other diagnostic/development load; not a benchmark confidence interval or KV260 speed',
   'dev':{k:app[k] for k in ('functional_pass','source_counts','fallback_rate','warnings','metrics','candidate_failure_buckets')},'dev_old_fallback_rate':2/17,'checker_changes':'two complete relation surface forms only; 36 historical tests + 3 methods/negative subcases',
   'audio':voice,'quantization_quality':quality,'hardware_error':None,'clinical_review':'PENDING','heldout_authored':0,'heldout_planned':300,
   'known_raw_label_erratum':'quality-v1 H0 worker uses F16 file explicitly recorded in its wire argv/config. The retained v3 scope=none native header labels all non-hook runs S0_Q4_K_M; use quality.json H0/F16 input identity, not that legacy label. S1 default header is correct.',
   'remaining':['Full-model physical T=2/4/8 state/logits equivalence failed on the retained Q4 variant. Canonical physical T1 is the explicit safe implementation, not evidence that larger physical batches passed.','F16 non-MLP diagnostic is separate and never adopted automatically.','R1 snapshots optional; no state reuse claimed.','Broader quality/teacher review/independent 300 final questions and acoustic timings remain.','No PL/XRT/ARM/board acceptance.'],
   'next_action':'Resolve the physical-batch discrepancy, or obtain explicit acceptance of the canonical T1 scope before calling full A05 complete. Do not silently advance to BOARD.'}
with (OUT/'REPORT.json').open('x') as f:json.dump(r,f,ensure_ascii=False,indent=2)
print(json.dumps({'status':r['status'],'abi_checks':len(abi['checks']),'voice_passed':voice['passed'],'max_observed_process_kib':max(known_hwm)},ensure_ascii=False))
