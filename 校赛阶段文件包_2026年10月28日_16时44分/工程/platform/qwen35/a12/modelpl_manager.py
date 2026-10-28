"""Actual-model specialization of the frozen dual-lane manager, CPU proof only."""
import ast
import copy
import json
import os
from pathlib import Path
import queue
import select
import threading
import time
import types
from modelpl_evidence import ROOT,OUT,PARENT,read,save,sha,pin
from request_journal_verified import canonical,digest,FrozenProbe
from request_journal_audit import strict_json
from resource_probe_policy import ordinary_comparison
from plm_journal import need
from plm_manager import ticks

# Keep protocol, request-range validation, journal and failure mechanics pinned.
parent=ROOT/'platform/qwen35/a12/plm_manager.py';pins={r['path']:r['sha256'] for r in read(PARENT/'FINAL_REVIEW.json')['source']}
need(sha(parent)==pins['platform/qwen35/a12/plm_manager.py'],'frozen PL manager changed')
text=parent.read_text(encoding='utf-8');changes=[]
def replace(old,new):
    global text
    need(text.count(old)==1,'manager constructor derivation anchor differs');text=text.replace(old,new);changes.append((old,new))
replace("self.build['domain']=='PC_XRT_CONTROL_ONLY_A53_UNBOUND'","self.build['domain']=='PC_REAL_MODEL_PLM_V1'")
replace("for row in self.build['artifacts']:","for row in self.build['runtime_artifacts']:")
replace("pins={Path(row['path']).resolve():row['sha256'] for row in self.build['artifacts']}",
    "pins={Path(row['path']).resolve():row['sha256'] for row in self.build['runtime_artifacts']}")
replace("self.artifact_readers={Path(self.build[k]).resolve():FreshCheckedFile(Path(self.build[k]).resolve(),pins[Path(self.build[k]).resolve()])\n            for k in ('probe','backend_library','router_library')}",
    "self.artifact_readers={p:FreshCheckedFile(p,h) for p,h in pins.items()}")
replace("argv=[self.build['probe'],str(self.directory/'config.json'),self.build['router_library'],fault or 'none']","argv=self.native_argv()")
replace("env.update(ASAN_OPTIONS='detect_leaks=0:halt_on_error=1',UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')",
    "env.update(ASAN_OPTIONS='detect_leaks=0:halt_on_error=1',UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1');env.update(self.native_env())")
replace("domain='PC_XRT_CONTROL_ONLY_NOT_MODEL',real_device_approval=False","domain='PC_REAL_MODEL_CPU_REFERENCE',real_device_approval=False")
inverse=text
for old,new in reversed(changes):need(inverse.count(new)==1,'constructor inverse ambiguous');inverse=inverse.replace(new,old)
need(inverse==parent.read_text(encoding='utf-8'),'constructor inverse differs')
base=types.ModuleType('frozen_plm_model_base');base.__file__=str(parent);exec(compile(text,str(parent),'exec'),base.__dict__)

def cpu_route(route):
    need(route.get('pc_adapter')=='A12_REAL_MODEL_PLM_CPU_V1' and route.get('execution_kind')=='CPU_REFERENCE' and
        route.get('pc_domain')=='PC_NATIVE_MATH_NOT_FPGA' and route.get('a12_domain')=='PC_MATH_DOUBLE' and
        route.get('kernel_build_id') is None and route.get('hardware_done_count') is None and route.get('a12_hardware_global_count') is None,'CPU/hardware identity differs')
    need(route.get('status')=='READY' and route.get('cpu_quiescent') is True and route.get('pc_poisoned') is False and
        route.get('pc_closing') is False and route.get('pc_failed_calls')==0,'CPU route not healthy/quiescent')
    vals=[route[k] for k in ('pc_attempted_calls','pc_started_calls','pc_verified_completions','cpu_run_count')]
    need(all(type(v) is int and v>=0 for v in vals) and len(set(vals))==1,'actual CPU call/verification counters differ')
    return vals[0]

