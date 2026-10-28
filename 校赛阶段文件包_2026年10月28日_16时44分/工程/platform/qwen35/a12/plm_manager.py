"""Real-backend PC XRT control window. No ARM execution, model or Board authorization."""
import copy
import json
import os
from pathlib import Path
import queue
import select
import socket
import subprocess
import threading
import time
from health_fence import HealthFence
from plm_evidence import ROOT,read,save,sha
from plm_page import Page,COUNT,REVOKED,UNKNOWN
from plm_journal import Journal,need
from request_journal_verified import FrozenProbe,canonical,digest
from request_journal_audit import strict_json
from fresh_identity_io import FreshCheckedFile

def ticks(pid):
    raw=Path('/proc',str(pid),'stat').read_text();return int(raw[raw.rfind(')')+2:].split()[19])
class Manager:
    def __init__(self,build,directory,*,cap=72,fault=None):
        self.directory=Path(directory)
        self.page=None;self.journal=None;self.p=None;self.pidfd=None;self.monitor=None;self.threads=[]
        self.fault=None;self.completed=[];self.control_results=[];self.legacy_sequences={};self.private_sequence=0
        need(os.name=='posix' and cap in (1,72),'PC Linux control cap required')
        self.build=read(build);need(self.build['domain']=='PC_XRT_CONTROL_ONLY_A53_UNBOUND','foreign build')
        for row in self.build['artifacts']:
            need(sha(row['path'])==row['sha256'],'changed PLM artifact')
        pins={Path(row['path']).resolve():row['sha256'] for row in self.build['artifacts']}
        self.artifact_readers={Path(self.build[k]).resolve():FreshCheckedFile(Path(self.build[k]).resolve(),pins[Path(self.build[k]).resolve()])
            for k in ('probe','backend_library','router_library')}
        self.directory=Path(directory);self.directory.mkdir(mode=0o700);self.cap=cap;self.injection=fault
        self.lock=threading.RLock();self.fault=None;self.closing=False;self.normal_terminal_requested=False
        self.p=None;self.pidfd=None;self.control_results=[];self.completed=[];self.active=None
        self.router=False;self.device=False;self.router_closed=False;self.loads=0;self.reserved=0;self.claims=0;self.bound=False
        self.legacy_sequences={'router':0,'backend':0};self.private_sequence=0;self.context_sha=None;self.messages=queue.Queue(maxsize=8)
        self.frozen=FrozenProbe();self.requests=copy.deepcopy(self.frozen.requests)
        self.page=Page(self.build['writer_library'],self.build['writer_sha256'])
        self.journal=Journal(self.directory/'state',self.page.epoch,self._fail,fault)
        self.legacy,self.child_legacy=socket.socketpair();self.private,self.child_private=socket.socketpair(socket.AF_UNIX,socket.SOCK_SEQPACKET)
        self.profile=self._fixtures()
        self.stderr=(self.directory/'worker.stderr').open('xb')
        env={k:v for k,v in os.environ.items() if not k.startswith(('LD_','SP_A12','SP_TT10','GGML_','OMP_'))}
        env.update(SP_A12_CONTROL_FD=str(self.child_legacy.fileno()),SP_A12_PLM_FD=str(self.child_private.fileno()),SP_A12_PLM_PAGE_FD=str(self.page.fd))
        env.update(ASAN_OPTIONS='detect_leaks=0:halt_on_error=1',UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
        argv=[self.build['probe'],str(self.directory/'config.json'),self.build['router_library'],fault or 'none']
        self.p=subprocess.Popen(argv,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.stderr,env=env,
            pass_fds=(self.child_legacy.fileno(),self.child_private.fileno(),self.page.fd,self.journal.lock),cwd=self.directory,text=True)
        self.child_legacy.close();self.child_private.close();self.pidfd=os.pidfd_open(self.p.pid);self.worker_ticks=ticks(self.p.pid)
        self.poller=select.poll();self.poller.register(self.pidfd,select.POLLIN)
        self.journal.append('WINDOW_OPEN',worker_pid=self.p.pid,worker_start_ticks=self.worker_ticks,cap=cap,domain='PC_XRT_CONTROL_ONLY_NOT_MODEL',real_device_approval=False)
        self.monitor=HealthFence(self._observe,on_fault=self._fail,interval_s=.05)
        self.threads=[threading.Thread(target=self._service,name='PLM-dual-channel-service',daemon=True),
            threading.Thread(target=self._stdout,name='PLM-stdout',daemon=True)]
        for t in self.threads:t.start()
    def _fixtures(self):
        payload=b'PC PLM CONTROL ONLY, NOT A BITSTREAM\n';(self.directory/'not-a-bitstream').write_bytes(payload);bit=sha(self.directory/'not-a-bitstream')
        source=dict(provider='B',accepted=True,frozen=True,production_or_A07_link_allowed=True,selected_build_id='0xB3030002',xo_sha256='CONTROL_ONLY')
        profile=dict(status='CONTROL_TEST_ONLY_NOT_BOARD',source_xo_sha256='CONTROL_ONLY',xclbin_sha256=bit,xclbin_uuid='CONTROL_ONLY_UUID',
            trial_bo_limit_bytes=10000000,bo_charge_alignment=8192,a12_max_runs=5000,a12_max_loads=72,kernel_build_id=0xB3030002,
            device_index=0,device_name='CONTROL_ONLY_DEVICE',argument_groups=[5,3,7,7,9,11],argument_address_windows=[dict(base=0,span=10000000) for _ in range(6)])
        cfg=dict(api_version=1,contract_sha256='83bd402b39350710d8689d50f79296e9625e9c75ccb0ecee145f08067c4ee3b6',backend_id='A_XRT_B_KERNEL_V1',fallback='disabled',
            kernel_source='source.json',deployment_profile='profile.json',allow_device_access=True,xclbin_path='not-a-bitstream',xclbin_sha256=bit)
        for name,v in [('source.json',source),('profile.json',profile),('config.json',cfg)]:save(self.directory/name,v)
        return profile
    def _owned(self):
        need(self.p is not None and self.pidfd is not None and not self.poller.poll(0),'owned live worker pidfd required')
        need(time.monotonic_ns()<self.page.deadline,'PC control window expired')
    def _observe(self):
        started=time.monotonic_ns();self._owned();boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        memory={row.split(':')[0]:int(row.split()[1]) for row in Path('/proc/meminfo').read_text().splitlines() if row.startswith('MemAvailable:')}
        need(memory['MemAvailable']>=1114112,'original PC MemAvailable floor refused')
        if self.journal is not None:self.journal.owner_check() # no changing append extent/inventory check on the observer
        self.page.health(started)
        return dict(domain='PC_XRT_CONTROL_ONLY',worker_pid=self.p.pid,worker_start_ticks=self.worker_ticks,boot_id=boot,started_ns=started,
            PC_MemAvailable_kib=memory['MemAvailable'],board_CMA=None,board_health_measured=False)
    def _guard(self):return self.fault is None and time.monotonic_ns()<self.page.deadline and not self.page.state()&REVOKED
    def _fail(self,reason):
        # Revoke BEFORE locks, persistence or any attempted diagnostics.
        if self.page is not None:self.page.revoke()
        if self.fault is None:self.fault=str(reason)[:400]
        for name in ('legacy','private'):
            sock=getattr(self,name,None)
            if sock:
                try:sock.shutdown(socket.SHUT_RDWR)
                except OSError:pass
        p=self.p
        if p is not None and p.stdin:
            try:p.stdin.close()
            except (OSError,ValueError):pass
    def _valid(self,q,sequence):
        self._owned();need(type(q.get('sequence')) is int and q['sequence']==sequence+1 and
            type(q.get('pid')) is int and q['pid']==self.p.pid,'foreign/replayed control request')
        need(self.fault is None,'PLM window fault latched')
    def _legacy_message(self,q):
        lane='router' if q.get('phase','').startswith('router_') else 'backend'
        with self.lock:
            self._valid(q,self.legacy_sequences[lane]);need(type(q.get('job')) is int and 0<=q['job']<=5000,'legacy job type/range')
            phase=q['phase'];ticket=self.monitor.fence()
            if phase=='router_open':need(not self.router and q['job']==0,'duplicate router open');self.router=True
            elif phase=='device_open':need(self.router and not self.device and q['job']==0,'device open order');self.device=True
            elif phase=='weight_load':
                need(self.bound and not self.active and not self.completed and self.loads<72 and q['job']==self.loads+1,'weight load order');self.loads+=1
            elif phase=='router_close':
                need(self.device and self.bound and not self.active and len(self.completed)==3 and not self.router_closed and q['job']==0,'premature/duplicate close');self.router_closed=True
            else:raise RuntimeError('legacy submit/unknown lane refused')
            self.journal.append('LEGACY_PERMISSION',lane=lane,phase=phase,sequence=q['sequence'],job=q['job'])
            self.legacy_sequences[lane]=q['sequence'];self.monitor.authorize(ticket,guard=self._guard)
            self.legacy.sendall(canonical(dict(sequence=q['sequence'],allow=True))+b'\n')
    def _private_message(self,q):
        with self.lock:
            self._valid(q,self.private_sequence);need(q['schema']=='PC_PLM_BACKEND_WIRE_V1' and q['worker_start_ticks']==self.worker_ticks,'private worker incarnation differs')
            ticket=self.monitor.fence();reply=dict(schema=q['schema'],sequence=q['sequence'],allow=True)
            if q['phase']=='bind':
                need(self.router and self.device and not self.bound and self.loads==0 and not self.active,'bootstrap order')
                facts=q['facts'];ctx=digest(facts)
                need(q['context_sha256']==ctx and facts['schema']=='A12_PL_CONTEXT_UNBOUND_V1' and facts['production_enabled'] is False and
                    facts['board_generation_approval']=='UNBOUND' and facts['worker_pid']==self.p.pid and facts['worker_start_ticks']==self.worker_ticks and
                    facts['kernel_build_id']==self.profile['kernel_build_id'] and facts['xclbin_sha256']==self.profile['xclbin_sha256'] and
                    facts['xclbin_uuid']==self.profile['xclbin_uuid'] and facts['device_name']==self.profile['device_name'] and facts['device_index']==0 and
                    facts['groups']==self.profile['argument_groups'] and facts['windows']==[[0,10000000]]*6 and
                    facts['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text() and len(facts['context_generation'])>=3,
                    'actual opened-context facts differ from PC recipe')
                need(len(facts['io_addresses'])==4 and len(set(facts['io_addresses']))==4 and
                    facts['io_sizes']==[40960,8192,155648,8192] and all(0<=a<10000000-s for a,s in zip(facts['io_addresses'],facts['io_sizes'])),'IO ownership facts differ')
                self.journal.append('CONTEXT_BIND',facts=facts,context_sha256=ctx,independent_board_approval=False)
                self.page.bind(self.p.pid,self.worker_ticks,ctx);self.context_sha=ctx;self.bound=True;self.facts=facts;reply['context_sha256']=ctx
            elif q['phase']=='batch':
                need(all(type(q.get(k)) is int for k in ('job','T','generation')),'private job/T/generation type')
                a=self.active;s=self.page.snapshot();need(self.bound and a and q['context_sha256']==self.context_sha and
                    q['request_sha256']==a['digest'] and q['generation']==s['generation'] and q['job']==self.reserved+1==s['claims']+1 and
                    s['grant_limit']==s['claims'] and s['active'] and not s['unknown_io'] and not s['revoked'],'batch identity/state/range differs')
                index=(self.reserved-a['base'])//72;need(index<len(a['full_plan']) and q['T']==a['full_plan'][index],'batch graph T differs')
                count=min(self.cap,72-(self.reserved-a['base'])%72);first=self.reserved+1;last=self.reserved+count
                need(last<=a['base']+a['budget']<=5000,'request/window grant budget exceeded');self.reserved=last
                reply.update(context_sha256=self.context_sha,first_job=first,last_job=last,generation=s['generation'],request_sha256=a['digest'],deadline_monotonic_ns=self.page.deadline)
                self.journal.append('GRANT',request_id=a['id'],sequence=q['sequence'],generation=s['generation'],first=first,last=last,T=q['T'],
                    context_sha256=self.context_sha,request_sha256=a['digest'],fresh_sample=ticket.sample)
                self.page.grant(first,last)
            else:raise RuntimeError('unknown private phase')
            self.private_sequence=q['sequence'];self.monitor.authorize(ticket,guard=self._guard)
            self.private.sendall(canonical(reply))
    def _service(self):
        sockets={self.legacy,self.private};pending=b''
        try:
            while sockets:
                ready,_,_=select.select(list(sockets),[],[],.1)
                for sock in ready:
                    if sock is self.legacy:
                        raw=sock.recv(4097)
                        if not raw:
                            need(self.normal_terminal_requested and not pending,'unexpected/truncated legacy EOF');sockets.remove(sock);continue
                        pending+=raw;need(len(pending)<=4096,'oversize legacy wire')
                        while b'\n' in pending:
                            line,pending=pending.split(b'\n',1);self._legacy_message(strict_json(line))
                    else:
                        raw,_,flags,_=sock.recvmsg(8192)
                        if not raw:
                            need(self.normal_terminal_requested,'unexpected private EOF');sockets.remove(sock);continue
                        need(not flags&socket.MSG_TRUNC,'oversize private packet');self._private_message(strict_json(raw))
        except BaseException as exc:self._fail('service: '+str(exc))
    def _stdout(self):
        try:
            while True:
                raw=self.p.stdout.readline(32769)
                if not raw:self.messages.put(None,timeout=1);return
                need(len(raw.encode())<=32768 and raw.endswith('\n'),'worker output bound');q=strict_json(raw.encode())
                need(q.get('domain')=='PC_XRT_CONTROL_ONLY_NOT_MODEL' and q.get('BOARD')=='NOT_TESTED','foreign output domain')
                self.messages.put(q,timeout=1)
        except BaseException as exc:self._fail('stdout: '+str(exc))
    def get(self,timeout=60):
        q=self.messages.get(timeout=timeout);need(q is not None,'native EOF before requested result');self.last_native=q;return q
    def ready(self):
        q=self.get();need(q['event']=='ready','worker failed during startup');r=q['report'];s=self.page.snapshot()
        need(self.loads==72 and self.bound and r['execution_kind'] is None and r['test_domain']=='CONTROL_TEST_DOUBLE_NOT_FPGA' and
            r['weight_load_count']==72 and r['host_verified_completions']==0 and q['inventory']['stub_live']==148 and
            r['a11_explicit_bo_allocations_host_counter']==148 and r['a11_io_bo_addresses']==self.facts['io_addresses'] and
            len(r['a11_live_weights'])==72 and not s['unknown_io'] and not s['revoked'],'startup inventory/identity differs')
        self.loaded_identity();self.page.load_end();self.journal.append('READY',native_sha256=digest(q),weights=72,stub_BO_count=148,real_BO_count=None)
        save(self.directory/'READY.json',q);return q
    def run_request(self,index,*,native_fault=None):
        with self.lock:
            need(self._guard() and self.active is None and index==len(self.completed)<3,'request order/fault')
            r=self.requests[index];n=len(r['tokens'])-(70 if r['id']=='app_hit' else 0)
            self.loaded_identity()
            pre=[min(8,n-i) for i in range(0,n,8)];full=pre+([1]*7 if r['op']!='cache_create' else [])
            actual=pre+([1]*6 if r['op']!='cache_create' else []) # explicit CONTROL fixture, never model/EOS evidence
            d=digest(r);self.journal.check_all();ticket=self.monitor.fence()
            self.journal.append('BEGIN',request=r,request_sha256=d,base=self.claims,budget=len(full)*72,control_actual_plan=actual,
                mode='CAP1_STRICT_CONTROL' if self.cap==1 else 'CAP72_CANDIDATE_CONTROL')
            self.page.begin(self.claims,len(full)*72,d);self.active=dict(id=r['id'],digest=d,base=self.claims,budget=len(full)*72,full_plan=full,actual_plan=actual)
            wire=dict(op='run',id=r['id'],request_sha256=d,plan=actual,fault=native_fault or '')
            if self.injection=='request_digest':wire['request_sha256']='0'*64
            self.monitor.authorize(ticket,guard=self._guard);self.p.stdin.write(canonical(wire).decode()+'\n');self.p.stdin.flush()
        q=self.get();need(q['event']=='result','native did not finish a control request')
        with self.lock:
            a=self.active;s=self.page.snapshot();result=q['report'];expected=len(a['actual_plan'])*72
            need(self._guard() and q['request_id']==a['id'] and q['request_sha256']==a['digest'] and q['calls']==expected and
                q['last_job']==a['base']+expected==s['claims']==self.reserved and s['active'] and not s['unknown_io'] and
                result['status']=='READY' and result['last_status_code']==0 and result['output_consumable'] is True and
                result['host_verified_completions']==q['last_job']==result['job_id'] and result['kernel_build_id']==0xB3030002 and
                result['plm_control']['bound_request_sha256']=='' and result['plm_control']['local_generation']==0 and
                q['inventory']['stub_live']==148 and q['inventory']['stub_starts']==s['claims'],'control completion/counter/cleanup differs')
            self.journal.check_all();ticket=self.monitor.fence();self.page.end(s['claims'])
            end=self.journal.append('END',request_id=a['id'],request_sha256=a['digest'],result_sha256=digest(q),actual_control_calls=expected,
                final_job=s['claims'],hardware_calls=None,control_result_only=True)
            self.journal.receipt(a['id'],dict(schema='PC_PLM_RECEIPT_V1',request_id=a['id'],END_sha256=end['sha256'],result_sha256=digest(q),answer_delivered=False))
            self.journal.check_all();stamp=self.monitor.authorize(ticket,guard=self._guard)
            self.claims=s['claims'];self.completed.append(a['id']);self.active=None;self.control_results.append(q)
            save(self.directory/(a['id']+'-CONTROL_RESULT.json'),dict(result=q,delivery_fence=stamp,clinical_answer_delivered=False))
            return q
    def normal_close(self):
        need(self._guard() and len(self.completed)==3 and not self.active,'close before verified requests')
        self.p.stdin.write('{"op":"close"}\n');self.p.stdin.flush();q=self.get();need(q['event']=='closed' and q['inventory']['stub_live']==0 and self.router_closed,'native close not confirmed')
        need(self.monitor.stop(),'health observer still live');self.normal_terminal_requested=True;self.page.revoke()
        self.p.stdin.write('{"op":"exit"}\n');self.p.stdin.flush();self.p.stdin.close();self.p.wait(timeout=5)
        need(self.p.returncode==0 and self.poller.poll(0),'owned worker not terminal')
        for t in self.threads:t.join(2)
        need(all(not t.is_alive() for t in self.threads) and self.fault is None,'control threads not cleanly stopped')
        s=self.page.snapshot();need(not s['unknown_io'] and not s['active'] and s['claims']==2880,'normal page not quiescent')
        self.journal.normal_close();self.page.close();os.close(self.pidfd);self.pidfd=None;self.stderr.close();self.legacy.close();self.private.close()
        identity_bytes=sum(v.bytes_read for v in self.artifact_readers.values())
        for reader in self.artifact_readers.values():reader.close()
        return dict(status='PASS_PC_XRT_MANAGER_WINDOW_NOT_MODEL',cap=self.cap,completed=self.completed,claims=self.claims,
            private_messages=self.private_sequence,legacy_sequences=self.legacy_sequences,page=s,control_results=len(self.control_results),
            journal_records=self.journal.serial,journal_bytes=self.journal.size,boundary_journal_read_bytes=self.journal.boundary_read_bytes,
            boundary_artifact_read_bytes=identity_bytes,
            worker_exit_code=self.p.returncode,all_threads_stopped=True,actual_FPGA_calls=None,BOARD='NOT_TESTED',release_allowed=False)
    def failed_observation(self,reason):
        self._fail(reason)
        if self.monitor is not None:self.monitor.stop()
        if self.p is not None:
            try:self.p.wait(timeout=5)
            except subprocess.TimeoutExpired:pass # observation timeout is not a terminal/release verdict
        for t in self.threads:t.join(1)
        s=self.page.snapshot() if self.page is not None else None
        return dict(status='FAILED_PC_CONTROL_WINDOW_RETAINED',reason=self.fault,page=s,completed=list(self.completed),control_results=len(self.control_results),
            worker_exit_code=self.p.poll() if self.p is not None else None,owned_pidfd_terminal=bool(self.poller.poll(0)) if self.pidfd is not None else False,
            dirty_marker_retained=(self.directory/'state/DIRTY.json').exists(),writer_FD_retained=self.page is not None and self.page.fd is not None,
            all_threads_stopped=all(not t.is_alive() for t in self.threads),
            legacy_sequences=self.legacy_sequences,private_messages=self.private_sequence,BOARD='NOT_TESTED',release_allowed=False,replay_allowed=False)
    def loaded_identity(self):
        self._owned();expected=self.artifact_readers
        mapped=set()
        with Path('/proc',str(self.p.pid),'maps').open() as f:
            used=0
            for line in f:
                used+=len(line);need(used<=2*1024*1024,'bounded worker maps exceeded')
                parts=line.rstrip().split(maxsplit=5)
                if len(parts)<6 or not parts[5].startswith('/'):continue
                name=parts[5];need(not (name.endswith(' (deleted)') and any(p.name in name for p in expected)),'candidate mapping deleted')
                p=Path(name).resolve()
                if p in expected:
                    reader=expected[p];st=os.fstat(reader.fd);dev=tuple(int(x,16) for x in parts[3].split(':'))
                    need(int(parts[4])==st.st_ino and dev==(os.major(st.st_dev),os.minor(st.st_dev)),'mapped artifact identity differs');mapped.add(p)
        need(mapped==set(expected),'actually mapped candidate libraries differ')
        # All bytes are freshly hashed at startup/request boundaries; no mtime verdict cache.
        for reader in expected.values():reader.check()
        return sorted(str(p) for p in mapped)
