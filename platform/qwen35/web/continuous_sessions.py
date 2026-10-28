"""Keep finished consultations available while retaining only eight in memory."""
import copy
import json
from pathlib import Path


def install(coordinator,directory):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    original={name:getattr(coordinator,name) for name in ('finish','create_session','snapshot','evaluation','turn_result','event_batch')}
    def path(sid):
        if len(sid)!=32 or any(c not in '0123456789abcdef' for c in sid):
            return directory/'invalid-session'
        return directory/(sid+'.json')
    def archive(sid):
        snapshot=original['snapshot'](sid)
        if not snapshot['closed']:raise RuntimeError('Cannot archive an active consultation')
        data=dict(snapshot=snapshot,evaluation=original['evaluation'](sid),
                  turn_results={t['request_id']:original['turn_result'](sid,t['request_id']) for t in snapshot['turns']})
        path(sid).write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
    def finish(sid,rid):
        with coordinator.lock:
            result=original['finish'](sid,rid)
            archive(sid)
            return result
    def create(rid,case_id=None,**options):
        with coordinator.lock:
            if rid not in coordinator.starts and len(coordinator.conversations)>=8:
                closed=next((sid for sid,c in coordinator.conversations.items() if c.closed),None)
                if closed is not None:
                    archive(closed)
                    del coordinator.conversations[closed]
            return original['create_session'](rid,case_id,**options)
    def stored(sid):
        p=path(sid)
        return json.loads(p.read_text(encoding='utf-8')) if p.is_file() else None
    def snapshot(sid):
        with coordinator.lock:
            if sid in coordinator.conversations:return original['snapshot'](sid)
            data=stored(sid)
            if data is None:return original['snapshot'](sid)
            result=copy.deepcopy(data['snapshot']);result['cursor']=coordinator.journal.sequence
            return result
    def evaluation(sid):
        with coordinator.lock:
            if sid in coordinator.conversations:return original['evaluation'](sid)
            data=stored(sid)
            return data['evaluation'] if data is not None else original['evaluation'](sid)
    def turn_result(sid,rid):
        with coordinator.lock:
            if sid in coordinator.conversations:return original['turn_result'](sid,rid)
            data=stored(sid)
            if data is not None and rid in data['turn_results']:return data['turn_results'][rid]
            return original['turn_result'](sid,rid)
    def events(sid,after):
        with coordinator.lock:
            if sid not in coordinator.conversations and stored(sid) is not None:
                return [],False,coordinator.journal.sequence
            return original['event_batch'](sid,after)
    for name,method in dict(finish=finish,create_session=create,snapshot=snapshot,evaluation=evaluation,turn_result=turn_result,event_batch=events).items():
        setattr(coordinator,name,method)


def may_end(*,continuous,closed,idle,model_requests,maximum_questions,broken,stop_requested=False):
    if not idle:return False
    if continuous:return broken or stop_requested
    return closed and (broken or model_requests>=maximum_questions)


def question_reserve(context_tokens=1024,prefix_tokens=70,output_tokens=24,*,draft_strategy=None):
    base=72*((context_tokens-prefix_tokens+7)//8+output_tokens-1)
    if draft_strategy is None:return base
    from realtime_draft import STRATEGY
    if draft_strategy!=STRATEGY:raise ValueError('unknown draft budget strategy')
    # One bounded verification pass plus a possible full serial replay.
    # Each fits the original context/output bound; doubling is conservative.
    return 2*base
