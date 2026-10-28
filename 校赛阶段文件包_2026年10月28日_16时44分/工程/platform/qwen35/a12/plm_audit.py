"""Independent journal semantics / native completion / mirror audit, never release authority."""
import argparse
import json
from pathlib import Path
import struct
from plm_evidence import ROOT,OUT,read,save,sha,pin
from request_journal_verified import canonical,digest,ZERO,FrozenProbe
from request_journal_audit import strict_json

def audit_window(tag):
    directory=OUT/tag;r=read(directory/'RESULT.json');state=directory/'state';raw=(state/'control.jsonl').read_bytes()
    assert len(raw)<=4*1024*1024 and raw.endswith(b'\n');rows=[];chain=ZERO
    for line in raw.splitlines():
        assert len(line)+1<=8192;q=strict_json(line);h=q.pop('sha256')
        assert q['schema']=='PC_PLM_JOURNAL_V1' and q['serial']==len(rows)+1 and q['previous_sha256']==chain and digest(q)==h
        q['sha256']=h;chain=h;rows.append(q)
    assert len(rows)<=4096
    # Actual originals in the private directory, not a mirror treated as new authority.
    original=Path(r['private_directory'])
    for p in directory.rglob('*'):
        rel=p.relative_to(directory)
        if p.is_file() and rel.as_posix() not in ('RESULT.json','LAUNCH.json'):
            assert (original/rel).is_file() and sha(p)==sha(original/rel),str(rel)
    cap=read(directory/'LAUNCH.json')['cap'];requests=FrozenProbe().requests
    active=None;completed=[];last=0;reserved=0;private=1;grants=0;seq={'router':0,'backend':0};bound=False;ready=False;closed=False
    for q in rows:
        event=q['event']
        if event=='WINDOW_OPEN':assert q['cap']==cap and not q['real_device_approval']
        elif event=='LEGACY_PERMISSION':
            lane=q['lane'];assert q['sequence']==seq[lane]+1;seq[lane]+=1
            if q['phase']=='router_close':assert completed==['app_R0','warm_prefix','app_hit'] and active is None
            assert q['phase'] in ('router_open','device_open','weight_load','router_close')
        elif event=='CONTEXT_BIND':
            assert not bound and digest(q['facts'])==q['context_sha256'] and q['facts']['board_generation_approval']=='UNBOUND' and not q['independent_board_approval'];bound=True
        elif event=='READY':assert bound and q['weights']==72 and q['stub_BO_count']==148 and q['real_BO_count'] is None;ready=True
        elif event=='BEGIN':
            assert ready and active is None and len(completed)<3;req=requests[len(completed)];assert q['request']==req and q['request_sha256']==digest(req) and q['base']==last
            n=len(req['tokens'])-(70 if req['id']=='app_hit' else 0);pre=[min(8,n-i) for i in range(0,n,8)]
            full=pre+([1]*7 if req['op']!='cache_create' else []);actual=pre+([1]*6 if req['op']!='cache_create' else [])
            assert q['budget']==len(full)*72 and q['control_actual_plan']==actual
            active=dict(id=req['id'],digest=digest(req),base=last,full=full,actual=actual,budget=q['budget']);reserved=last
        elif event=='GRANT':
            assert active and q['request_id']==active['id'] and q['request_sha256']==active['digest']
            assert q['sequence']==private+1 and q['generation']==len(completed)+2;private+=1;grants+=1
            index=(reserved-active['base'])//72;assert index<len(active['full']) and q['T']==active['full'][index]
            count=min(cap,72-(reserved-active['base'])%72);assert q['first']==reserved+1 and q['last']==reserved+count<=active['base']+active['budget'];reserved=q['last']
        elif event=='END':
            assert active and q['request_id']==active['id'] and q['request_sha256']==active['digest']
            count=len(active['actual'])*72;assert q['actual_control_calls']==count and q['final_job']==reserved==last+count and q['hardware_calls'] is None and q['control_result_only']
            # A complete END line is historical bytes, never proof that fsync/receipt/delivery succeeded.
            if r['status']=='PASS_PC_XRT_MANAGER_WINDOW_NOT_MODEL':
                result=read(directory/(active['id']+'-CONTROL_RESULT.json'));native=result['result'];nr=native['report']
                assert digest(native)==q['result_sha256'] and nr['status']=='READY' and nr['output_consumable'] is True and nr['host_verified_completions']==reserved
                assert native['last_job']==reserved==nr['job_id'] and native['calls']==count
                meta=bytes.fromhex(nr['a12_raw_meta_hex']);assert len(meta)==64
                magic,build,job,err,done,per_call,weight_bytes=struct.unpack('<IIQIIQQ',meta[:40])
                assert (magic,build,job,err,done,per_call,weight_bytes)==(0x57344138,0xB3030002,reserved,0,1,1,2048)
                receipt=read(state/(active['id']+'-receipt.json'));assert receipt['END_sha256']==q['sha256'] and receipt['result_sha256']==digest(native) and receipt['answer_delivered'] is False
                fence=result['delivery_fence'];assert fence['requested_ns']<=fence['started_ns']<=fence['ended_ns']<=fence['authorized_ns'] and fence['authorized_ns']-fence['started_ns']<=250000000
            completed.append(active['id']);last=reserved;active=None
        elif event=='WINDOW_CLOSE':assert completed==['app_R0','warm_prefix','app_hit'] and active is None and not q['release_allowed'] and not q['replay_allowed'];closed=True
        else:raise AssertionError('unlisted event '+event)
    normal=r['status']=='PASS_PC_XRT_MANAGER_WINDOW_NOT_MODEL'
    if normal:
        assert closed and not (state/'DIRTY.json').exists() and r['claims']==2880 and r['page']['claims']==2880 and not r['page']['unknown_io'] and not r['page']['active'] and r['page']['revoked']
        assert r['worker_exit_code']==0 and r['all_threads_stopped'] and r['private_messages']==private and r['legacy_sequences']==seq
        assert grants==(2880 if cap==1 else 40) and r['control_results']==3
    else:
        assert not closed and (state/'DIRTY.json').exists() and r['page']['revoked'] and r['control_results']==0 and r['writer_FD_retained']
        assert r['owned_pidfd_terminal'] and r['all_threads_stopped'] and not r['release_allowed'] and not r['replay_allowed']
    return dict(tag=tag,status='COMPLETE_CONTROL_WINDOW' if normal else 'FAILED_WINDOW_DIRTY_NO_RELEASE',cap=cap,claims=r['page']['claims'],
        grant_records=grants,legacy_sequences=seq,native_result_count=r['control_results'],hardware_completions=None,release_allowed=False,replay_allowed=False)
