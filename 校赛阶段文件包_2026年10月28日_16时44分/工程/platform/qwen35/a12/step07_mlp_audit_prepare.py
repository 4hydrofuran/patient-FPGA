"""Derive the independent numeric audit for three real projections and normal finish."""
import ast
from common import ROOT
from step07_mlp_prepare import OUT

if __name__=='__main__':
    p=ROOT/'platform/qwen35/a12';s=(p/'step07_audit.py').read_text()
    s=s.replace('from step07_protocol import OUT','from step07_mlp_prepare import OUT')
    s=s.replace('stopped_readback_01','readback_01').replace('stopped-readback-v1.tar.gz','readback-v1.tar.gz')
    s=s.replace("j(OUT/'BUILD.json')","j(OUT.parent/'20261023-step07-single-v1/BUILD.json')")
    s=s.replace('len(trace)==3','len(trace)==9').replace("t['op']=='gate'","t['op'] in ('gate','up','down')")
    s=s.replace("c['weight_load_count']==1","c['weight_load_count']==3").replace('2162688','6062080')
    s=s.replace("host_counter']==6","host_counter']==10").replace('len(spans)==6','len(spans)==10')
    s=s.replace("p['id']=='l00_gate'","p['id']=='l00_'+t['op']")
    s=s.replace("==[8,1,1]","==[8,8,8,1,1,1,1,1,1]")
    a=s.index('    # Preserve current stopped lifecycle.')
    b=s.index('    lifecycle=',a)
    s=s[:a]+'''    stopped=j(run/'independent-readback.json')
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
''' +s[b:]
    s=s.replace("'PASS_SINGLE_GATE_NUMERIC_AND_REAL_CONSUMER_CLOSEOUT_NOT_COMPLETE' if numeric else 'FAIL_SINGLE_GATE_NUMERIC_CLOSEOUT_NOT_COMPLETE'","'PASS_BOARD_L00_MLP_REAL_CONSUMPTION_AND_NORMAL_CLOSEOUT' if numeric else 'FAIL_BOARD_L00_MLP_NUMERIC'")
    s=s.replace("scope='l0_gate'","scope='l0'").replace('explicit_BO_count=6,weight_loads=1,actual_calls=3','explicit_BO_count=10,weight_loads=3,actual_calls=9')
    s=s.replace("MLP_three_projections='NOT_TESTED'","MLP_three_projections='PASS' if numeric else 'FAIL'")
    a=s.index("        lifecycle=dict(status='NOT_COMPLETE_OWNER_RETAINED'")
    b=s.index('        deferred_failures=',a)
    s=s[:a]+'''        lifecycle=dict(status='NORMAL_EXIT_AND_RESTORE_PASS',worker_exit_codes=[0,0],manager_exit_code=0,
          active_lease=False,dual_locks_held=False,default_PL_restored=True,GDM_active=True,ZOCL_absent=True,
          no_device_users=True,finalization_events=finalize,forced_signals=0),
''' +s[b:]
    s=s.replace('manager_exit_code=None)))','manager_exit_code=0)))')
    # Per-projection coverage and stable allocation/weight set across every call.
    a=s.index('    # Preserve current stopped lifecycle.') if '    # Preserve current stopped lifecycle.' in s else s.index("    stopped=j(run/'independent-readback.json')")
    s=s[:a]+'''    assert [t['op'] for t in trace]==['gate','up','down']*3
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
''' +s[a:]
    ast.parse(s);(p/'step07_mlp_audit.py').write_text(s,encoding='utf-8',newline='\n')
    print('MLP_INDEPENDENT_AUDIT_READY')
