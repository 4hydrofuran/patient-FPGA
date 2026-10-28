"""Collect immutable build identity/logs, summarize completed actual runs."""
import argparse,hashlib,json,shutil,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'eval/qwen35/a04'
def read(p):return json.loads((ROOT/p).read_text())
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--summary-only',action='store_true');parser.add_argument('--report',default='REPORT.json');parser.add_argument('--load-profile',default='load-profile.json');args=parser.parse_args()
    build=OUT/'build'
    if not args.summary_only:
        build.mkdir(exist_ok=False)
        for name in ('build-run','capture-build-run'):
            log=read('platform/qwen35/a04/evidence/'+name+'.json');job=json.loads(log['stdout']);assert job['exit_code']==0
            for stream in ('stdout','stderr'):shutil.copy2(Path(job['cwd'])/(stream+'.txt'),build/(name+'-'+stream+'.txt'))
        shutil.copy2('/home/member-a/qwen35-a04/build-v1/vectorization.txt',build/'vectorization.txt')
    assert (build/'vectorization.txt').read_bytes()==Path('/home/member-a/qwen35-a04/build-v1/vectorization.txt').read_bytes()
    names=['w4ref','w4ref-sanitize','capture'];binaries={n:sha(Path('/home/member-a/qwen35-a04/build-v1')/n) for n in names}
    old=read('eval/qwen35/design_import/build/identity.json')['files']
    assert all(sha(Path(p))==h for p,h in old.items()),'Existing runtime binary changed'
    vector=read('eval/qwen35/a04/vectors-v1/summary.json');san=read('eval/qwen35/a04/vectors-sanitize-v1/summary.json')
    cross=read('eval/qwen35/a04/export-cross-v1/summary.json');real=read('eval/qwen35/a04/real-v1/summary.json');quality=read('eval/qwen35/a04/quality-diagnostics-v1/summary.json')
    assert all(r['passed'] for r in (vector,san,cross,real)) and real['count']==48
    loader=read('platform/qwen35/a04/evidence/loader-tests-v1.json');assert loader['exit_code']==0 and 'Ran 6 tests' in loader['stderr']
    metrics={}
    for model in ('H0_F16','S0_Q4'):
        rows=[r for r in real['rows'] if r['input_model']==model]
        metrics[model]={'quantization_nrmse_min':min(r['raw_FP32_vs_W4A8_same_input']['nrmse'] for r in rows),
                        'quantization_nrmse_max':max(r['raw_FP32_vs_W4A8_same_input']['nrmse'] for r in rows),
                        'max_abs_quantization_error':max(r['raw_FP32_vs_W4A8_same_input']['max_abs'] for r in rows)}
    timing={}
    for t in (1,8):
        rows=[r for r in real['rows'] if r['T']==t];timing[str(t)]={key:{'min':min(r['cpp_metrics'][key] for r in rows),'max':max(r['cpp_metrics'][key] for r in rows)} for key in ('scalar_ms','tiled_ms','quant_ms','optimized_including_activation_quant_ms','load_validate_quant_ms')}
    commands=[]
    for p in sorted((ROOT/'platform/qwen35/a04/evidence').glob('*.json')):
        log=json.loads(p.read_text())
        if log.get('exit_code') is not None:commands.append({'log':p.relative_to(ROOT).as_posix(),'argv':log['argv'],'exit_code':log['exit_code']})
    result={'stage':'A04','status':'PASS_PC_A04_NUMERICS_FULL_GRAPH_PENDING_A05',
        'domains':{'PC':'PASS','Csim':'NOT_TESTED','Cosim':'NOT_TESTED','synthesis':'NOT_TESTED','implementation':'NOT_TESTED','cross_build':'NOT_TESTED','BOARD':'NOT_TESTED'},
        'vector_assertions':len(vector['checks']),'same_vectors_under_ASAN_UBSAN':len(san['checks']),'loader_test_methods':6,
        'independent_CPP_export_matrices':len(cross['checks']),'repro_manifest_identical':cross['manifests_identical'],
        'payload_bytes':140378112,'manifest_bytes':cross['manifest_bytes'],'manifest_sha256':sha(ROOT/'models/sidecar_A/qwen35-v1/manifest.json'),
        'real_projection_count':48,'integer_bit_exact':all(r['integer_bit_exact'] for r in real['rows']),
        'fp32_bit_exact':all(r['float_bit_exact'] for r in real['rows']),
        'cpp_oracle_max_abs':max(r['cpp_vs_independent_reference']['max_abs'] for r in real['rows']),
        'frozen_tolerance':{'atol':1e-4,'rtol':1e-5},'quantization_diagnostics':metrics,
        'max_W4_only_nrmse':max(r['W4_only_same_input']['nrmse'] for r in quality['rows']),
        'max_A8_only_nrmse':max(r['A8_only_same_weight']['nrmse'] for r in quality['rows']),
        'timing_ms':timing,'timing_scope':'Single diagnostics per captured projection; one CPU thread -O3, no p95/speedup/board claim; load/validation separate. Python oracle never performance baseline.',
        'export_profile':json.loads(read('platform/qwen35/a04/evidence/export-v1.json')['stdout']),
        'load_profile':read('eval/qwen35/a04/'+args.load_profile),'binaries':binaries,'existing_runtime_identity_preserved':True,
        'H0_to_S0':'24 actual capture comparisons, includes upstream differences; quality-diagnostics-v1',
        'S0_to_S1':'Local projection only; whole graph logits/task quality NOT_TESTED_A05','S1_to_S2_error':None,
        'commands':commands,'new_commit':None,'remote_push':False,
        'codex':{'requested':'GPT-6 Astra / Extra High / Standard','actual':'unknown','changed':False},
        'failures_retained':['Initial test launch: Python stdlib platform name collision, exit1, fixed explicit script entry; no vector executed on failed launch'],
        'next':'A05 only after explicit continuation; no ABI/graph backend replacement in A04'}
    with (OUT/args.report).open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps({k:result[k] for k in ('status','payload_bytes','real_projection_count','integer_bit_exact','fp32_bit_exact','quantization_diagnostics','max_W4_only_nrmse','max_A8_only_nrmse')}))
if __name__=='__main__':main()
