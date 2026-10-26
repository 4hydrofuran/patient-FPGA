"""Expected ARM startup failures before any backend/device-open permission.

Negative child exit 2 is recorded as rejection, never passed through the normal
positive-worker close gate. Locks stay owned by manager throughout; no kill.
"""
import json,os,socket,subprocess,threading
from pathlib import Path
from common import sha,save,CONTRACT

def startup_negatives(bundle,owner,platform,run):
    folder=run/'startup-negative';folder.mkdir();rows=[]
    args=[str(bundle/'bin/qwen35-a12'),'/opt/patient-qwen/artifacts/qwen35-0.8b/qwen35-text-Q4_K_M.gguf','2','256','all','TILED','2','8']
    for name in ('missing_required_library','wrong_contract_version'):
        owner.owner_check();owner.health();case=folder/name;case.mkdir()
        cfg=dict(contract_sha256=CONTRACT if name=='missing_required_library' else '0'*64,
          fallback='disabled',fpga_required=True,scope='all',execution_kind='FPGA_REAL',
          library=str(bundle/'bin/MISSING_REQUIRED_A12_LIBRARY.so'),library_sha256='0'*64,
          backend_config='/opt/patient-qwen/modules/linear_A/cpu_config.json',backend_config_sha256=sha('/opt/patient-qwen/modules/linear_A/cpu_config.json'),trace_limit=4096)
        save(case/'route.json',cfg);manager,child=socket.socketpair();permits=[]
        with (case/'stdout.txt').open('x') as out,(case/'stderr.txt').open('x') as err:
            env=dict(os.environ,SP_A12_CONFIG=str(case/'route.json'),SP_A12_CONTROL_FD=str(child.fileno()))
            proc=subprocess.Popen(args,stdin=subprocess.DEVNULL,stdout=out,stderr=err,env=env,pass_fds=(*owner.locks,child.fileno()))
            child.close();save(case/'identity.json',dict(pid=proc.pid,argv=args,binary_sha256=sha(bundle/'bin/qwen35-a12'),expected_exit_code=2,no_device_open_permission=True))
            def serve():
                with manager.makefile('r') as stream:
                    for line in stream:
                        q=json.loads(line);allow=(name=='missing_required_library' and not permits and q==dict(sequence=1,phase='router_open',job=0,pid=proc.pid))
                        owner.owner_check();owner.health();permits.append(dict(request=q,allow=allow))
                        manager.sendall((json.dumps(dict(sequence=q['sequence'],allow=allow))+'\n').encode())
            thread=threading.Thread(target=serve,daemon=True);thread.start()
            rc=proc.wait(timeout=180) # timeout keeps inherited locks and manager isolation; never kill.
            thread.join(timeout=3);assert not thread.is_alive();manager.close()
        stderr=(case/'stderr.txt').read_text();stdout=(case/'stdout.txt').read_text()
        assert rc==2 and 'S1_FAILURE:' in stderr and '"type":"ready"' not in stdout
        expected='A12 missing pinned artifact' if name=='missing_required_library' else 'A12 identity/fallback policy'
        assert expected in stderr and len(permits)==(1 if name=='missing_required_library' else 0)
        assert all(q['request']['phase']=='router_open' for q in permits)
        platform.no_users(module_loaded=False);owner.owner_check()
        row=dict(case=name,status='PASS_ARM_FAIL_CLOSED_BEFORE_DEVICE_OPEN',exit_code=rc,permits=permits,hardware_submissions=0,fallback='disabled',forced_exit=False)
        save(case/'rejection.json',row);rows.append(row)
    save(folder/'SUMMARY.json',dict(status='PASS_ARM_MISSING_ARTIFACT_AND_WRONG_CONTRACT_NO_FALLBACK',rows=rows,physical_unplug='NOT_TESTED'))
