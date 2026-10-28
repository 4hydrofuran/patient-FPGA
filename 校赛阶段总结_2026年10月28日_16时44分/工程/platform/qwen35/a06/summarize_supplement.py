"""Generate a non-accepting machine report from actual incremental evidence."""
import json,re
from pathlib import Path
R=Path(__file__).resolve().parents[3];E=R/'evidence/A06_acceptance/supplement-v1'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def main():
 s=read(E/'static.json');r=read(E/'a04-rtl/REPORT.json');f=read(E/'final-checks-v2/REPORT.json');o=read(E/'tests/outcome.json')
 pc=read(E/'tests/pc.json');summary=json.loads(re.search(r'^SUMMARY (\{.*\})$',pc['stdout'],re.M).group(1))
 assert pc['exit_code']==0 and summary['cases']==61 and summary['checks']==2800022
 assert len(r['transactions'])==66 and len(r['vectors'])==382
 assert read(E/'commands/archive-tests-v3.json')['exit_code']==0
 csim=read(E/'tests/csim.json');assert csim['exit_code']==1 and 'valid license was not found' in csim['stdout']
 result={'status':'PARTIAL_LOCAL_CSIM_LICENSE_BLOCKED','accepted':False,'frozen':False,
         'release_tag':'b03-a06-supplement-20261003','source_commit':'e227297ee1bb0bdf542fc81761642b23639e15c0',
         'provider':'B','selected_variant':'double','xo_sha256':s['xo']['sha256'],
         'embedded_metadata_sha256':s['xo']['embedded_metadata_sha256'],
         'source_sha256':s['candidate']['artifact']['source_sha256'],'archive_files':s['inventory_files'],
         'exact_input_receipts':len(s['receipts']),'PC':summary,'A_local_Csim':'BLOCKED_LICENSE_BEFORE_NUMERICAL_RUN',
         'B_Csim':'SAME_VERSION_FULL50_AUDITED_T1_TO_T8_BOTH_REAL_SHAPES',
         'A_archived_RTL_replay':{'transactions':66,'max_abs_error':max(v['max_abs_error'] for v in r['transactions']),
             'reference_partial_comparisons':sum(v['reference_int32_compared'] for v in r['transactions']),
             'rtl_internal_partials_observed':False,'native_pass_transactions':65,'native_failed_postcheck_recovered_transactions':1},
         'negative_probes':f['A04_negative_probes'],'strict_provider_command_exit':o['provider_replay'],
         'vectors':{'total':382,'byte_exact':r['byte_exact_vectors'],'json_CRLF_LF_only':sum(v['only_CRLF_LF'] for v in f['json_format_differences'])},
         'new_RTL_run':'NOT_TESTED','new_synthesis':'NOT_TESTED','implementation':'NOT_TESTED','BOARD':'NOT_TESTED',
         'hardware_error':None,'CMA':None,'max_verified_BO_bytes':None,
         'new_commit':None,'push':False,'B_files_modified':False,'next':'Only retry new-source A Csim after official host-bound license recovery; keep B formatting/tool issues explicit.'}
 with (E/'REPORT.json').open('x',encoding='utf-8') as out:json.dump(result,out,indent=2)
 print(json.dumps({'status':result['status'],'PC_cases':61,'RTL_replay':66,'actual_XO_received':True}))
if __name__=='__main__':main()