class ModelManager(base.Manager):
    def _owned(self):
        # CPython poll objects reject concurrent calls. Observe the SAME held pidfd
        # through a per-call poll object; never reopen/re-identify from a PID/file.
        need(self.p is not None and self.pidfd is not None,'owned worker handle absent')
        observer=select.poll();observer.register(self.pidfd,select.POLLIN)
        need(not observer.poll(0),'owned live worker pidfd required')
        need(time.monotonic_ns()<self.page.deadline,'PC model control window expired')
    def _observe(self):
        observed=super()._observe();observed['domain']='PC_REAL_MODEL_CPU_REFERENCE'
        if self.injection=='cached_revoke':
            state=self.page.state()
            if (state&0xffffffff)>=5 and state&((1<<61)|(1<<60)|(1<<59)):raise RuntimeError('PC cached fifth-claim revoke fixture')
        return observed
    def _fixtures(self):
        cpu_cfg=ROOT/'modules/linear_A/cpu_threads2_config.json';library=self.build['CPU_library'];self.adapter=self.build['adapter']
        adapter=dict(schema='A12_REAL_MODEL_PLM_CPU_V1',execution_kind='CPU_REFERENCE',contract_sha256='83bd402b39350710d8689d50f79296e9625e9c75ccb0ecee145f08067c4ee3b6',
            allow_device_access=False,cpu_library=library,cpu_library_sha256=self.build['CPU_library_sha256'],cpu_config=str(cpu_cfg),cpu_config_sha256=sha(cpu_cfg))
        save(self.directory/'adapter.json',adapter)
        route=dict(contract_sha256=adapter['contract_sha256'],fallback='disabled',fpga_required=True,scope='all',execution_kind='PC_MATH_DOUBLE',
            library=self.adapter,library_sha256=sha(self.adapter),backend_config=str(self.directory/'adapter.json'),backend_config_sha256=sha(self.directory/'adapter.json'),
            a12_private_protocol='A12_PLM_PRIVATE_V1',a12_compact_completion=True,trace_limit=4096)
        save(self.directory/'route.json',route)
        prefix=read(ROOT/'evidence/model_pl_A/20261025-resource-probe-v1/native-PC-02/prefix-config-PC.json')
        prefix['identity']['executable_sha256']=sha(self.build['native']);prefix['identity']['libraries']['liba12_native_cpu_control.so']=sha(self.adapter)
        prefix['identity']['pc_adapter_config_sha256']=sha(self.directory/'adapter.json');prefix['identity']['pc_route_config_sha256']=sha(self.directory/'route.json')
        save(self.directory/'prefix.json',prefix);return dict(adapter=adapter,route=route,prefix=prefix)
    def native_argv(self):
        return [self.build['native'],str(ROOT/'artifacts/qwen35-0.8b/qwen35-text-Q4_K_M.gguf'),'2','1024','all','TILED','2','8']
    def native_env(self):
        env=dict(SP_A12_CONFIG=str(self.directory/'route.json'),SP_TT10_CONFIG=str(self.directory/'prefix.json'),OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='1')
        if self.injection=='drop_copy':env['SP_A12_TEST_DROP_OUTPUT']='1'
        if self.injection=='cached_revoke':env['SP_A12_MODELPL_TEST_PAUSE_JOB']='5'
        return env
    def _private_message(self,q):
        if q.get('phase')!='bind':return super()._private_message(q)
        with self.lock:
            self._valid(q,self.private_sequence);need(q['schema']=='PC_PLM_BACKEND_WIRE_V1' and q['worker_start_ticks']==self.worker_ticks,'CPU context worker incarnation differs')
            need(self.router and self.device and not self.bound and self.loads==0 and not self.active,'CPU private bootstrap order')
            ticket=self.monitor.fence();facts=q['facts'];ctx=digest(facts);cfg=self.profile['adapter'];r=facts['actual_CPU_fresh_report']
            need(q['context_sha256']==ctx and facts['schema']=='A12_MODEL_PLM_CPU_CONTEXT_V1' and facts['execution_kind']=='CPU_REFERENCE' and
                facts['worker_pid']==self.p.pid and facts['worker_start_ticks']==self.worker_ticks and facts['context_generation'] and
                facts['cpu_library_sha256']==cfg['cpu_library_sha256'] and facts['cpu_config_sha256']==cfg['cpu_config_sha256'] and
                facts['contract_sha256']==cfg['contract_sha256'] and facts['real_device_generation_approval']=='UNBOUND_PC_CPU_ONLY' and
                facts['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text(),'actual CPU context/library/config differs')
            # The CPU provider has no BO/device/kernel facts, not fabricated FPGA values.
            need(r['execution_kind']=='CPU_REFERENCE' and r['kernel_build_id'] is None and r['hardware_done_count'] is None and
                r['cpu_run_count']==0 and r['weight_count']==0 and r['pc_verified_completions']==0 and r['pc_adapter']=='A12_REAL_MODEL_PLM_CPU_V1',
                'CPU context not fresh')
            self.journal.append('CONTEXT_BIND',facts=facts,context_sha256=ctx,independent_board_approval=False)
            self.page.bind(self.p.pid,self.worker_ticks,ctx);self.context_sha=ctx;self.bound=True;self.facts=facts
            self.private_sequence=q['sequence'];self.monitor.authorize(ticket,guard=self._guard)
            self.private.sendall(canonical(dict(schema=q['schema'],sequence=q['sequence'],allow=True,context_sha256=ctx)))
    def _stdout(self):
        try:
            used=0;packets=0
            with (self.directory/'native.stdout').open('xb') as capture:
                while True:
                    raw=self.p.stdout.readline(131073)
                    if not raw:self.messages.put(None,timeout=1);return
                    data=raw.encode();used+=len(data);packets+=1
                    need(raw.endswith('\n') and len(data)<=131072 and used<=1024*1024 and packets<=32,'bounded native stream exceeded')
                    capture.write(data);capture.flush();q=strict_json(data)
                    need(q.get('type') in ('ready','token','result','cache_created','error','private_closed'),'unexpected native message')
                    self.messages.put(q,timeout=1)
        except BaseException as exc:self._fail('real-model stdout: '+str(exc))
    def ready(self):
        q=self.get(timeout=120);need(q['type']=='ready' and q['domain']=='PC' and q['execution_kind']=='PC_MATH_DOUBLE' and q['physical_ubatch']==8,'actual native ready/domain differs')
        route=q['bridge']['a12_route'];count=cpu_route(route)
        need(q['bridge']['cpu_run_count']==q['bridge']['weight_count']==0 and route['pc_loads']==route['weight_count']==self.loads==72 and count==0,'unrouted fallback/startup counts differ')
        pc=route['a12_private_control'];need(pc['enabled'] is True and pc['request_active'] is False and pc['closed'] is False and pc['failed'] is False,'actual Route private hooks not ready')
        self.resident={k:route[k] for k in ('weight_load_count','weight_count','owned_weight_bytes','workspace_capacity_bytes','partial_sums_capacity_bytes','partial_sums_capture_enabled')}
        self.binding=q['prefix_cache']['binding_sha256'];need(q['prefix_cache']['enabled'] is True and type(self.binding) is str and len(self.binding)==64,'actual prefix not ready')
        need(q['prefix_cache']['identity']['verified_loaded_libraries']==self.profile['prefix']['identity']['libraries'],'actual native loaded libraries differ')
        self.loaded_identity();self.page.load_end();self.journal.append('READY',native_sha256=digest(q),weights=72,execution_kind='CPU_REFERENCE',hardware_completions=None)
        save(self.directory/'READY.json',q);self.ready_packet=q;self.reference=None;self.raw_first_tokens={};return q
    def wire(self,frozen):
        q={k:copy.deepcopy(v) for k,v in frozen.items() if 'application' not in frozen or k not in ('application','tokens')}
        if q['op']=='cache_create' or q['cache_policy']!='R0':q['cache_binding_sha256']=self.binding
        return q
    def run_request(self,index,*,native_fault=None):
        with self.lock:
            need(self._guard() and self.active is None and index==len(self.completed)<3,'actual model request order/fault')
            frozen=self.requests[index];wire=self.wire(frozen);d=digest(wire);n=len(frozen['tokens'])-(70 if frozen['id']=='app_hit' else 0)
            full=[min(8,n-i) for i in range(0,n,8)]+([1]*(frozen['max_tokens']-1) if frozen['op']!='cache_create' else [])
            self.loaded_identity();self.journal.check_all();ticket=self.monitor.fence()
            self.journal.append('BEGIN',request=wire,request_sha256=d,frozen_request_sha256=digest(frozen),base=self.claims,budget=len(full)*72,
                execution_kind='PC_NATIVE_MATH_NOT_FPGA',prefix_binding=self.binding)
            self.page.begin(self.claims,len(full)*72,d);self.active=dict(id=frozen['id'],digest=d,base=self.claims,budget=len(full)*72,full_plan=full)
            send=copy.deepcopy(wire)
            if self.injection=='request_digest':send['id']='tampered-native-id'
            self.monitor.authorize(ticket,guard=self._guard);started=time.monotonic_ns();self.p.stdin.write(canonical(send).decode()+'\n');self.p.stdin.flush()
        tokens=[];first=None
        while True:
            packet=self.get(timeout=120)
            if packet['type']!='token':break
            need(frozen['op']=='generate' and packet['id']==frozen['id'] and type(packet['index']) is int and packet['index']==len(tokens)<frozen['max_tokens'] and
                type(packet['token']) is int and 0<=packet['token']<248320,'actual native token stream differs')
            tokens.append(packet['token']);first=first or time.monotonic_ns()
        result=packet
        with self.lock:
            a=self.active;need(self._guard() and result['id']==a['id'] and result['status']=='OK' and result['type']==('cache_created' if frozen['op']=='cache_create' else 'result'),
                'actual native terminal status/identity differs')
            need(result['state_cleared_before_response'] is True and result['state_position_after_clear']==-1 and result['prefix_cache']['binding_sha256']==self.binding,'actual native cleanup/prefix binding differs')
            bridge=result['bridge'];route=bridge['a12_route'];total=cpu_route(route)
            need(bridge['cpu_run_count']==bridge['weight_count']==0 and bridge['error']=='','unselected CPU fallback observed')
            need({k:route[k] for k in self.resident}==self.resident,'actual CPU residency changed')
            if frozen['op']=='cache_create':
                need(not tokens and result['prefix_tokens']==70 and len(result['prefix_cache']['entries'])==1 and result['prefix_cache']['entries'][0]['tokens']==70,'actual warm snapshot differs')
                new=70;decode=0;content=None
            else:
                hit=frozen['id']=='app_hit';cache=result['prefix_cache_request'];new=37 if hit else 107;decode=result['decode_calls']
                need(cache['hit'] is hit and cache['new_tokens']==new and cache['reused_tokens']==(70 if hit else 0) and result['prompt_tokens']==107 and
                    type(decode) is int and 0<=decode<=7 and result['eos'] is True and result['teacher_forced'] is False and result['gpu_layers']==0 and result['domain']=='PC' and
                    result['output_tokens']==tokens and 0<len(tokens)<=8,'actual native R0/hit/tokens/EOS differs')
                content=self.frozen.check_answer(frozen,result);ordinary_comparison(result,result)
                if hit:ordinary_comparison(self.reference,result)
            expected=72*((new+7)//8+decode);s=self.page.snapshot();pc=route['a12_private_control']
            need(total==self.claims+expected==s['claims']==self.reserved and route['pc_last_job']==route['job_id']==total and route['pc_output_consumable'] is True and
                pc['schema']=='A12_MODEL_PLM_ROUTE_V1' and pc['enabled'] is True and pc['request_active'] is False and pc['failed'] is False and
                pc['request_sha256']==d and pc['copy_checks']==expected and pc['checked_copy_bytes']>0 and pc['closed'] is False and
                route['pc_plm']['bound_request_sha256']=='' and route['pc_plm']['local_generation']==0 and s['active'] and not s['unknown_io'] and not s['revoked'],
                'actual Route copy checks/private boundary/counters differ')
            self.journal.check_all();ticket=self.monitor.fence();self.page.end(total)
            end=self.journal.append('END',request_id=a['id'],request_sha256=d,result_sha256=digest(result),actual_CPU_calls=expected,final_job=total,
                graph_copy_checks=pc['copy_checks'],graph_checked_bytes=pc['checked_copy_bytes'],hardware_calls=None,content=content)
            self.journal.receipt(a['id'],dict(schema='PC_REAL_MODEL_PLM_RECEIPT_V1',request_id=a['id'],END_sha256=end['sha256'],result_sha256=digest(result),clinical_review=False))
            self.journal.check_all();stamp=self.monitor.authorize(ticket,guard=self._guard);delivered=time.monotonic_ns()
            self.claims=total;self.completed.append(a['id']);self.active=None;self.control_results.append(result)
            if frozen['id']=='app_R0':self.reference=copy.deepcopy(result)
            summary=dict(actual_CPU_calls=expected,cumulative_CPU_calls=total,graph_copy_checks=pc['copy_checks'],content=content,request_sha256=d,
                send_to_validated_result_s=(delivered-started)/1e9,raw_native_first_token_s=(first-started)/1e9 if first else None,
                scope='PC_ONLY_RAW_TOKEN_NOT_USER_DELIVERY; SMALL_DESCRIPTIVE_SAMPLE_NOT_BOARD',hardware_completions=None)
            save(self.directory/(a['id']+'-MODEL_RESULT.json'),dict(result=result,summary=summary,delivery_fence=stamp));return result
    def normal_close(self):
        need(self._guard() and self.active is None and len(self.completed)==3,'actual model close before complete requests')
        self.p.stdin.write('{"op":"shutdown"}\n');self.p.stdin.flush();q=self.get(timeout=30)
        need(q['type']=='private_closed' and q['status']=='NATIVE_CONTEXT_CLOSED_NOT_PLATFORM_RELEASE' and self.router_closed and
            q['private_control']['closed'] is True and q['private_control']['failed'] is False and q['private_control']['request_active'] is False,'actual Route close not confirmed')
        need(self.monitor.stop(),'native health observer still live');self.normal_terminal_requested=True;self.page.revoke()
        self.p.stdin.write('{"op":"private_exit_ack"}\n');self.p.stdin.flush();self.p.stdin.close();self.p.wait(timeout=20)
        need(self.p.returncode==0 and self.poller.poll(0),'actual model process not terminal')
        for t in self.threads:t.join(2)
        need(all(not t.is_alive() for t in self.threads) and self.fault is None,'actual model protocol threads not stopped')
        state=self.page.snapshot();need(state['claims']==2880 and state['revoked'] and not state['active'] and not state['unknown_io'],'actual model page not quiescent')
        self.journal.normal_close();self.page.close();os.close(self.pidfd);self.pidfd=None;self.stderr.close();self.legacy.close();self.private.close()
        for reader in self.artifact_readers.values():reader.close()
        return dict(status='PASS_ACTUAL_QWEN_PLM_CPU_WINDOW_NOT_BOARD',cap=self.cap,completed=self.completed,claims=self.claims,model_requests=3,validated_answers=2,
            private_messages=self.private_sequence,legacy_sequences=self.legacy_sequences,page=state,journal_records=self.journal.serial,journal_bytes=self.journal.size,
            all_threads_stopped=True,worker_exit_code=0,private_close_packet=q,actual_FPGA_calls=None,BOARD='NOT_TESTED',production_enabled=False,release_allowed=False)
