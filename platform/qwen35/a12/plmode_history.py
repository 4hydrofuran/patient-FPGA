"""Semantic mode history validation independent from coordinator transitions."""
import re
from plm_journal import need
from plmode_provider import MODES

def validate(rows,*,closed_required=False):
    session=None;active=None;mode='STRICT_CONTROL';disabled=False;used=set();windows=set();reserved=None
    for r in rows:
        e=r['event']
        if e=='SESSION_OPEN':
            need(session is None and r['default_mode']=='STRICT_CONTROL' and r['candidate_disabled'] is disabled and
                r['domain'] in ('PC_CPU_MODEL','BOARD_PL_MODEL') and r['release_allowed'] is False,'invalid session open')
            need(type(r['manager_pid']) is int and r['manager_pid']>0 and type(r['manager_start_ticks']) is int and r['manager_start_ticks']>0,'session manager incarnation missing')
            session=r;mode='STRICT_CONTROL';active=None;reserved=None;continue
        need(session and r['session_epoch']==session['session_epoch'],'orphan/wrong session event')
        if e=='MODE_CHANGE':
            need(active is None and r['previous']==mode and r['next'] in MODES and not(disabled and r['next']=='BATCH_CANDIDATE'),'active/disabled mode change')
            mode=r['next']
        elif e=='WINDOW_BEGIN':
            need(active is None and r['input_id'] not in used and r['window_id'] not in windows and len(used)<8 and
                (reserved is None or r['input_id']==reserved) and r['mode']==mode and r['cap']==MODES[mode] and
                r['domain']==session['domain'],'window replay/mode/domain differs')
            used.add(r['input_id']);windows.add(r['window_id']);reserved=None;active=dict(begin=r,native=None,failed=False,await_owner=False)
        elif e=='NATIVE_OWNED':
            need(active and active['native'] is None and r['window_id']==active['begin']['window_id'] and
                type(r['native_pid']) is int and r['native_pid']>0 and type(r['native_start_ticks']) is int and r['native_start_ticks']>0 and
                re.fullmatch('[0-9a-f]{32}',r['page_epoch']),'invalid owned native observation')
            active['native']=r
        elif e in ('WINDOW_END','WINDOW_FAILED'):
            need(active and not active['failed'] and r['window_id']==active['begin']['window_id'] and r['input_id']==active['begin']['input_id'] and
                r['release_allowed'] is False and r['replay_allowed'] is False,'orphan/duplicate completion')
            p=r.get('page')
            if e=='WINDOW_END':
                need(active['native'] and r['native_pidfd_terminal'] is True and r['worker_exit_code']==0 and p['revoked'] is True and
                    p['active'] is p['unknown_io'] is False and p['claims']==2880 and p['request_serial']==3 and
                    p['worker_pid']==active['native']['native_pid'] and p['worker_start_ticks']==active['native']['native_start_ticks'] and
                    p['manager_epoch']==active['native']['page_epoch'] and p['manager_pid']==session['manager_pid'] and
                    p['manager_start_ticks']==session['manager_start_ticks'],'normal window not proven')
                if session['domain']=='BOARD_PL_MODEL':active['await_owner']=True
                else:active=None
            else:
                need(p is None or p['revoked'] is True,'failed native authorization not revoked')
                active['failed']=True;active['failure']=r;disabled=True
        elif e=='OWNER_FINALIZED':
            need(active and active['await_owner'] and not active['failed'] and session['domain']=='BOARD_PL_MODEL' and
                r['window_id']==active['begin']['window_id'] and r['original_owner_finished'] is True,'unproven owner finalization')
            active=None
        elif e=='FAILED_OWNER_FINALIZED':
            need(active and active['failed'] and session['domain']=='BOARD_PL_MODEL' and r['original_owner_finished'] is True and
                r['native_pidfd_terminal'] is True and r['page']['revoked'] is True and not r['page']['active'] and
                not r['page']['unknown_io'] and r['next_mode']=='STRICT_CONTROL','failed/unknown owner cannot be finalized')
            active=None;mode='STRICT_CONTROL';disabled=True
        elif e=='NEXT_OWNER_BOUND':need(active is None and session['domain']=='BOARD_PL_MODEL','new owner while active or wrong provider')
        elif e=='PC_NATIVE_DRAINED':
            need(active and active['failed'] and session['domain']=='PC_CPU_MODEL' and r['native_pidfd_terminal'] is True and
                r['page']['revoked'] is True and r['old_page_not_reset'] is True,'unproven CPU drain')
        elif e=='FALLBACK_NEW_INPUT':
            need(active and active['failed'] and session['domain']=='PC_CPU_MODEL' and r['native_pidfd_terminal'] is True and
                r['old_page_revoked'] is True and r['old_page_not_reset'] is True and r['failed_input']==active['begin']['input_id'] and
                r['next_input'] not in used and r['next_mode']=='STRICT_CONTROL','unsafe fallback/replay')
            active=None;reserved=r['next_input'];mode='STRICT_CONTROL'
        elif e=='BOARD_RECOVERY_NEW_INPUT':
            need(active and active['failed'] and session['domain']=='BOARD_PL_MODEL' and r['failed_window']==active['begin']['window_id'] and
                r['failed_input']==active['begin']['input_id'] and r['next_input'] not in used and r['next_mode']=='STRICT_CONTROL' and
                r['native_pidfd_terminal'] is r['old_page_revoked'] is r['old_page_not_reset'] is True and
                r['old_lease_sha256']!=r['new_lease_sha256'],'unproven Board recovery/new window')
            active=None;reserved=r['next_input'];mode='STRICT_CONTROL';disabled=True
        elif e=='CANCEL_REQUEST':need(active and r['window_id']==active['begin']['window_id'],'orphan cancel')
        elif e=='SESSION_CLOSE':
            need((active is None or active['failed'] and session['domain']=='PC_CPU_MODEL' and
                (r['failed_PC_native_terminal'] is True or r.get('native_not_launched') is True and active['native'] is None and active['failure'].get('native_not_launched') is True)) and
                r['candidate_disabled'] is disabled and r['release_allowed'] is False,'cannot close unknown/live Board session')
            active=None;session=None
        else:raise RuntimeError('unlisted PL mode event '+str(e))
    need(not closed_required or session is None,'mode history not closed')
    return dict(candidate_disabled=disabled,used=used,active=None if active is None else active['begin']['window_id'],session_open=session is not None)
