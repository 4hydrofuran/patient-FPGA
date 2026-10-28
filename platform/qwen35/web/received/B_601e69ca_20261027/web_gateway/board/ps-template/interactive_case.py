"""User-operated single question, warmed prefix and retained HDMI desktop."""
import copy
import json
from pathlib import Path
import subprocess
import threading
import time

from board_case import WorkerTransport, load_native
from graphical_runtime import settle_terminal

SERVER = THREAD = APP = None


class CachedTransport(WorkerTransport):
    def __init__(self, *args, maximum_questions=1):
        super().__init__(*args)
        self.binding = None
        self.answer_requested = False
        self.warm_result = None
        self.maximum_questions=maximum_questions
        self.questions_sent=0
        self.pending_id=None
        self.receive_failed=False

    def warm(self, ready, request):
        self.binding = ready['prefix_cache']['binding_sha256']
        request = copy.deepcopy(request)
        request['cache_binding_sha256'] = self.binding
        self.inflight = True
        self.pending_id=request['id']
        self.worker.send(request)
        while True:
            result = self.api.receive(self.worker, self.owner, self.path, timeout=180)
            if result.get('type')=='cache_created':
                self.inflight = False
                self.warm_result = result
                assert result['id']==request['id'] and result['status']=='OK'
                assert result['state_cleared_before_response'] and result['state_position_after_clear']==-1
                assert result['prefix_cache']['binding_sha256']==self.binding
                assert any(e['tokens']==70 for e in result['prefix_cache']['entries'])
                return result
            if result.get('type')=='error':
                self.inflight = False
                raise RuntimeError('Prefix preparation failed: '+str(result))

    def send(self, request):
        if self.maximum_questions is not None and self.questions_sent>=self.maximum_questions:
            raise RuntimeError('This window has consumed its model question allowance')
        request = dict(request, cache_policy='TT10_REQUIRE_HIT', cache_id='neutral',
                       cache_binding_sha256=self.binding, prefill_chunk=256,
                       profile=False, diagnostic_report=False)
        self.answer_requested = True
        self.pending_id=request['id']
        result=super().send(request)
        self.questions_sent+=1
        return result

    def get(self, timeout):
        try:result = super().get(timeout)
        except BaseException:
            self.receive_failed=True
            raise
        if result.get('type')=='result':
            cache = result['prefix_cache_request']
            assert cache['hit'] is True and cache['reused_tokens']==70
        return result


def desktop_environment():
    for p in Path('/proc').iterdir():
        if not p.name.isdigit():
            continue
        try:
            if p.stat().st_uid==1000 and (p/'comm').read_text().strip()=='gsd-power':
                values=dict(x.split('=',1) for x in (p/'environ').read_bytes().decode().split('\0') if '=' in x)
                return {k:values[k] for k in ('DBUS_SESSION_BUS_ADDRESS','DISPLAY','WAYLAND_DISPLAY','XDG_RUNTIME_DIR','XAUTHORITY') if k in values}
        except (FileNotFoundError,PermissionError):
            pass
    raise RuntimeError('Logged-in desktop is required')


