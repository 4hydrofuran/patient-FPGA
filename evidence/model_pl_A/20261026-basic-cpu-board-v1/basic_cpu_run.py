"""One explicit CPU-only synthetic question on the physical ARM board."""
import hashlib,json,os,select,signal,subprocess,sys,time
from pathlib import Path

DATA = None
ROOT=Path('/home/ubuntu/a12-resident-basic-20261026-v1')
STAGE=ROOT/'a12-resident-20261026-v1'
RUN=ROOT/'run-v1'

def main():
    os.umask(0o077);RUN.mkdir(mode=0o700)
    result=dict(status='STARTED_CPU_ONLY',physical_host='BOARD_ARM64',kernel=os.uname().release,
                hardware_acceleration=False,PL_calls=0,private_PLM_chain_tested=False)
    p=None;raw=None;errors=None;started=time.monotonic_ns()
    try:
        assert os.geteuid()==0 and os.uname().machine=='aarch64'
        assert hashlib.sha256(Path('/etc/machine-id').read_bytes()).hexdigest()=='ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec'
        assert hashlib.sha256((STAGE/'bin/qwen35-a12').read_bytes()).hexdigest()=='5435c3fe8c83d3e292d992f6c48a572c8929eac2cce2f46a08b3ce9e7db13196'
        model=Path('/opt/patient-qwen/artifacts/qwen35-0.8b/qwen35-text-Q4_K_M.gguf')
        assert model.is_file()
        sys.path.insert(0,str(STAGE/'resident-app'))
        from app.session import Session
        env={k:v for k,v in os.environ.items() if not k.startswith(('SP_A12','SP_TT10','GGML_','LD_','OMP_','OPENBLAS_'))}
        env.update(LD_LIBRARY_PATH=str(STAGE/'bin'),OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='1')
        raw=(RUN/'native.stdout').open('xb');errors=(RUN/'native.stderr').open('xb')
        argv=[str(STAGE/'bin/qwen35-a12'),str(model),'2','1024','all','TILED','2','8']
        p=subprocess.Popen(argv,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=errors,env=env)
        result['native_pid']=p.pid;result['argv']=argv
        print(json.dumps(dict(event='CPU_WORKER_STARTED',pid=p.pid)),flush=True)
        buffer=bytearray();execution_deadline=time.monotonic()+300
        def receive(timeout=180):
            deadline=min(time.monotonic()+timeout,execution_deadline)
            while b'\n' not in buffer:
                wait=deadline-time.monotonic()
                if wait<=0 or not select.select([p.stdout],[],[],max(0,wait))[0]:raise TimeoutError('CPU native response deadline')
                part=os.read(p.stdout.fileno(),32768)
                if not part:raise RuntimeError('CPU native stdout closed')
                raw.write(part);raw.flush();buffer.extend(part)
                if len(buffer)>131072:raise RuntimeError('CPU native response line bound')
            line,_,tail=buffer.partition(b'\n');buffer[:]=tail
            return json.loads(line)
        ready=receive()
        result['ready']=ready
        assert ready['type']=='ready' and ready['execution_kind']=='CPU_REFERENCE'
        result['startup_s']=(time.monotonic_ns()-started)/1e9
        print(json.dumps(dict(event='CPU_MODEL_READY',startup_s=result['startup_s'])),flush=True)
        class Backend:
            def generate(self,messages,timeout_s):
                assert messages==DATA['messages']
                request=DATA['native_request'];p.stdin.write((json.dumps(request,ensure_ascii=False)+'\n').encode());p.stdin.flush()
                while True:
                    q=receive(timeout_s)
                    if q['type']=='token':continue
                    result['native_result']=q
                    assert q['type']=='result' and q['status']=='OK' and q['eos'] is True
                    assert q['state_cleared_before_response'] is True and q['state_position_after_clear']==-1
                    assert q['bridge']['a12_route']['enabled'] is False
                    return dict(status=q['status'],text=q['text'],eos=q['eos'],actual_backend='BOARD_CPU_REFERENCE')
        session=Session('SYN_CP_01',software_test=True)
        received=time.monotonic_ns()
        answer=session.submit(dict(request_id='basic-cpu-01',text=DATA['question'],source='typed',final=True),Backend(),timeout_s=180)
        result['input_to_checked_answer_s']=(time.monotonic_ns()-received)/1e9;result['answer']=answer
        assert answer['type']=='validated_answer' and answer['answer_source']=='MODEL' and answer['final_check']['status']=='pass'
        session.trusted_delivery(answer['request_id'],answer['epoch'],kind='PC_TEXT_TEST_ACK')
        p.stdin.write(b'{"op":"shutdown"}\n');p.stdin.flush();p.stdin.close();p.wait(timeout=30)
        assert p.returncode==0
        result.update(status='PASS_BOARD_ARM_CPU_BASIC_MODEL_RUN_NOT_PL_ACCEPTANCE',exit_code=0,
                      question=DATA['question'],text=answer['text'],eos=True,content_check='pass',normal_shutdown=True)
    except BaseException as exc:
        result.update(status='FAILED_BOARD_CPU_BASIC_RUN',error=type(exc).__name__+': '+str(exc))
        if p is not None:
            if p.poll() is None:
                # CPU only: cooperative native abort, never FPGA/reset/unload.
                p.send_signal(signal.SIGUSR1)
                try:
                    if p.stdin and not p.stdin.closed:p.stdin.close()
                    p.wait(timeout=30)
                except (subprocess.TimeoutExpired,OSError):pass
            result['exit_code']=p.poll();result['process_still_live']=p.poll() is None
    finally:
        if raw:raw.close()
        if errors:errors.close()
        result['elapsed_s']=(time.monotonic_ns()-started)/1e9
        if errors and (RUN/'native.stderr').exists():result['stderr_tail']=(RUN/'native.stderr').read_text(errors='replace')[-1600:]
        (RUN/'RESULT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
        small={k:v for k,v in result.items() if k not in ('ready','native_result','answer')}
        print('__A12_UPLOAD_BEGIN__',flush=True);print(json.dumps(small,ensure_ascii=False),flush=True);print('__A12_UPLOAD_END__',flush=True)
    return 0 if result['status'].startswith('PASS_') else 1

if __name__=='__main__':raise SystemExit(main())
