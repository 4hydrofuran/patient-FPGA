"""User-operated single question, warmed prefix and retained HDMI desktop."""
import copy
import json
from pathlib import Path
import subprocess
import threading
import time

from board_case import WorkerTransport, load_native
from graphical_runtime import settle_terminal
from fast_response_profile import LEGACY, load_profile, check_ready, builder
from neutral_prefixes import prefix_choices,select_prefix,warm_requests

SERVER = THREAD = APP = None


class CachedTransport(WorkerTransport):
    def __init__(self, *args, maximum_questions=1, profile=None):
        super().__init__(*args)
        self.binding = None
        self.answer_requested = False
        self.warm_result = None
        self.warm_results = {}
        self.maximum_questions=maximum_questions
        self.questions_sent=0
        self.pending_id=None
        self.receive_failed=False
        self.profile=dict(LEGACY if profile is None else profile)
        self.strict_profile=profile is not None
        self.pending_prefix=prefix_choices(self.profile)[0]

    def warm(self, ready, request):
        choice=next((p for p in prefix_choices(self.profile) if p['cache_id']==request.get('cache_id')),None)
        if self.strict_profile:
            check_ready(self.profile,ready)
            if choice is None or request.get('tokens')!=choice['prefix_token_ids']:
                raise RuntimeError('warm request differs from active profile')
        if choice is None:choice=prefix_choices(self.profile)[0]
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
                self.warm_results[choice['cache_id']]=result
                if choice['cache_id']==self.profile['cache_id']:self.warm_result = result
                assert result['id']==request['id'] and result['status']=='OK'
                assert result['state_cleared_before_response'] and result['state_position_after_clear']==-1
                assert result['prefix_cache']['binding_sha256']==self.binding
                assert any(e['tokens']==choice['prefix_tokens'] for e in result['prefix_cache']['entries'])
                if self.strict_profile and not any(e.get('id')==choice['cache_id'] and
                    e.get('tokens')==choice['prefix_tokens'] for e in result['prefix_cache']['entries']):
                    raise RuntimeError('warm cache namespace differs')
                return result
            if result.get('type')=='error':
                self.inflight = False
                raise RuntimeError('Prefix preparation failed: '+str(result))

    def send(self, request):
        if self.strict_profile and self.warm_result is None:raise RuntimeError('prefix warm has not completed')
        if self.strict_profile and self.profile.get('additional_neutral_prefixes') and any(p['cache_id'] not in self.warm_results for p in prefix_choices(self.profile)):
            raise RuntimeError('all selected neutral prefixes must be warm before questions')
        if self.strict_profile and getattr(self.worker,'real',False):
            from continuous_sessions import question_reserve
            reserve=question_reserve(self.profile['context_tokens'],self.profile['prefix_tokens'],self.profile['output_tokens'],
                draft_strategy=self.profile.get('realtime_draft_strategy'))
            if self.worker.max_runs-self.worker.runs<reserve:raise RuntimeError('insufficient complete-question budget')
        if self.maximum_questions is not None and self.questions_sent>=self.maximum_questions:
            raise RuntimeError('This window has consumed its model question allowance')
        self.pending_prefix=select_prefix(self.profile,request)
        request = dict(request, cache_policy='TT10_REQUIRE_HIT', cache_id=self.pending_prefix['cache_id'],
                       cache_binding_sha256=self.binding, prefill_chunk=self.profile.get('prefill_chunk',256),
                       profile=self.profile.get('profile_model_requests',False), diagnostic_report=False)
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
            assert cache['hit'] is True and cache['reused_tokens']==self.pending_prefix['prefix_tokens']
            if self.strict_profile:
                if result.get('prefix_cache',{}).get('binding_sha256')!=self.binding:
                    raise RuntimeError('active cache binding changed')
                entries=result.get('prefix_cache',{}).get('entries',[])
                if not any(e.get('id')==self.pending_prefix['cache_id'] and e.get('tokens')==self.pending_prefix['prefix_tokens'] for e in entries):
                    raise RuntimeError('active cache namespace changed')
                if ('prefill_chunk' in self.profile or self.profile.get('additional_neutral_prefixes')) and result.get('prefill_chunk')!=self.profile.get('prefill_chunk',256):
                    raise RuntimeError('live prefill chunk changed')
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
    profile=load_profile(overlay/config['profile']) if config.get('profile') else dict(LEGACY)
    profile['profile_model_requests']=config.get('profile_model_requests',False)
    from answer_cache_profile import prepared_answer_cache
    answer_cache=prepared_answer_cache(overlay,config)
    continuous=config.get('continuous',False)
    maximum_questions=None if continuous else config.get('maximum_questions',1)
    assert continuous is True or maximum_questions in (1,2)
    transport = CachedTransport(worker,owner,path,api,maximum_questions=maximum_questions,
                                profile=profile if config.get('profile') else None)
    ready = api.receive(worker,owner,path,timeout=180)
    api.save(path/'ready.json',ready)
    api.validate_bo(ready['bridge']['a12_route'])
    owner.full_resident=True
    api.save(path/'graphical-allocation.json',dict(status='ACTUAL_FULL_BO_ALLOCATION_VERIFIED',
             charged_bytes=140591104,bo_count=148,weight_count=72,low_2GiB=True))
    requests=json.loads((api.BUNDLE/'control/requests.json').read_text())
    warm=next(r for r in requests if r['id']=='warm_prefix')
    for request in warm_requests(profile,warm):transport.warm(ready,request)
    api.save(path/'warm-result.json',transport.warm_result)
    api.save(path/'warm-results.json',transport.warm_results)
    native=load_native(overlay,'/opt/patient-qwen')(transport,ready,max_output_tokens=profile['output_tokens'],
                template_path=api.BUNDLE/'control/chat_template.jinja',generation_strategy=profile.get('realtime_draft_strategy'))
    from continuous_sessions import question_reserve
    budget_available=lambda: not continuous or worker.max_runs-worker.runs>=question_reserve(
                profile['context_tokens'],profile['prefix_tokens'],profile['output_tokens'],draft_strategy=profile.get('realtime_draft_strategy'))
    accepting=threading.Event();accepting.set()
    alive=lambda: (accepting.is_set() and budget_available() and not owner.finished and not worker.closed and not worker.quarantined
                   and not worker.delivery_cancelled and worker.process.poll() is None)
    APP=create_app(native,is_ready=alive,remaining_seconds=lambda:(owner.expires-time.monotonic_ns())/1e9,
                   prompt_builder=builder(profile),answer_cache=None if config.get('verify_first') else answer_cache)
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
        api.save(path/'WEB_START_FAILED.json',dict(status='WEB_START_FAILED_NO_QUESTION_ACCEPTED',
            reason='HTTP server did not start',normal_worker_drain_requested=True))
        # No question has been accepted. Return through the original platform
        # restore/finalization path after the ordinary worker shutdown completes.
        assert worker.close(timeout=30) and worker.closed and worker.process.returncode==0
        return transport.warm_result
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
    browser_profile=config.get('browser_profile','/home/ubuntu/snap/firefox/common/manual-pl-20261026-v2')
    subprocess.run(['runuser','-u','ubuntu','--','/usr/bin/python3','-c',
                    'import json;from pathlib import Path;p=Path('+repr(browser_profile)+');p.mkdir(exist_ok=True);'
                    'prefs={"layers.acceleration.disabled":True,"gfx.webrender.software":True,"webgl.disabled":True,"layout.frame_rate":60};'
                    '(p/"user.js").write_text("".join("user_pref("+json.dumps(k)+","+json.dumps(v)+");\\n" for k,v in prefs.items()))'],check=True)
    with (path/'browser.log').open('xb') as log:
        browser=subprocess.Popen(command+['gnome-session-inhibit','--inhibit','idle','--reason','Manual-PL-consultation',
            '/snap/bin/firefox','--no-remote','--profile',browser_profile,'--remote-debugging-port','9222','--kiosk','http://127.0.0.1:8000/'],
            stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
    api.save(path/'INTERACTIVE_READY.json',dict(status='READY_WAITING_FOR_USER_INPUT',url='http://127.0.0.1:8000/',
             backend='FPGA_REAL',prefix_warmed=True,prefix_tokens=profile['prefix_tokens'],
             profile_id=profile['profile_id'],cache_id=profile['cache_id'],model_questions=0,browser_pid=browser.pid,
             maximum_questions=maximum_questions,expires_monotonic_ns=owner.expires))
    if config.get('verify_first'):
        from verify_graphical import verify_first
        verify_first(worker,owner,path,api,transport)
        # The existing startup test proves a fresh PL answer. Only after that
        # test completes may public sessions reuse the prepared model catalog.
        if answer_cache is not None:
            with coordinator.lock:
                assert coordinator.work is None
                coordinator.engine.answer_cache=answer_cache
                coordinator.answer_cache=answer_cache
                for conversation in coordinator.conversations.values():
                    conversation.business.answer_cache=answer_cache
            api.save(path/'ANSWER_CACHE_ENABLED.json',dict(status='VERIFIED_MODEL_CACHE_ENABLED_AFTER_REAL_PL_PROBE',
                cache=answer_cache.report(),current_model_called_for_hits=False))
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
    if SERVER is not None and SERVER.started:
        # Hardware already finalized: stop its HTTP view with the requested service.
        SERVER.should_exit=True
        THREAD.join(timeout=15)
