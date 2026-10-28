"""Derive task09 packages from reviewed task08 packager without touching old evidence."""
from common import ROOT

if __name__=='__main__':
    p=ROOT/'platform/qwen35/a12';s=(p/'step08_package.py').read_text()
    s=s.replace('from step08_common import OUT','from step09_common import OUT')
    s=s.replace("    if variant=='generation':assert j(OUT/'DIAGNOSTIC_AUDIT.json')['status']=='PASS_BOARD_ALL_24_LAYERS_216_REAL_CONSUMED_OUTPUTS'\n    for n in ('health_pc_01','pc_graph_01'):assert j(OUT/(n+'.json'))['exit_code']==0", "    assert j(OUT/'PC_MATRIX.json')['status']=='PASS_PC_NATIVE_PARTITION_STATE_CANCEL_AND_FAIL_CLOSED'\n    for n in ('supervisor_pc_01','permission_pc_01'):assert j(OUT/(n+'.json'))['exit_code']==0")
    s=s.replace("'step07_supervisor.py'):","'step07_supervisor.py','step09_window.py','step09_supervisor.py'):")
    s=s.replace("shutil.copyfile(ROOT/'platform/qwen35/a12/step08_manager.py',control/'step08_manager.py')","shutil.copyfile(ROOT/'platform/qwen35/a12/step09_manager.py',control/'step09_manager.py')")
    s=s.replace("OUT/('generation-budget-v2.json' if variant=='generation' else 'diagnostic-budget.json')","OUT/(variant+'-budget.json')")
    s=s.replace("window='a12-full-'+variant+'-20261024-v1';remote='/var/lib/kv260-a12/step08-'+variant+'-20261024-v1'","window='a12-state-'+variant+'-20261024-v1';remote='/var/lib/kv260-a12/step09-'+variant+'-20261024-v1'")
    s=s.replace("requests=j(OUT/'REQUESTS.json')['diagnostic'] if variant=='diagnostic' else j(OUT/'TOKENIZED_REQUESTS.json')['generation']","requests=j(OUT/'REQUESTS.json')[variant]")
    s=s.replace("([OUT/'diagnostic/readback_01/stdout.txt'] if variant=='generation' else [])","([OUT/'short/readback_01/stdout.txt'] if variant=='context' else [])")
    s=s.replace('A12_STEP08_','A12_STEP09_').replace('a12-step08-','a12-step09-').replace("replace('review06_manager.py','step08_manager.py')","replace('review06_manager.py','step09_manager.py')").replace("'STEP08_'","'STEP09_'")
    s=s.replace("choices=['diagnostic','generation']","choices=['short','context']")
    # The previous task08 archives are now eligible for exact, hash-bound cache advice.
    s=s.replace("save(control/'archive-pins.json',pins)","\n    for v in ('diagnostic','generation'):\n        r=j(ROOT/('evidence/model_pl_A/20261024-step08-v1/'+v+'/readback_01/stdout.txt'))['package']\n        for k in ('path','download'):\n            if k in r:pins.append(dict(path=r[k],bytes=r['bytes'],sha256=r['sha256']))\n    save(control/'archive-pins.json',pins)")
    (p/'step09_package.py').write_text(s,encoding='utf-8',newline='\n')
    s=(p/'step08_monitor.py').read_text().replace('step08-generation','step09-short')
    (p/'step09_monitor_short.py').write_text(s,encoding='utf-8',newline='\n')
    (p/'step09_monitor_context.py').write_text(s.replace('step09-short','step09-context'),encoding='utf-8',newline='\n')
    s=(p/'step08_lifecycle_supplement.py').read_text().replace('from step08_common import OUT','from step09_common import OUT').replace("choices=['diagnostic','generation']","choices=['short','context']")
    (p/'step09_lifecycle_supplement.py').write_text(s,encoding='utf-8',newline='\n')
    print('TASK09_PACKAGE_DERIVATION_READY')