def run_case(worker, owner, path, *, real, api, overlay):
    global SERVER, THREAD, APP
    import uvicorn
    from patient_web.errors import GatewayError
    from web_managed import create_app
    assert real
    path, overlay = Path(path), Path(overlay)
    config_path=overlay/'web-config.json'
    config=json.loads(config_path.read_text()) if config_path.exists() else {}
    continuous=config.get('continuous',False)
    maximum_questions=None if continuous else config.get('maximum_questions',1)
    assert continuous is True or maximum_questions in (1,2)
    transport = CachedTransport(worker,owner,path,api,maximum_questions=maximum_questions)
    ready = api.receive(worker,owner,path,timeout=180)
    api.save(path/'ready.json',ready)
    api.validate_bo(ready['bridge']['a12_route'])
    owner.full_resident=True
    api.save(path/'graphical-allocation.json',dict(status='ACTUAL_FULL_BO_ALLOCATION_VERIFIED',
             charged_bytes=140591104,bo_count=148,weight_count=72,low_2GiB=True))
    requests=json.loads((api.BUNDLE/'control/requests.json').read_text())
    warm=next(r for r in requests if r['id']=='warm_prefix')
    transport.warm(ready,warm)
    api.save(path/'warm-result.json',transport.warm_result)
    native=load_native(overlay,'/opt/patient-qwen')(transport,ready,max_output_tokens=24)
    from continuous_sessions import question_reserve
    budget_available=lambda: not continuous or worker.max_runs-worker.runs>=question_reserve()
    accepting=threading.Event();accepting.set()
    alive=lambda: (accepting.is_set() and budget_available() and not owner.finished and not worker.closed and not worker.quarantined
                   and not worker.delivery_cancelled and worker.process.poll() is None)
    APP=create_app(native,is_ready=alive,remaining_seconds=lambda:(owner.expires-time.monotonic_ns())/1e9)
    coordinator=APP.state.coordinator
    if continuous:
        original_status=coordinator.status
        def continuous_status():
            result=original_status()
            result.update(service_mode='continuous',remaining_seconds=max(0,(owner.expires-time.monotonic_ns())/1e9))
            result['capabilities']['archived_sessions_readable']=True
            if not result['ready'] and (not accepting.is_set() or not budget_available() or result['remaining_seconds']<180):
                result['failure']=dict(code='SERVICE_WINDOW_ENDED',message='本次服务运行已结束，问诊记录已保存。')
            return result
        coordinator.status=continuous_status
    original_submit=coordinator.submit
    def single_submit(sid,rid,text):
        with coordinator.lock:
            conversation=coordinator._conversation(sid)
            previous=coordinator._duplicate(conversation,rid,'turn',text)
            if previous:
                return previous
            if conversation.turns:
                raise GatewayError('SINGLE_QUESTION_COMPLETE','本次提问已完成，请点击“结束问诊”查看评价。')
            return original_submit(sid,rid,text)
    if continuous:
        from continuous_sessions import install
        install(coordinator,path/'consultations')
    else:
        coordinator.submit=single_submit
    SERVER=uvicorn.Server(uvicorn.Config(APP,host='127.0.0.1',port=8000,workers=1,log_level='info'))
    THREAD=threading.Thread(target=SERVER.run,name='manual-web',daemon=True)
    THREAD.start()
    for _ in range(100):
        if SERVER.started and coordinator.initialized.is_set():
            break
        time.sleep(.1)
    else:
        raise RuntimeError('Web initialization failed')
    if config.get('open_browser',True):
        # A desktop login may be recreated while the PL is being prepared. Keep the
        # valid HTTP/model window alive while waiting, rather than escaping ownership.
        while True:
            try:
                env=desktop_environment()
                break
            except RuntimeError:
                if time.monotonic_ns()>=owner.expires-180_000_000_000:
                    assert worker.close(timeout=30)
                    return transport.warm_result
                time.sleep(1)
        command=['runuser','-u','ubuntu','--','env',*[k+'='+v for k,v in env.items()],
                 'MOZ_AVOID_OPENGL_ALTOGETHER=1']
        subprocess.run(command+['gsettings','set','org.gnome.desktop.a11y.applications','screen-keyboard-enabled','true'],check=True)
        profile=config.get('browser_profile','/home/ubuntu/snap/firefox/common/manual-pl-20261026-v2')
        subprocess.run(['runuser','-u','ubuntu','--','/usr/bin/python3','-c',
                        'import json;from pathlib import Path;p=Path('+repr(profile)+');p.mkdir(exist_ok=True);'
                        'prefs={"layers.acceleration.disabled":True,"gfx.webrender.software":True,"webgl.disabled":True};'
                        '(p/"user.js").write_text("".join("user_pref("+json.dumps(k)+","+json.dumps(v)+");\\n" for k,v in prefs.items()))'],check=True)
        with (path/'browser.log').open('xb') as log:
            browser=subprocess.Popen(command+['gnome-session-inhibit','--inhibit','idle','--reason','Manual-PL-consultation',
                '/snap/bin/firefox','--no-remote','--profile',profile,'--remote-debugging-port','9222','--kiosk','http://127.0.0.1:8000/'],
                stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
        api.save(path/'INTERACTIVE_READY.json',dict(status='READY_WAITING_FOR_USER_INPUT',url='http://127.0.0.1:8000/',
                 backend='FPGA_REAL',prefix_warmed=True,prefix_tokens=70,model_questions=0,browser_pid=browser.pid,
                 maximum_questions=maximum_questions,expires_monotonic_ns=owner.expires))
    else:
        api.save(path/'INTERACTIVE_READY.json',dict(status='READY_SERIAL_API_MODE',url='http://127.0.0.1:8000/',backend='FPGA_REAL',prefix_warmed=True,browser_pid=None))
    if config.get('verify_first'):
        from verify_graphical import verify_first
        verify_first(worker,owner,path,api,transport)
    if config.get('verify_continuous'):
        from verify_continuous import verify_continuous
        verify_continuous(worker,owner,path,api,transport)
    from continuous_sessions import may_end
    while time.monotonic_ns()<owner.expires-180_000_000_000:
        with coordinator.lock:
            sid=coordinator.current_session
            conversation=coordinator.conversations.get(sid) if sid else None
            done=may_end(continuous=continuous,closed=conversation is not None and conversation.closed,
                         idle=coordinator.work is None,model_requests=native.count,
                         maximum_questions=maximum_questions,broken=native.broken,
                         stop_requested=(overlay/'stop-request.json').exists() or not budget_available())
        if done:
            break
        owner.platform.health_schedule.idle(owner._health_observation,owner.owner_check)
        time.sleep(1)
    accepting.clear()
    drain_deadline=min(time.monotonic()+180,owner.expires/1e9-5)
    while coordinator.work is not None and time.monotonic()<drain_deadline:
        time.sleep(.25)
    if coordinator.work is not None:
        raise RuntimeError('Active web call has not completed; original owner retained')
    if transport.inflight and not settle_terminal(transport,timeout=10):
        raise RuntimeError('Terminal response not confirmed in bounded close; original owner retained')
    with coordinator.lock:
        if continuous and sid and not coordinator.conversations[sid].closed and coordinator.work is None:
            coordinator.finish(sid,'host-service-close')
        snapshot=coordinator.snapshot(sid) if sid else None
    api.save(path/'manual-session.json',snapshot)
    result=transport.last_result or transport.warm_result
    api.save(path/'native-result.json',result)
    assert worker.close(timeout=30) and worker.closed and worker.process.returncode==0
    api.save(path/'manual-compute-closed.json',dict(worker_exit=0,permission_runs=worker.runs,
             model_requests=native.count,prefix_hit=result.get('prefix_cache_request',{}).get('hit')))
    return result


def keep_result_service(seconds=1800):
    """After PS releases hardware, keep the completed session readable."""
    if SERVER is not None:
        time.sleep(seconds)
        SERVER.should_exit=True
        THREAD.join(timeout=15)
