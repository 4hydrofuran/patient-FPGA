"""One explicitly selected actual-CPU resident window; all attempts retained."""
import argparse
import os
import select
import shutil
import time
import threading
from resident_evidence import ROOT, OUT, WORK, read, save, pin
from resident_service import ResidentService
from livegen_binding import ReadOnlyPage


def main():
    p=argparse.ArgumentParser();p.add_argument('--tag',required=True);p.add_argument('--scenario',choices=('flow','capacity','cohort','policy','fault'),default='flow')
    p.add_argument('--start',type=int,default=0);p.add_argument('--count',type=int,default=3)
    p.add_argument('--fault',choices=('begin_fsync','end_fsync','receipt_fsync','end_slow','deadline','delivery_deadline','app_end_fsync','generation','cancel','busy'))
    a=p.parse_args();assert a.tag.isalnum();os.umask(0o077)
    folder=OUT/a.tag;folder.mkdir();directory=WORK/a.tag;build=OUT/'SERVICE_BUILD-v3.json';b=read(build)
    save(folder/'LAUNCH.json',dict(source=[pin(q) for q in sorted((ROOT/'platform/qwen35/a12').glob('resident_*.py'))],
                                 scenario=a.scenario,fault=a.fault,BOARD='NOT_TESTED'))
    svc=ResidentService(build,directory);observer=None;fd=None;events=[];error=None
    def record(op,value):
        events.append(dict(op=op,value=value));save(folder/('EVENT_'+str(len(events)).zfill(3)+'.json'),events[-1]);return value
    def check(v,msg):
        if not v:raise RuntimeError(msg)
    def ask(case,question,name):
        if a.scenario!='flow' or svc.session is None or svc.session.snapshot()['case_id']!=case:
            r=record('open_session',svc.open_session(case));check(r['type']=='session_opened',str(r))
        t=dict(request_id=name,text=question,source='typed',final=True)
        if a.fault=='generation':svc.manager.injection='same_uuid_reload'
        r=record('submit',svc.submit(t,timeout_s=.001 if a.fault=='deadline' else 30))
        return t,r
    try:
        r=record('start',svc.start());check(r['type']=='ready',str(r))
        m=svc.manager;fd=os.dup(m.pidfd);observer=ReadOnlyPage(m.page,b['observer_library'],b['observer_sha256'])
        pid=m.p.pid;loads=m.loads
        if a.scenario=='fault':
            check(a.fault is not None,'fault required')
            if a.fault=='app_end_fsync':
                svc.journal.fault='app_end_fsync'
            elif a.fault in ('begin_fsync','end_fsync','receipt_fsync','end_slow'):m.journal.fault=a.fault
            elif a.fault=='generation':pass  # arm after a healthy session-open fence
            elif a.fault=='delivery_deadline':
                original=m.execute
                def expire_after_native(request):
                    result=original(request);m.current_deadline=time.monotonic_ns()-1;return result
                m.execute=expire_after_native
            elif a.fault in ('cancel','busy'):
                original=m.execute
                def intercept(request):
                    if request['op']=='generate':
                        def contender():
                            result=(svc.cancel() if a.fault=='cancel' else svc.submit(dict(request_id='concurrent',text='哪里疼痛？',source='typed',final=True)))
                            record('concurrent_'+a.fault,result)
                        t=threading.Thread(target=contender);t.start();t.join(2);check(not t.is_alive(),'contender stuck')
                    return original(request)
                m.execute=intercept
            t,r=ask('SYN_CP_01','疼痛在什么位置？','fault1')
            if a.fault=='busy':
                check(r['type']=='validated_answer' and not svc.failed,'busy affected active operation')
                ack=record('host_ack',svc.acknowledge(r['request_id'],r['epoch']));check(ack['type']=='delivery_ack',str(ack))
                closed=record('close',svc.close());check(closed['type']=='closed',str(closed));result=closed['result']
            else:
                check(r['type']=='error' and r['tts_ready'] is False and svc.failed,'fault unexpectedly delivered')
                result=m.failed_observation('EXPECTED_'+a.fault)
        else:
            if a.scenario=='policy':
                rows=read(ROOT/'evidence/model_pl_A/20261026-short-prompt-v1/facts-only-02/WORKLOADS.json')['policy_inputs']
                requests=[('SYN_CP_01',q['question'],q['id']) for q in rows]
            elif a.scenario=='cohort':
                rows=read(ROOT/'evidence/model_pl_A/20261026-short-prompt-v1/facts-only-02/WORKLOADS.json')['real_inputs'][a.start:a.start+a.count]
                requests=[(q['application']['case_id'],q['application']['question'],q['id']) for q in rows]
            elif a.scenario=='capacity':requests=[('SYN_CP_01','什么方法能减轻疼痛？','capacity'+str(i)) for i in range(7)]
            else:requests=[('SYN_CP_01','疼痛在什么位置？','flow1'),('SYN_CP_01','刚才呢？','flow2'),('SYN_CP_03','疼痛在什么位置？','flow3')]
            for case,question,name in requests:
                t,r=ask(case,question,name)
                if a.scenario=='capacity' and r['type']=='error':
                    check(r['code']=='capacity' and not r['fatal'],'capacity failed after submission');break
                check(r['type']=='validated_answer' and r['answer_source']==('TEMPLATE' if a.scenario=='policy' else 'MODEL') and r['tts_ready'] is True,str(r))
                check(m.p.pid==pid and m.loads==loads==72 and len(m.control_results)==1+len(svc.generated),'not one resident worker')
                if a.scenario=='flow' and name=='flow1':
                    before=m.claims;dup=record('duplicate',svc.submit(t));check(dup['code']=='duplicate_input' and m.claims==before,'duplicate submitted')
                    pending=record('pending',svc.submit(dict(t,request_id='pending1')));check(pending['code']=='delivery_pending' and m.claims==before,'pending input submitted')
                ack=record('host_ack',svc.acknowledge(r['request_id'],r['epoch']));check(ack['type']=='delivery_ack',str(ack))
            closed=record('close',svc.close());check(closed['type']=='closed',str(closed));result=closed['result']
            if a.scenario=='capacity':check(len(svc.generated)>=4 and len(svc.generated)<8,'capacity boundary not exercised')
    except BaseException as exc:
        error=type(exc).__name__+': '+str(exc)
        m=svc.manager
        result=m.failed_observation(error) if m is not None and getattr(m,'monitor',None) else dict(status='CONSTRUCTOR_FAILED')
    done=False
    if fd is not None:
        poll=select.poll();poll.register(fd,select.POLLIN);done=bool(poll.poll(0))
    result.update(error=error,owned_pidfd_terminal=done,independent_page=observer() if observer else None,
                  application_generated=svc.generated,external_inputs=len(svc.inputs),rejections=svc.rejections)
    if svc.manager is not None and svc.manager.p is not None and not done:
        save(folder/'LIVE_WAIT.json',result);raise RuntimeError('native still live; retain and observe, no restart')
    if directory.exists():
        for q in directory.rglob('*'):
            if q.is_file():
                target=folder/q.relative_to(directory);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(q,target)
    save(folder/'RESULT.json',result)
    if observer:observer.close()
    if fd is not None:os.close(fd)
    print('PASS_RESIDENT_'+a.scenario.upper() if error is None else error,flush=True)
    if error:raise SystemExit(1)


if __name__=='__main__':main()
