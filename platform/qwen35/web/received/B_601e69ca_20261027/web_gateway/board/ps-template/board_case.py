"""One real browser question over an existing accepted PS worker lifecycle."""
import base64
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import threading
import time
import types
import urllib.request


class WorkerTransport:
    def __init__(self, worker, owner, path, api):
        self.worker, self.owner, self.path, self.api = worker, owner, path, api
        self.last_result = None
        self.inflight = False

    def send(self, request):
        if self.inflight:
            raise RuntimeError('Only one web generation is allowed at a time')
        self.inflight = True
        self.worker.send(request)

    def get(self, timeout):
        result = self.api.receive(self.worker, self.owner, self.path, timeout=timeout)
        if result.get('type') in ('result', 'error'):
            self.inflight = False
            self.last_result = result
        return result


def load_native(overlay, asset_root):
    name = '_board_web_native'
    package = types.ModuleType(name)
    package.__path__ = [str(overlay)]
    sys.modules[name] = package
    asset_module = types.ModuleType(name+'.native')
    asset_module.ROOT = Path(asset_root)
    sys.modules[name+'.native'] = asset_module
    spec = importlib.util.spec_from_file_location(name+'.native_pl', overlay/'native_pl.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.NativePL


def run_case(worker, owner, path, *, real, api, overlay):
    assert real is True
    from browser_bidi import Bidi
    from web_managed import create_app
    import uvicorn
    overlay, path = Path(overlay), Path(path)
    transport = WorkerTransport(worker, owner, path, api)
    ready = api.receive(worker, owner, path, timeout=180)
    api.save(path/'ready.json', ready)
    native = load_native(overlay, '/opt/patient-qwen')(transport, ready, max_output_tokens=24)
    alive = lambda: (not owner.finished and not worker.quarantined
                     and not worker.delivery_cancelled and not worker.closed
                     and worker.process.poll() is None)
    app = create_app(native, is_ready=alive,
                     remaining_seconds=lambda: (owner.expires-time.monotonic_ns())/1e9,
                     generation_timeout_s=180)
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=8000,
                                          workers=1, log_level='info'))
    thread = threading.Thread(target=server.run, name='web-frontend', daemon=True)
    thread.start()
    browser = ws = None
    report = dict(scope='ONE_ACTUAL_BOARD_FIREFOX_PL_QUESTION', ready_kind=ready.get('execution_kind'))
    def http(route):
        with urllib.request.urlopen('http://127.0.0.1:8000'+route, timeout=5) as response:
            return json.load(response)
    try:
        for _ in range(100):
            if server.started:
                break
            time.sleep(.1)
        else:
            raise RuntimeError('Web service did not start')
        status = http('/ui/v1/status')
        assert status['ready'] and status['backend']['execution_kind']=='FPGA_REAL'
        api.save(path/'web-status.json', status)
        profile = Path('/home/ubuntu/snap/firefox/common/pl-web-20261026-v1')
        subprocess.run(['runuser','-u','ubuntu','--','/usr/bin/python3','-c',
                        'from pathlib import Path;Path('+repr(str(profile))+').mkdir()'], check=True)
        with (path/'browser.log').open('xb') as log:
            browser = subprocess.Popen(['runuser','-u','ubuntu','--','/snap/bin/firefox',
                '--headless','--no-remote','--profile',str(profile),
                '--remote-debugging-port','9222','about:blank'], stdout=log, stderr=log)
        for _ in range(120):
            try:
                ws = Bidi()
                break
            except ConnectionRefusedError:
                time.sleep(.25)
        else:
            raise RuntimeError('Board browser did not start')
        ws.s.settimeout(200)
        caps = ws.call('session.new', {'capabilities': {}})
        report['browser_version'] = caps['capabilities'].get('browserVersion')
        context = ws.call('browsingContext.create', {'type':'tab'})['context']
        ws.call('browsingContext.setViewport', {'context':context,
                    'viewport':{'width':1024,'height':600},'devicePixelRatio':1})
        ws.call('browsingContext.navigate', {'context':context,
                    'url':'http://127.0.0.1:8000/','wait':'complete'})
        def evaluate(expression):
            result = ws.call('script.evaluate', {'expression':expression,
                       'target':{'context':context},'awaitPromise':True})
            if result.get('type')=='exception':
                raise RuntimeError(json.dumps(result))
            return result.get('result',{}).get('value')
        def wait(condition, seconds=15):
            expression = '(async()=>{for(let i=0;i<'+str(seconds*10)+';i++){if('+condition+')return true;await new Promise(r=>setTimeout(r,100));}return false;})()'
            if evaluate(expression) is not True:
                raise RuntimeError('Browser condition failed: '+condition)
        def screenshot(name):
            image = base64.b64decode(ws.call('browsingContext.captureScreenshot', {'context':context})['data'])
            (path/name).write_bytes(image)
        wait("document.getElementById('cases').options.length===3 && !document.getElementById('start').disabled")
        screenshot('browser-ready.png')
        evaluate("document.getElementById('start').click();true")
        wait("!document.getElementById('question').disabled")
        question = '\u6bcf\u6b21\u75bc\u75db\u6301\u7eed\u591a\u4e45\uff1f'
        begin = time.monotonic_ns()
        evaluate("document.getElementById('question').value="+json.dumps(question)+";document.getElementById('question-form').requestSubmit();true")
        wait("document.getElementById('turns').textContent.includes('10') && !document.getElementById('finish').disabled", 190)
        report['browser_question_to_answer_s'] = (time.monotonic_ns()-begin)/1e9
        screenshot('browser-answer.png')
        sid = http('/ui/v1/status')['current_session_id']
        snapshot = http('/ui/v1/sessions/'+sid)
        turn = snapshot['turns'][0]
        receipt = http('/ui/v1/sessions/'+sid+'/turns/'+turn['request_id'])
        api.save(path/'web-turn.json', receipt)
        delivery = receipt['delivery_receipt']
        assert receipt['answer_source']=='MODEL' and receipt['actual_backend']=='FPGA_REAL'
        assert delivery['model_called'] is True and delivery['validation_status']=='pass'
        report['answer'] = receipt['answer']
        evaluate("document.getElementById('finish').click();true")
        wait("!document.getElementById('evaluation-result').hidden && document.getElementById('total-score').textContent==='10'")
        screenshot('browser-evaluation.png')
        evaluation = http('/ui/v1/sessions/'+sid+'/evaluation')
        api.save(path/'web-evaluation.json', evaluation)
        report.update(verdict='PASS_BOARD_WEB_PL_SINGLE_QA', score=evaluation['rule_score']['score'],
                      error=evaluate("document.getElementById('error').textContent"),
                      permission_runs=worker.runs, weight_loads=worker.loads)
        assert report['error']==''
        try:
            ws.call('browser.close', {})
        except EOFError:
            pass
    except BaseException as exc:
        report.update(verdict='FAILED_BOARD_WEB_QA', error=type(exc).__name__+': '+str(exc))
    finally:
        if ws:
            ws.s.close()
        if browser:
            try:
                report['browser_exit'] = browser.wait(timeout=10)
            except subprocess.TimeoutExpired:
                browser.terminate()
                report['browser_exit'] = browser.wait(timeout=10)
        server.should_exit = True
        thread.join(timeout=15)
        report['web_thread_stopped'] = not thread.is_alive()
        api.save(path/'web-report.json', report)
    if transport.inflight:
        raise RuntimeError('Web request completion unknown; original owner retained')
    result = transport.last_result or ready
    api.save(path/'native-result.json', result)
    assert worker.close(timeout=30) and worker.closed and worker.process.returncode==0
    return result