def main():
    p=argparse.ArgumentParser();p.add_argument('--suite',required=True);a=p.parse_args();suite=read(OUT/(a.suite+'-SUITE.json'))
    windows=[audit_window(tag) for tag in suite['windows']]
    assert len(windows)==17 and sum(w['status']=='COMPLETE_CONTROL_WINDOW' for w in windows)==2
    failure={w['tag'].split(a.suite+'-',1)[1]:w for w in windows if w['status']!='COMPLETE_CONTROL_WINDOW'}
    for key in ('begin-fsync','grant-fsync','grant-slow','request-digest','legacy-replay','premature-unload'):assert failure[key]['claims']==0
    assert failure['cached-T']['claims']==1 and failure['revoke-claim']['claims']==5
    for key in ('end-fsync','receipt-fsync','end-slow','reuse-generation'):assert failure[key]['claims']==1440
    save(OUT/(a.suite+'-AUDIT.json'),dict(status='PASS_INDEPENDENT_CONTROL_JOURNALS_META_AND_RECEIPTS',windows=windows,
        BOARD='NOT_TESTED',model_numerical_verification=False,release_allowed=False,replay_allowed=False))
    print('PASS_INDEPENDENT_CONTROL_JOURNALS_META_AND_RECEIPTS',a.suite)
if __name__=='__main__':main()
