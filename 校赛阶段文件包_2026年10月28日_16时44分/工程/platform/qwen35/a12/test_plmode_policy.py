"""Metadata-policy fixtures, not FPGA runs; semantic mode tampering checks."""
import argparse
import copy
import os
from pathlib import Path
import tempfile
from plmode_evidence import ROOT,OUT,read,save
from plmode_provider import fpga_route,BoardProvider,CONTRACT
from plmode_history import validate
from plmode_journal import read_journal
from plmode_coordinator import Coordinator

def refuses(operation):
    try:operation()
    except (RuntimeError,KeyError,ValueError,AttributeError):return
    raise AssertionError('policy mutation unexpectedly accepted')

def main():
    p=argparse.ArgumentParser();p.add_argument('--tag',required=True);a=p.parse_args();results=[]
    r=dict(execution_kind='FPGA_REAL',a12_domain='BOARD',backend_id='A_XRT_B_KERNEL_V1',contract_sha256=CONTRACT,kernel_build_id=0xB3030002,
        status='READY',no_silent_fallback=True,retains_resources_on_poison=True,hardware_done_count=None,a12_hardware_global_count=None,
        a12_hardware_global_completion_counter=None,host_verified_completions=4,job_id=4,output_consumable=True,last_status_code=0)
    assert fpga_route(r,completed=True)==4;results.append('HOST_VERIFIED_COUNTER_REMAINS_DISTINCT_FROM_NULL_HARDWARE_COUNTER')
    for key,value in [('execution_kind','CPU_REFERENCE'),('a12_domain','PC'),('hardware_done_count',4),('a12_hardware_global_count',4),
        ('status','POISONED'),('job_id',3),('host_verified_completions',5001),('output_consumable',False),('last_status_code',8),('no_silent_fallback',False)]:
        changed=copy.deepcopy(r);changed[key]=value;refuses(lambda:fpga_route(changed,completed=True));results.append('REJECT_'+key)
    refuses(lambda:BoardProvider({},OUT/'BOARD_BUILD-v2-assets.json'));results.append('PC_JSON_CANNOT_CONSTRUCT_BOARD_PROVIDER')
    runs={}
    for tag in ('normal03','fallback03'):
        result=read(OUT/tag/'RESULT.json');rows=read_journal(Path(result['private_state'])/'history/coordinator.jsonl');validate(rows,closed_required=True);runs[tag]=rows
    for name,tag,event,mutate in [
        ('END_UNKNOWN_IO','normal03','WINDOW_END',lambda r:r['page'].__setitem__('unknown_io',True)),
        ('END_WRONG_MANAGER','normal03','WINDOW_END',lambda r:r['page'].__setitem__('manager_pid',r['page']['manager_pid']+1)),
        ('END_BAD_EXIT','normal03','WINDOW_END',lambda r:r.__setitem__('worker_exit_code',2)),
        ('FALLBACK_REPLAY','fallback03','FALLBACK_NEW_INPUT',lambda r:r.__setitem__('next_input',r['failed_input'])),
        ('FALLBACK_BATCH','fallback03','FALLBACK_NEW_INPUT',lambda r:r.__setitem__('next_mode','BATCH_CANDIDATE')),
        ('LOST_FAULT_LATCH','fallback03','SESSION_CLOSE',lambda r:r.__setitem__('candidate_disabled',False)),
        ('NO_REVOKE_BEFORE_FAILURE','fallback03','WINDOW_FAILED',lambda r:r['page'].__setitem__('revoked',False)),
    ]:
        rows=copy.deepcopy(runs[tag]);mutate(next(r for r in rows if r['event']==event));refuses(lambda:validate(rows,closed_required=True));results.append(name)
    with tempfile.TemporaryDirectory(prefix='a12-mode-restart-') as root:
        # Fresh journal tests don't run a model. Persisted actual failed history is
        # reopened separately below using its original owning Linux directory.
        c=Coordinator(Path(root)/'closed',OUT/'BUILD-v2.json',trusted_candidate=True)
        refuses(lambda:c.switch('SERVICE'));c.close();results.append('NO_UNLIMITED_SERVICE_ALIAS')
    prior=read(OUT/'fallback03/RESULT.json');c=Coordinator(Path(prior['private_state'])/'history',OUT/'BUILD-v2.json',trusted_candidate=True)
    assert c.mode=='STRICT_CONTROL' and c.disabled
    refuses(lambda:c.switch('BATCH_CANDIDATE'));refuses(lambda:c.start('first-fallback03'));c.close()
    results.append('CLEAN_RESTART_STRICT_DEFAULT_LATCH_AND_NO_OLD_INPUT_REPLAY')
    dirty=read(OUT/'fsync01/RESULT.json');refuses(lambda:Coordinator(Path(dirty['private_state'])/'history',OUT/'BUILD-v2.json',trusted_candidate=True))
    results.append('DIRTY_FSYNC_FAILURE_FORBIDS_RESTART')
    save(OUT/('POLICY_TEST-'+a.tag+'.json'),dict(status='PASS_PLM_MODE_POLICY_AND_PERSISTENT_HISTORY',tests=results,count=len(results),
        FPGA_metadata_cases='SYNTHETIC_POLICY_ONLY_NOT_EXECUTION',BOARD='NOT_TESTED',actual_FPGA_calls=None))
    print('PASS_PLM_MODE_POLICY_AND_PERSISTENT_HISTORY',len(results))
if __name__=='__main__':main()
