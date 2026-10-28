"""One real GUI question, then leave a separate empty session for the user."""
import base64
import json
from pathlib import Path
import time
import urllib.request
from browser_bidi import Bidi


def http(path):
    return json.load(urllib.request.urlopen('http://127.0.0.1:8000'+path,timeout=5))


def verify_first(worker,owner,path,api,transport):
    path=Path(path);ws=None
    report=dict(status='RUNNING_REAL_GUI_VERIFICATION',case_id='SYN_CP_03')
    try:
        for _ in range(120):
            try:ws=Bidi();break
            except ConnectionRefusedError:time.sleep(.25)
        else:raise RuntimeError('Graphical Firefox debugging endpoint did not start')
        ws.s.settimeout(200)
        caps=ws.call('session.new',{'capabilities':{}})
        report['browser_version']=caps['capabilities'].get('browserVersion')
        context=ws.call('browsingContext.getTree',{})['contexts'][0]['context']
        def evaluate(expression):
            r=ws.call('script.evaluate',dict(expression=expression,target={'context':context},awaitPromise=True))
            if r.get('type')=='exception':raise RuntimeError(str(r))
            return r.get('result',{}).get('value')
        def wait(condition,seconds=15):
            js='(async()=>{for(let i=0;i<'+str(seconds*10)+';i++){if('+condition+')return true;await new Promise(r=>setTimeout(r,100));}return false;})()'
            if evaluate(js) is not True:raise RuntimeError('GUI condition not met: '+condition)
        def screenshot(name):
            data=ws.call('browsingContext.captureScreenshot',{'context':context})['data']
            (path/name).write_bytes(base64.b64decode(data))
        wait("document.getElementById('cases').options.length===3 && !document.getElementById('start').disabled")
        screenshot('real-gui-ready.png')
        evaluate("document.getElementById('cases').value='SYN_CP_03';document.getElementById('start').click();true")
        wait("!document.getElementById('question').disabled")
        question='每次疼痛持续多久？'
        begin=time.monotonic()
        evaluate("document.getElementById('question').value="+json.dumps(question)+";document.getElementById('question-form').requestSubmit();true")
        sid=http('/ui/v1/status')['current_session_id']
        deadline=time.monotonic()+190
        while time.monotonic()<deadline:
            snapshot=http('/ui/v1/sessions/'+sid)
            if snapshot['turns'] and snapshot['turns'][0]['status'] in ('COMPLETED','FAILED','CANCELLED'):break
            time.sleep(.25)
        else:raise RuntimeError('Real GUI answer deadline')
        report['question_to_answer_seconds']=time.monotonic()-begin
        turn=snapshot['turns'][0]
        receipt=http('/ui/v1/sessions/'+sid+'/turns/'+turn['request_id'])
        api.save(path/'verification-turn.json',receipt)
        assert turn['status']=='COMPLETED' and receipt['answer_source']=='MODEL' and receipt['actual_backend']=='FPGA_REAL'
        assert receipt['delivery_receipt']['model_called'] and receipt['delivery_receipt']['validation_status']=='pass'
        result=transport.last_result
        expected_prefix=transport.pending_prefix['prefix_tokens']
        assert result['prefix_cache_request']['hit'] and result['prefix_cache_request']['reused_tokens']==expected_prefix
        report.update(answer=receipt['answer'],backend='FPGA_REAL',answer_source='MODEL',
                      prefix_cache_request=result['prefix_cache_request'],native_request_wall_ms=result['request_profile']['native_request_wall_ms'])
        wait("!document.getElementById('finish').disabled")
        screenshot('real-gui-answer.png')
        evaluate("document.getElementById('finish').click();true")
        wait("!document.getElementById('evaluation-result').hidden")
        api.save(path/'verification-evaluation.json',http('/ui/v1/sessions/'+sid+'/evaluation'))
        screenshot('real-gui-evaluation.png')
        wait("!document.getElementById('new-session').disabled")
        evaluate("document.getElementById('new-session').click();true")
        wait("!document.getElementById('question').disabled")
        user_sid=http('/ui/v1/status')['current_session_id']
        user_snapshot=http('/ui/v1/sessions/'+user_sid)
        assert user_sid!=sid and not user_snapshot['turns'] and not user_snapshot['closed']
        screenshot('user-input-ready.png')
        report.update(status='PASS_REAL_GRAPHICAL_MODEL_FPGA_QUESTION',test_session_id=sid,
                      user_session_id=user_sid,user_questions_sent=0,permission_runs=worker.runs,weight_loads=worker.loads)
        remaining=None if transport.maximum_questions is None else max(0,transport.maximum_questions-transport.questions_sent)
        api.save(path/'USER_INPUT_READY.json',dict(status='READY_FOR_USER_INPUT',
                 session_id=user_sid,model_questions_remaining=remaining,expires_monotonic_ns=owner.expires))
    except BaseException as exc:
        report.update(status='FAILED_REAL_GRAPHICAL_VERIFICATION',error=type(exc).__name__+': '+str(exc))
        raise
    finally:
        api.save(path/'WEB_REAL_VERIFICATION.json',report)
        if ws:ws.s.close()
