"""Independent semantic replay of PC coordinator history; no release authority."""
import re
from mode_journal import need

MODES={'PC_STRICT_CONTROL':1,'PC_BATCH_CANDIDATE':72}
def _hex(v,n):return type(v) is str and re.fullmatch('[0-9a-f]{'+str(n)+'}',v)
def _positive(v):return type(v) is int and v>0

def validate_history(rows,*,closed_required=False):
    session=None;mode=None;active=None;disabled=False;used=set();windows=set();tags=set();reserved=None
    for r in rows:
        event=r['event']
        if event=='SESSION_OPEN':
            need(session is None and _hex(r['session_epoch'],32) and r['domain']=='PC_ONLY' and
                r['default_mode']=='PC_STRICT_CONTROL' and r['candidate_disabled'] is disabled and
                r['replay_allowed'] is r['release_allowed'] is False and _hex(r['capsule_sha256'],64),
                'invalid PC session open')
            session=r;mode='PC_STRICT_CONTROL';active=None;reserved=None;continue
        need(session is not None and r['session_epoch']==session['session_epoch'],'event outside/wrong session')
        if event=='MODE_CHANGE':
            need(active is None and r['previous_mode']==mode and r['next_mode'] in MODES and
                not (disabled and r['next_mode']=='PC_BATCH_CANDIDATE') and r['reason']=='NO_ACTIVE_AUTHORIZATION',
                'mode change while active/disabled')
            mode=r['next_mode']
        elif event=='WINDOW_BEGIN':
            need(active is None and r['input_id'] not in used and len(used)<8 and
                (reserved is None or r['input_id']==reserved) and r['mode']==mode and r['grant_size']==MODES[mode] and
                r['capsule_sha256']==session['capsule_sha256'] and r['independent_test_input'] is True and
                _hex(r['window_id'],32) and r['window_id'] not in windows and r['tag'] not in tags,
                'window replay/mode/budget differs')
            used.add(r['input_id']);windows.add(r['window_id']);tags.add(r['tag']);reserved=None
            active=dict(begin=r,manager=None,native=None,failed=False,cancelled=False)
        elif event=='WINDOW_MANAGER_OBSERVED':
            need(active and r['window_id']==active['begin']['window_id'] and active['manager'] is None and
                _positive(r['manager_pid']) and _positive(r['manager_start_ticks']),'manager ownership order differs')
            active['manager']=r
        elif event=='WINDOW_NATIVE_OBSERVED':
            need(active and r['window_id']==active['begin']['window_id'] and active['manager'] and active['native'] is None and
                _positive(r['native_pid']) and _positive(r['native_start_ticks']) and _hex(r['page_epoch'],32) and
                _hex(r['page_snapshot_sha256'],64),'native ownership order differs')
            active['native']=r
        elif event=='CANCEL_REQUEST':
            need(active and r['window_id']==active['begin']['window_id'] and r['no_replay'] is True,'orphan cancel')
            active['cancelled']=True
        elif event in ('WINDOW_END','WINDOW_FAILED'):
            need(active and not active['failed'] and active['manager'] and active['native'],'orphan/duplicate window completion')
            b=active['begin'];p=r['page'];a=r['independent_audit']
            need(r['window_id']==b['window_id'] and r['input_id']==b['input_id'] and r['tag']==b['tag'] and r['mode']==mode and
                r['manager_pidfd_terminal'] is r['native_pidfd_terminal'] is p['revoked'] is True and
                p['manager_pid']==active['manager']['manager_pid'] and p['worker_pid']==active['native']['native_pid'] and
                p['worker_start_ticks']==active['native']['native_start_ticks'] and p['manager_epoch']==active['native']['page_epoch'] and
                r['BOARD']=='NOT_TESTED' and r['release_allowed'] is False and a['release_allowed'] is a['replay_allowed'] is False,
                'window terminal/resource binding differs')
            if event=='WINDOW_END':
                need(not active['cancelled'] and r['outcome']=='PASS_PC_WINDOW' and r['manager_exit_code']==0 and
                    r['capsule_unchanged'] is True and p['active'] is p['inflight_or_unknown'] is False and
                    p['shared_claims']==2880 and p['request_generation']==3 and a['status']=='COMPLETE_ACTUAL_PC_MICROBATCH_TRANSCRIPT'
                    and a['grant_size']==MODES[mode] and a['actual_cpu_calls']==2880,'incomplete/unsafe normal window')
                active=None
            else:
                need(r['outcome']=='FAILED_PC_DRAINED_NO_REPLAY','invalid failure disposition')
                active['failed']=True;disabled=True
        elif event=='FALLBACK_NEXT_INPUT':
            need(active and active['failed'] and r['failed_window']==active['begin']['window_id'] and
                r['failed_input']==active['begin']['input_id'] and r['next_input'] not in used and
                r['next_mode']=='PC_STRICT_CONTROL' and r['old_page_not_reset'] is True,'unsafe fallback/replay')
            reserved=r['next_input'];active=None;mode='PC_STRICT_CONTROL'
        elif event=='SESSION_CLOSE':
            need((active is None or active['failed']) and r['candidate_disabled'] is disabled and
                r['replay_allowed'] is r['release_allowed'] is False,'session close while active/unknown')
            session=None;active=None;reserved=None
        else:raise RuntimeError('unknown coordinator event: '+str(event))
    need(not closed_required or session is None,'history is not closed')
    return dict(session_open=session is not None,active_window=None if active is None else active['begin']['window_id'],
        candidate_disabled=disabled,used_inputs=sorted(used),normal_release_allowed=False,replay_allowed=False)
