"""Independent raw files, application plans, counter and delivery-order audit.

Historical fsync success cannot be inferred from complete bytes alone. This
auditor never authorizes replay, Board compute, physical release or medicine.
"""
import argparse
import copy
from pathlib import Path
from jinja2.sandbox import ImmutableSandboxedEnvironment
from resident_evidence import ROOT, OUT, read, save, sha
from resident_policy import Probe, IDS
from request_journal_verified import canonical, digest, ZERO
from request_journal_audit import strict_json
from plm_journal import need


def chain(path):
    rows=[];previous=ZERO;used=0;epoch=None
    with Path(path).open('rb') as f:
        for line in f:
            used+=len(line);need(len(line)<=8192 and used<=4*1024*1024 and line.endswith(b'\n'), 'journal byte bounds')
            row=strict_json(line);payload=dict(row);h=payload.pop('sha256')
            epoch=epoch or row['epoch']
            need(h==digest(payload) and row['serial']==len(rows)+1 and row['previous_sha256']==previous and row['epoch']==epoch,'journal chain differs')
            rows.append(row);previous=h
    need(len(rows)<=4096,'journal row bounds')
    return rows


def fence(row, after):
    need(after<=row['requested_ns']<=row['started_ns']<=row['ended_ns']<=row['authorized_ns'] and
         row['authorized_ns']-row['started_ns']<=250000000,'final fresh delivery fence/order differs')


