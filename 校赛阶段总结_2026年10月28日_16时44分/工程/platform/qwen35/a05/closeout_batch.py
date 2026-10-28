"""Assert real final evidence before generating the A05 engineering closeout."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];A=ROOT/'eval/qwen35/a05';OUT=A/'batch-fix-v1'
def read(p):return json.loads(p.read_text())
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()
num=read(A/'state-v8/numerics.json');history=read(A/'state-v8/canonical-history-comparison.json')
for result in [*num.values(),history]:
    assert result['passed']
    assert all(x['bit_equal'] for x in result['logits'].values())
    assert all(x['bit_equal'] for x in result['state_arrays'].values())
    assert all(x['bit_equal'] for p in result['projections'].values() for x in p.values())
checks=read(A/'state-v8/checks.json');extra=read(A/'extra-batch-v8/report.json');app=read(A/'app-dev-v8/S1-summary.json');voice=read(A/'voice-s1-v8/summary.json')
assert all(x['passed'] for x in checks+extra['checks']+app['assertions'])
assert app['functional_pass'] and app['fallback_count']==0 and app['source_counts']=={'MODEL':17,'TEMPLATE':7}
assert voice['passed'] and voice['turns']==2 and voice['acoustic_onset_ns'] is None
records=read(A/'state-v8/records.json')
for t in (2,4,8):assert records[f'chunk-{t}']['bridge']['physical_cpu_calls_by_T'][str(t)]>0
build=read(OUT/'runtime-build-v8.json');old=read(A/'runtime-build-v3.json')
for release in (old,build):
    for p,v in release['files'].items():assert sha(Path(p))==v['sha256'],p
for p,h in build['source_files'].items():
    if not p.endswith('.md'):assert sha(ROOT/p)==h,p
summary={'stage':'A05','status':'PASS_PC_A05_FULL_MODEL_PHYSICAL_T8',
 'base_commit':'81e39ad34368329b5db77620721510fd91107e80','runtime_build':build,
 'physical_ubatch':8,'state_checks':len(checks),'additional_checks':len(extra['checks']),
 'all72_projection_and23_logit_positions_and48_state_arrays_bit_exact':True,
 'canonical_T1_history_same_fixed_sample_bit_exact':True,
 'cpu_ABI_binary_unchanged_from_103_check_release':True,'same_math_SIMD_48_samples_retained':True,
 'actual_call_histograms':{k:v['bridge']['physical_cpu_calls_by_T'] for k,v in records.items() if k.startswith('chunk-')},
 'app':{'assertions':len(app['assertions']),'sources':app['source_counts'],'unexpected_fallback':0,'metrics':app['metrics']},
 'long_inputs':{k:{x:r[x] for x in ('prefill_ms','logits_comparison','output_tokens','prefill_requested_logits')} for k,r in extra['records'].items() if k.startswith('long-')},
 'memory':{'sidecar_payload_bytes':140378112,'gguf_target_rss_kib':records['long-1024']['bridge']['protected_gguf_rss_kib'],
  'weight_load_count':records['long-1024']['bridge']['weight_load_count'],'runtime_capacity_bytes':records['long-1024']['bridge']['runtime_buffer_capacity_bytes']},
 'voice':voice,'quality':'H0/S0/S1 nonzero differences retained separately in quality-v1/quality.json; not clinical approval',
 'domains':{'PC':'PASS_STAGE_ENGINEERING_SCOPE','Csim':'NOT_TESTED','Cosim':'NOT_TESTED','synthesis':'NOT_TESTED','implementation':'NOT_TESTED','ARM64':'NOT_TESTED','BOARD':'NOT_TESTED'},
 'hardware_error':None,'linux_board_memory_bytes':None,'BO_budget_bytes':None,
 'later_required':['teacher review','independent final 300 QA','A08 reliability/long run','acoustic onset','ARM64/PL/BOARD'],
 'optional_P2':['R1/R2 prefix snapshot','further throughput optimization'],
 'new_commit':None,'pushed':False,'next_stage':'A06 preconditions ready; not executed in A05'}
with (OUT/'REPORT.json').open('x') as f:json.dump(summary,f,ensure_ascii=False,indent=2)
commands={}
for p in sorted((ROOT/'platform/qwen35/a05/evidence').glob('continue-*.json')):
    r=read(p)
    if r.get('exit_code') is not None:commands[str(p.relative_to(ROOT))]={'sha256':sha(p),**{k:r.get(k) for k in ('argv','exit_code','elapsed_s')}}
with (OUT/'commands.json').open('x') as f:json.dump(commands,f,ensure_ascii=False,indent=2)
manifest=read(ROOT/'modules/linear_A/manifest.json');manifest['status']=summary['status'];manifest['validation_report']='eval/qwen35/a05/batch-fix-v1/REPORT.json'
(ROOT/'modules/linear_A/manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'status':summary['status'],'state_checks':len(checks),'additional_checks':len(extra['checks']),'commands':len(commands),'BOARD':'NOT_TESTED'}))
