"""Independent raw-native audit plus semantic mode history. No Board acceptance."""
import argparse
import ast
from pathlib import Path
import textwrap
import types
import modelpl_audit as frozen
from plmode_evidence import ROOT,OUT,read,save,sha
from plmode_history import validate
from plmode_journal import read_journal
from request_journal_verified import digest

def audit_window(folder,window):
    directory=folder/window['mirror'];normal=window['closed'];page=window['page']
    if not normal:
        q=window['last_native_message'];r=q['private_CPU_report']['a12_route']
        assert page['claims']==5 and page['unknown_io'] and r['pc_attempted_calls']==5 and r['pc_started_calls']==r['cpu_run_count']==r['pc_verified_completions']==4
        assert q['private_control']['copy_checks']==4 and r['pc_poisoned'] and not r['pc_output_consumable'] and window['model_results']==0
        assert 'generation node replaced/unloaded' in window['reason']
    meta=dict(status='PASS_ACTUAL_QWEN_PLM_CPU_WINDOW_NOT_BOARD' if normal else 'FAILED_PC_CONTROL_WINDOW_RETAINED',private_directory=window['directory'],
        claims=page['claims'],validated_answers=2 if normal else 0,worker_exit_code=window['worker_exit_code'],all_threads_stopped=window['all_threads_stopped'],
        private_messages=window['private_messages'],legacy_sequences=window['legacy_sequences'],page=page,
        fault_expectation=dict(intended_fault_verified=not normal),control_results=window['model_results'],writer_FD_retained=window['writer_FD_retained'],
        owned_pidfd_terminal=True,release_allowed=False,replay_allowed=False)
    source=ROOT/'platform/qwen35/a12/modelpl_audit.py';raw=source.read_text(encoding='utf-8');n=next(n for n in ast.parse(raw).body if isinstance(n,ast.FunctionDef) and n.name=='audit')
    text=textwrap.dedent('\n'.join(raw.splitlines()[n.lineno-1:n.end_lineno]))
    text=text.replace("row['domain']=='PC_REAL_MODEL_CPU_REFERENCE'","row['domain']=='PC_CPU_MODEL'")
    text=text.replace("row['actual_CPU_calls']==count","row['verified_backend_calls']==count and row['execution_kind']=='CPU_REFERENCE'")
    anchor="        else:raise AssertionError('unlisted model journal event '+event)";assert text.count(anchor)==1
    text=text.replace(anchor,"""        elif event=='LIVE_GENERATION_BIND':
            assert contexts==1 and row['Board_approval'] is False and row['context_sha256']==ready['bridge']['a12_route']['pc_plm']['bound_context_sha256']
            sm=read(folder/'LIVE_SOURCE.json');assert sm['identity_sha256']==row['source_identity_sha256'] and sm['epoch']==row['generation_epoch']
        elif event=='LIVE_GENERATION_RESIDENT':
            assert row['Board_approval'] is False and row['resident_signature']=={k:ready['bridge']['a12_route'][k] for k in row['resident_signature']}
            assert row['resident_report_sha256']==digest(ready['bridge']['a12_route'])
"""+anchor)
    def view(path):
        path=Path(path)
        if path==directory/'RESULT.json':return meta
        if path==directory/'LAUNCH.json':return dict(cap=window['cap'])
        return read(path)
    scope=dict(frozen.__dict__,OUT=folder,read=view);exec(compile(text,str(source)+'#mode-audit','exec'),scope)
    result=scope['audit'](window['mirror']);result['audit_view']='DERIVED_FROM_ACTUAL_SCENARIO_RECORDS_RAW_FILES_ARE_NOT_REWRITTEN'
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--tag',required=True);a=p.parse_args();folder=OUT/a.tag;r=read(folder/'RESULT.json');assert r['status']=='PASS_PC_MODE_SCENARIO'
    private_log=Path(r['private_state'])/'history/coordinator.jsonl'
    latest=folder/'clean-restart-current.jsonl' if (folder/'CLEAN_RESTART.json').exists() else folder/'history/coordinator.jsonl'
    assert sha(private_log)==sha(latest)
    rows=read_journal(private_log) # Linux ownership/mode gate applies to its actual private file, not a DrvFS mirror
    if r['scenario']=='begin_fsync':
        assert (folder/'history/DIRTY.json').exists() and r['windows']==[] and rows[-1]['event']=='WINDOW_BEGIN' and r['phase']=='QUARANTINED'
        results=[]
    else:
        replay=validate(rows,closed_required=True);results=[audit_window(folder,w) for w in r['windows']]
        assert r['phase']=='CLOSED' and not (folder/'history/DIRTY.json').exists()
        if r['scenario']=='fallback':
            assert len(results)==2 and results[0]['actual_CPU_claims']==5 and results[1]['actual_CPU_claims']==2880 and r['candidate_disabled'] and replay['candidate_disabled']
            assert r['windows'][0]['page']['manager_epoch']!=r['windows'][1]['page']['manager_epoch']
            assert r['windows'][0]['page']['source_slot']['epoch_sha256']!=r['windows'][1]['page']['source_slot']['epoch_sha256']
            assert [x['event'] for x in rows].count('FALLBACK_NEW_INPUT')==1 and r['windows'][1]['cap']==1
        else:assert len(results)==1 and results[0]['actual_CPU_claims']==2880
    save(folder/'AUDIT.json',dict(status='PASS_RAW_MODEL_AND_MODE_HISTORY',scenario=r['scenario'],windows=results,mode_rows=len(rows),
        BOARD='NOT_TESTED',actual_PL_results_consumed=False,release_allowed=False,full_intermediate_state='NOT_TESTED'))
    print('PASS_RAW_MODEL_AND_MODE_HISTORY',a.tag)
if __name__=='__main__':main()
