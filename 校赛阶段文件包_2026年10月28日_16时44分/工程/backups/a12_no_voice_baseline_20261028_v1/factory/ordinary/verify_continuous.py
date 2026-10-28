"""Verify two questions in one consultation and another in a fresh one."""
import base64
import json
from pathlib import Path
import time
from browser_bidi import Bidi
from verify_graphical import http


def verify_continuous(worker,owner,path,api,transport):
    path=Path(path);ws=None
    report=dict(status='RUNNING_CONTINUOUS_GUI_VERIFICATION',turns=[],sessions=[])
    try:
        for _ in range(120):
            try:ws=Bidi();break
            except ConnectionRefusedError:time.sleep(.25)
        else:raise RuntimeError('Graphical Firefox did not start')
        ws.s.settimeout(200);ws.call('session.new',{'capabilities':{}})
        context=ws.call('browsingContext.getTree',{})['contexts'][0]['context']
        def evaluate(js):
            r=ws.call('script.evaluate',dict(expression=js,target={'context':context},awaitPromise=True))
            if r.get('type')=='exception':raise RuntimeError(str(r))
            return r.get('result',{}).get('value')
        def wait(condition):
            script='(async()=>{for(let i=0;i<150;i++){if('+condition+')return true;await new Promise(r=>setTimeout(r,100));}return false;})()'
            if evaluate(script) is not True:raise RuntimeError('GUI condition failed: '+condition)
        def screenshot(name):
            (path/name).write_bytes(base64.b64decode(ws.call('browsingContext.captureScreenshot',{'context':context})['data']))
        wait("document.getElementById('cases').options.length===3 && !document.getElementById('start').disabled")
        for index,(case,questions) in enumerate((('SYN_CP_03',('每次疼痛持续多久？','疼痛在哪里？')),('SYN_CP_01',('每次疼痛持续多久？',)))):
            evaluate("document.getElementById('cases').value="+json.dumps(case)+";document.getElementById('start').click();true")
            wait("!document.getElementById('question').disabled")
            sid=http('/ui/v1/status')['current_session_id'];report['sessions'].append(sid)
            for turn_index,question in enumerate(questions):
                before=time.monotonic()
                evaluate("document.getElementById('question').value="+json.dumps(question)+";document.getElementById('question-form').requestSubmit();true")
                deadline=time.monotonic()+190
                while time.monotonic()<deadline:
                    snapshot=http('/ui/v1/sessions/'+sid)
                    if len(snapshot['turns'])>turn_index and snapshot['turns'][turn_index]['status'] in ('COMPLETED','FAILED','CANCELLED'):break
                    time.sleep(.25)
                else:raise RuntimeError('Continuous answer deadline')
                turn=snapshot['turns'][turn_index]
                receipt=http('/ui/v1/sessions/'+sid+'/turns/'+turn['request_id'])
                api.save(path/('multi-turn-'+str(len(report['turns'])+1)+'.json'),receipt)
                assert turn['status']=='COMPLETED' and receipt['answer_source']=='MODEL' and receipt['actual_backend']=='FPGA_REAL'
                assert receipt['delivery_receipt']['validation_status']=='pass'
                native=transport.last_result;cache=native['prefix_cache_request']
                assert native['status']=='OK' and cache['hit'] and cache['reused_tokens']==70
                api.save(path/('multi-native-'+str(len(report['turns'])+1)+'.json'),native)
                report['turns'].append(dict(session_id=sid,case_id=case,question=question,answer=receipt['answer'],
                    wall_seconds=time.monotonic()-before,backend=receipt['actual_backend'],cache=cache))
                wait("!document.getElementById('question').disabled && !document.getElementById('send').disabled")
            screenshot('multi-session-'+str(index+1)+'-answers.png')
            evaluate("document.getElementById('finish').click();true")
            wait("!document.getElementById('evaluation-result').hidden && !document.getElementById('new-session').disabled")
            evaluation=http('/ui/v1/sessions/'+sid+'/evaluation')
            api.save(path/('multi-evaluation-'+str(index+1)+'.json'),evaluation)
            assert evaluation['frozen_turn_count']==len(questions)
            assert http('/ui/v1/status')['ready']
            screenshot('multi-session-'+str(index+1)+'-evaluation.png')
            # Starting the next consultation uses the same visible Start control.
            # Keep case selection available on the finished view.
        evaluate("document.getElementById('cases').value='SYN_CP_03';document.getElementById('new-session').click();true")
        wait("!document.getElementById('question').disabled")
        user_sid=http('/ui/v1/status')['current_session_id']
        user=http('/ui/v1/sessions/'+user_sid)
        assert user_sid not in report['sessions'] and not user['turns'] and not user['closed']
        screenshot('multi-user-input-ready.png')
        report.update(status='PASS_CONTINUOUS_GUI_MULTI_TURN_AND_NEW_SESSION',user_session_id=user_sid,
            user_questions_sent=0,weight_loads=worker.loads,permission_runs=worker.runs,
            worker_pid=worker.process.pid,remaining_seconds=(owner.expires-time.monotonic_ns())/1e9)
        assert worker.loads==72
        api.save(path/'USER_INPUT_READY.json',dict(status='READY_FOR_CONTINUOUS_CONSULTATIONS',session_id=user_sid,
            expires_monotonic_ns=owner.expires,questions_per_consultation='MULTIPLE',new_consultations=True))
    except BaseException as exc:
        report.update(status='FAILED_CONTINUOUS_GUI_VERIFICATION',error=type(exc).__name__+': '+str(exc));raise
    finally:
        api.save(path/'CONTINUOUS_VERIFICATION.json',report)
        if ws:ws.s.close()
