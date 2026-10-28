"""Independently check archived lease bytes and every final scan attempt."""
import argparse
import hashlib
import json
import sys
from common import ROOT,save
from step09_common import OUT
sys.path.insert(0,str(ROOT/'platform/qwen35/a10'))
from accelerator_release_gate_v2 import require_no_users
from step07_finalize_policy import transient_scan
def j(p):return json.loads(p.read_text(encoding='utf-8'))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('variant',choices=['short','context']);variant=parser.parse_args().variant
    folder=OUT/variant;run=folder/'readback-v1/run-v1';review=j(run/'review.json');profile=j(run/'s2/runtime-profile.json')
    lease=dict(schema='A12_MODEL_LEASE_V1',owner='A',scope=review['scope'],window=review['window_id'],
        identity=review['machine_sha256']+':'+review['boot_id'],pid=profile['manager_pid'],
        owner_start_ticks=profile['manager_start_ticks'],expires_monotonic_ns=profile['expires_monotonic_ns'],
        compute_authorized=True,max_runs=review['max_runs'],max_loads=review['max_loads'],explicit_bo_budget_bytes=review['explicit_bo_budget_bytes'])
    pin=hashlib.sha256((json.dumps(lease,ensure_ascii=False,indent=2)+'\n').encode()).hexdigest()
    for name in ('status_final','delayed_01'):
        state=j(folder/name/'stdout.txt');assert state['lease_archived'] and state['lease_sha256']==pin
    events=[json.loads(line) for line in (run/'s2/finalization-events.jsonl').read_text().splitlines()]
    scans=[r for r in events if r['event']=='FULL_PROCESS_OBSERVATION'];assert scans
    assert all(r['kernel_allowed'] is True for r in scans)
    for row in scans[:-1]:assert transient_scan(row['scan'],review['boot_id'])
    require_no_users(scans[-1]['scan'],True,boot_id=review['boot_id'])
    assert any(r['event']=='FINALIZATION_PREPARED_FOR_ATOMIC_ARCHIVE' and r['normal_worker_exit'] for r in events)
    result=dict(status='PASS_EXACT_ARCHIVED_LEASE_AND_COMPLETE_FINAL_SCAN',variant=variant,lease=lease,archived_lease_sha256=pin,
        full_scan_attempts=len(scans),incomplete_transient_scans_preserved=len(scans)-1,final_complete_scan=True,
        forced_exit=False,finalize_ticket_used=any(r['event']=='EXPLICIT_FINALIZE_ONLY_TICKET_ACCEPTED' for r in events))
    save(OUT/(variant.upper()+'_LIFECYCLE_SUPPLEMENT.json'),result)
    print(json.dumps({k:v for k,v in result.items() if k!='lease'}))
