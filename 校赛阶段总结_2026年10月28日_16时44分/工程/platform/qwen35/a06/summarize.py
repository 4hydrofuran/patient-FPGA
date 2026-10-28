"""Produce scoped A06 results from actual intake and command receipts."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
E=ROOT/'evidence/A06_acceptance'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,data):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:json.dump(data,f,ensure_ascii=False,indent=2)

def main():
    audit=read(E/'static-audit.json');download=read(E/'intake-v1/download-manifest.json')
    B=ROOT/'hw/linear_B_received/B03-fdd1d656290b-20261003'
    reference_seal=read(ROOT/'eval/qwen35/a04/files.sha256.json')
    prior=read(ROOT/'eval/qwen35/a05/batch-fix-v1/files.sha256.json')
    preserve={}
    fixed=['quant/reference/w4a8.cpp','quant/reference/w4a8.hpp','quant/reference/scalar.py',
           'models/sidecar_A/qwen35-v1/manifest.json','models/model.lock.json','quant/qwen35_tensor_map.json',
           'docs/handoffs/A_A05_CLOSEOUT_20261002.md']
    for tensor in ['l00_gate','l00_down']:
        fixed += [f'models/sidecar_A/qwen35-v1/{tensor}.{ext}.bin' for ext in ['w','sw']]
    model_manifest=read(ROOT/'models/sidecar_A/qwen35-v1/manifest.json')
    for item in fixed:
        got=sha(ROOT/item);expected=prior.get(item,reference_seal.get(item))
        if expected is None and item.endswith('.bin'):
            expected=next(v['sha256'] for t in model_manifest['entries'] for v in t['files'].values() if v['file']==Path(item).name)
        if expected is None:raise ValueError('no prior identity: '+item)
        preserve[item]={'sha256':got,'expected_sha256':expected,'status':'MATCH' if got==expected else 'MISMATCH'}
    if any(v['status']!='MATCH' for v in preserve.values()):raise RuntimeError('A04/A05 input identity changed')
    save(E/'A04_A05_input_identity.json',preserve)
    local={}
    for v in ('baseline','reuse','double'):
        receipt=read(E/f'local-tests-v1/{v}-pc.json')
        cases=[json.loads(s[7:]) for s in receipt['stdout'].splitlines() if s.startswith('RESULT ')]
        summary=[json.loads(s[8:]) for s in receipt['stdout'].splitlines() if s.startswith('SUMMARY ')][0]
        if receipt['exit_code']!=0 or summary['status']!='PASS' or len(cases)!=61:raise RuntimeError('PC test failed')
        csim=read(E/f'local-tests-v1/{v}-csim.json')
        local[v]={'PC':summary,'cases':cases,'INT32_checks':sum(c.get('int32_compared',0) for c in cases),
                  'Csim_exit_code':csim['exit_code'],'Csim_status':'BLOCKED_LICENSE_BEFORE_SIMULATION',
                  'PC_receipt':f'evidence/A06_acceptance/local-tests-v1/{v}-pc.json',
                  'Csim_receipt':f'evidence/A06_acceptance/local-tests-v1/{v}-csim.json'}
    source_inputs={}
    for p in sorted((ROOT/'platform/qwen35/a06').glob('*')):
        if p.is_file():source_inputs[str(p.relative_to(ROOT))]=sha(p)
    source_inputs.update({p:v['sha256'] for p,v in preserve.items()})
    save(E/'test-inputs.sha256.json',source_inputs)
    license_info=json.loads(read(E/'commands/license-diagnostic.json')['stdout'])
    matrix=[
      {'item':'A04/A05 prerequisites','status':'PASS_SCOPED_IDENTITY','evidence':'A04_A05_input_identity.json'},
      {'item':'B source/header/config received','status':'PASS_STATIC_IDENTITY','evidence':'static-audit.json'},
      {'item':'frozen final B candidate','status':'MISSING_B_HAS_NOT_SELECTED','evidence':'B README/THREE_SCHEMES_STATUS'},
      {'item':'actual XO and embedded kernel.xml','status':'MISSING','evidence':'intake-v1/remote-tree.json'},
      {'item':'loose baseline XML/header argument map','status':'PASS_PROVISIONAL_NOT_XO_VERIFIED','evidence':'interface-map.candidate.json'},
      {'item':'A independent PC all three variants','status':'PASS_61_EACH','evidence':'local-tests-v1/*-pc.json'},
      {'item':'A local required Csim','status':'BLOCKED_LICENSE_BEFORE_SIMULATION','evidence':'local-tests-v1/*-csim.json'},
      {'item':'B Csim target shapes T1..8','status':'REPORTED_PASS_SOURCE_MATCH_TESTBENCH_HISTORY_GAPS','evidence':'static-audit.json'},
      {'item':'baseline Cosim real T1 both and T8 both','status':'B_REPORTS_PASS_NOT_FULLY_REPLAYABLE_RAW_DATA_MISSING','evidence':'static-audit.json'},
      {'item':'reuse/double required Cosim','status':'NOT_COMPLETED_BY_B','evidence':'B README'},
      {'item':'random backpressure/FIFO occupancy','status':'NOT_TESTED','evidence':'B THREE_SCHEMES_STATUS'},
      {'item':'2026.1/part/150MHz constraints','status':'VERIFIED_CONFIG_AND_LOGS_NOT_TIMING_CLOSURE','evidence':'B config/synth logs'},
      {'item':'implementation/ARM64/BOARD','status':'NOT_TESTED','evidence':None}]
    save(E/'acceptance-matrix.json',matrix)
    report={'stage':'A06','status':'NOT_ACCEPTED_DELIVERY_AND_LOCAL_LICENSE_BLOCKED','provider':'B',
            'source_commit':download['source_commit'],'received_files':len(download['files']),
            'received_bytes':sum(v['size'] for v in download['files']),'local_tests':local,
            'domains':{'PC':'PASS_183_CASES_INDEPENDENT_A04_ORACLE','Csim':'BLOCKED_LICENSE_NOT_RUN',
                       'Cosim':'A_NOT_TESTED_B_BASELINE_REPORTED_PASS_INCOMPLETE_RAW_DELIVERY',
                       'synthesis':'A_NOT_TESTED_B_LOGS_RECEIVED_XO_MISSING',
                       'implementation':'NOT_TESTED','aarch64_build':'NOT_TESTED','BOARD':'NOT_TESTED'},
            'hardware_error':None,'BO_budget_bytes':None,'license_diagnostic':license_info,
            'acceptance_matrix':'evidence/A06_acceptance/acceptance-matrix.json',
            'next':'B supplies a selected same-version artifact/traceable raw evidence; owner fixes official license; A reruns Csim and XO audit before A07 link',
            'no_new_HLS_kernel':True,'B_sources_edited':False,'remote_writes':False,'commit_created':False,
            'assistant_settings':{'actual':'unknown','settings_changed':False,'stage_requested_effort':'High'}}
    save(E/'REPORT.json',report)
    kernel_source={'provider':'B','status':'NOT_ACCEPTED','accepted':False,'frozen':False,
                   'reason':'No selected final kernel; no actual XO; local Csim license blocked; incomplete raw RTL evidence',
                   'source_commit':download['source_commit'],'received_directory':str(B.relative_to(ROOT)),
                   'selected_variant':None,'xo_path':None,'xo_sha256':None,'embedded_metadata_sha256':None,
                   'candidates':{k:{key:value for key,value in v.items() if key in ['source','source_sha256','header','header_sha256','config','config_sha256','claimed_xo_sha256']} for k,v in audit['variants'].items()},
                   'interface_candidate':'evidence/A06_acceptance/interface-map.candidate.json',
                   'acceptance_report':'evidence/A06_acceptance/REPORT.json',
                   'production_or_A07_link_allowed':False,'BOARD':'NOT_TESTED'}
    save(ROOT/'hw/linear_A/KERNEL_SOURCE.json',kernel_source)
    print(json.dumps({'status':report['status'],'PC_cases':sum(v['PC']['cases'] for v in local.values()),
                      'PC_checks':sum(v['PC']['checks'] for v in local.values()),
                      'INT32_per_variant':local['baseline']['INT32_checks'],'preserved_inputs':len(preserve)}))
if __name__=='__main__':main()