def audit(tag):
    folder=OUT/tag;r=read(folder/'RESULT.json');launch=read(folder/'LAUNCH.json')
    need(r.get('error') is None and r['owned_pidfd_terminal'] is True and r['all_threads_stopped'] is True,'window did not finish its declared scenario')
    need(r['independent_page']['revoked'] is True and r['independent_page']['source_slot']['domain']==1 and r['independent_page']['hardware_completions'] is None,'PC control mislabeled')
    events=[read(p) for p in sorted(folder.glob('EVENT_*.json'))]
    app=chain(folder/'application-state/control.jsonl');native=chain(folder/'state/control.jsonl')
    raw=(folder/'native.stdout').read_bytes();need(len(raw)<=1024*1024,'native stdout bound')
    packets=[strict_json(line) for line in raw.splitlines()];need(len(packets)<=228,'native packet bound')
    answers=[e['value'] for e in events if e['op']=='submit' and e['value']['type']=='validated_answer']
    if launch['scenario']=='fault' and launch['fault']!='busy':
        need(not answers and r['worker_exit_code']==2 and r['dirty_marker_retained'] and r['writer_FD_retained'],'failed window delivered or claimed clean release')
        need((folder/'state/DIRTY.json').is_file() and (folder/'application-state/DIRTY.json').is_file(),'dirty failures lost')
        failures=[e['value'] for e in events if e['op']=='submit']
        need(len(failures)==1 and failures[0]['type']=='error' and failures[0]['tts_ready'] is False and failures[0]['fatal'] is True,'fault final response differs')
        reason=str(r.get('reason',''))+' '+failures[0]['message']
        expected={'begin_fsync':'fsync','end_fsync':'fsync','receipt_fsync':'fsync','end_slow':'stale',
                  'deadline':'deadline','app_end_fsync':'fsync','generation':'replaced','cancel':'cancelled'}[launch['fault']]
        need(expected in reason.lower(),'declared fault did not hit intended gate: '+reason)
        return dict(status='PASS_FAILED_RESIDENT_ZERO_APP_DELIVERY_RETAINED',tag=tag,fault=launch['fault'],
                    claims=r['independent_page']['claims'],application_answers=0,BOARD='NOT_TESTED',release_allowed=False,
                    complete_bytes_prove_fsync=False)
    need(r['worker_exit_code']==0 and not r['independent_page']['unknown_io'] and not r['independent_page']['active'],'normal context not idle/terminal')
    need(not (folder/'state/DIRTY.json').exists() and not (folder/'application-state/DIRTY.json').exists(),'normal durable close missing')
    need(packets[0]['type']=='ready' and packets[-1]['type']=='private_closed' and
         packets[-1]['private_control']['closed'] is True,'native lifecycle packets differ')
    begin=[q for q in native if q['event']=='BEGIN'];ends=[q for q in native if q['event']=='END']
    need(len(begin)==len(ends)==len(r['completed']) and r['completed']==list(IDS[:len(begin)]),'bounded request order differs')
    results=[q for q in packets if q['type'] in ('cache_created','result')]
    need(len(results)==len(begin) and len([q for q in results if q['type']=='cache_created'])==1,'warm repeated/missing')
    ready=packets[0];residency=ready['bridge']['a12_route'];need(residency['weight_load_count']==72,'not exactly72 loads')
    total=0
    for index,(b,e,result) in enumerate(zip(begin,ends,results)):
        ident=IDS[index];need(b['request']['id']==e['request_id']==result['id']==ident and b['request_sha256']==digest(b['request'])==e['request_sha256'],'native request identity differs')
        need(b['base']==total and b['base']+b['budget']<=5000 and e['result_sha256']==digest(result),'native attempt budget/result differs')
        new=34 if index==0 else result['prefix_cache_request']['new_tokens']
        decode=0 if index==0 else result['decode_calls'];calls=72*((new+7)//8+decode)
        total+=calls;route=result['bridge']['a12_route'];pc=route['a12_private_control']
        need(e['verified_backend_calls']==calls and e['final_job']==total==route['pc_attempted_calls']==route['pc_started_calls']==route['pc_verified_completions']==route['cpu_run_count'],'actual CPU counters differ')
        need(pc['copy_checks']==calls and e['graph_copy_checks']==calls and pc['checked_copy_bytes']==e['graph_checked_bytes']>0,'graph-copy checks differ')
        need(result['state_cleared_before_response'] is True and result['state_position_after_clear']==-1 and route['pc_output_consumable'] is True,'uncleared/unverified result')
        need(route['weight_load_count']==72 and route['weight_count']==72 and route['hardware_done_count'] is None,'residency/CPU domain differs')
        grants=[q for q in native if q['event']=='GRANT' and b['monotonic_ns']<q['monotonic_ns']<e['monotonic_ns']]
        need(sum(q['last_job']-q['first_job']+1 for q in grants)==calls,'grant/call accounting differs')
        for q in grants:need(1<=q['last_job']-q['first_job']+1<=launch.get('cap',r['cap']),'grant bound differs')
        receipt=read(folder/'state'/(ident+'-receipt.json'))
        need(receipt['END_sha256']==e['sha256'] and receipt['result_sha256']==digest(result),'native durable receipt differs')
        checked=read(folder/(ident+'-MODEL_RESULT.json'));need(checked['result']==result,'native captured/model result differs')
        fence(checked['delivery_fence'],e['monotonic_ns'])
    need(total==r['claims']==r['independent_page']['claims'] and r['independent_page']['request_serial']==len(begin),'terminal cumulative count differs')
    probe=Probe(read(OUT/'SERVICE_BUILD-v3.json'));render=ImmutableSandboxedEnvironment().from_string(Path(probe.build['chat_template']).read_text())
    session=None;pending={};played=[];case=None;seen=set();plans={};timings=[]
    ends_by_id={q['request_id']:q for q in app if q['event']=='INPUT_END'}
    for row in app:
        if row['event']=='SESSION_OPEN':
            case=probe.app.domain.load_case(row['case_id']);need(case.sha256==row['case_sha256'],'application case differs');played=[];pending={}
        elif row['event']=='INPUT_BEGIN':
            t=probe.app.domain.Transcript.parse(row['input']);need(t.request_id not in seen,'input replayed');seen.add(t.request_id)
            plan=probe.app.planning.plan(case,t,played);need(digest(plan.to_dict())==row['plan_sha256'],'original trusted plan/history differs');plans[t.request_id]=plan
        elif row['event']=='INPUT_END':
            answer=next(q for q in answers if q['request_id']==row['request_id'])
            prepared=next(read(p) for p in folder.glob('input_*-PREPARED.json') if read(p)['request_id']==row['request_id'])
            need(digest(prepared)==row['prepared_response_sha256']==answer['prepared_response_sha256'],'prepared app result differs')
            plan=plans[row['request_id']];check=probe.app.checking.check(plan,answer['text']);need(check['status']=='pass' and check==answer['final_check'],'original content checker differs')
            need(digest(answer['answer_plan'])==digest(plan.to_dict()) and answer['worker_pid']==ready['bridge']['a12_route']['pc_plm']['page']['worker_pid'],'app/native plan/worker differs')
            if plan.route=='answer':
                need(answer['answer_source']=='MODEL' and answer['llm_calls']==1,'template counted as model')
                nb=next(q for q in begin if q['request']['id']==row['native_request_id'])
                prompt=render.render(messages=probe.app.checking.prompt_messages(plan,''),add_generation_prompt=True,enable_thinking=False)
                need(nb['request']['prompt']==prompt and answer['text']==next(q['text'] for q in results if q['id']==row['native_request_id']),'app prompt/model text differs')
            else:need(answer['answer_source']=='TEMPLATE' and answer['llm_calls']==0,'policy invoked model')
            fence(answer['delivery_fence'],row['monotonic_ns'])
            need(answer['application_received_ns']<=row['monotonic_ns']<=answer['application_delivered_ns'] and
                 answer['input_to_verified_result_s']==(answer['application_delivered_ns']-answer['application_received_ns'])/1e9,'application timing excludes work')
            pending=dict(request_id=answer['request_id'],turn_id=answer['turn_id'],epoch=answer['epoch'],
                         text=answer['text'],text_sha256=digest(answer['text']),fact_ids=list(plan.required_fact_ids),delivery_kind='PC_TEXT_TEST_ACK',audio_played=False)
            timings.append(answer['input_to_verified_result_s'])
        elif row['event']=='HOST_TEXT_ACK':
            need(pending and row['request_id']==pending['request_id'] and row['application_epoch']==pending['epoch'] and row['audio_played'] is False,'foreign host delivery ack')
            played.append(pending);pending={}
    need(len(answers)==len(ends_by_id) and not pending,'application deliveries missing/unacknowledged')
    return dict(status='PASS_RAW_RESIDENT_MODEL_AND_APP_ORDER',tag=tag,model_answers=len(r['application_generated']),
                policy_answers=len(answers)-len(r['application_generated']),calls=total,warm_count=1,weight_loads=72,
                input_to_verified_result_s=timings,BOARD='NOT_TESTED',actual_FPGA_calls=None,release_allowed=False,
                complete_bytes_prove_fsync=False)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--tag',required=True);a=p.parse_args()
    result=audit(a.tag);save(OUT/a.tag/'AUDIT.json',result);print(result['status'],a.tag)
