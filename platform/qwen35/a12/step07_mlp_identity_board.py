"""Wrong contract on the real ARM executable: reject before router/device admission."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

ROOT=Path('/var/lib/kv260-a12/step07-mlp-20261024-v1')

def main():
    assert os.geteuid()==0 and os.uname().release=='6.8.12-a10irq2'
    assert hashlib.sha256((ROOT/'manifest.json').read_bytes()).hexdigest()=='da9477f70919dcdd85829782c8117fdc1c02de0ae800106d4ab51fb327cff053'
    assert not Path('/sys/module/zocl').exists() and not Path('/var/lock/kv260-a1/active').exists()
    out=ROOT/'identity-rejection-v1';out.mkdir(mode=0o700)
    config=out/'wrong-contract.json'
    with config.open('x') as f:json.dump(dict(contract_sha256='0'*64,fallback='disabled',fpga_required=True),f)
    env={k:v for k,v in os.environ.items() if not k.startswith(('SP_A12','LD_','GGML_','OMP_'))}
    env.update(LD_LIBRARY_PATH=str(ROOT/'bin'),OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='1',SP_A12_CONFIG=str(config))
    with (out/'stdout.txt').open('x') as stdout,(out/'stderr.txt').open('x') as stderr:
        argv=[str(ROOT/'bin/qwen35-a12'),'/opt/patient-qwen/artifacts/qwen35-0.8b/qwen35-text-Q4_K_M.gguf','2','1024','all','TILED','2','8']
        p=subprocess.Popen(argv,env=env,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr)
        try:rc=p.wait(timeout=45)
        except subprocess.TimeoutExpired:
            print(json.dumps(dict(status='STOP_IDENTITY_CHILD_PENDING_NO_SIGNAL',pid=p.pid)),flush=True)
            raise
    text=(out/'stderr.txt').read_text()
    assert rc==2 and 'A12 identity/fallback policy' in text
    assert not Path('/sys/module/zocl').exists() and not Path('/var/lock/kv260-a1/active').exists()
    result=dict(status='PASS_BOARD_WRONG_CONTRACT_REJECTED_BEFORE_PERMISSION_OR_DEVICE',exit_code=rc,
       pid=p.pid,argv=argv,boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
       raw_stdout=(out/'stdout.txt').read_text(),raw_stderr=text,
       binary_sha256=hashlib.sha256((ROOT/'bin/qwen35-a12').read_bytes()).hexdigest(),
       source_order='contract guard precedes router_open permit and dlopen; no permission channel provided',
       accelerator_submissions=0,signals_sent=0,monotonic_ns=time.monotonic_ns())
    with (out/'result.json').open('x') as f:json.dump(result,f)
    print(json.dumps(result),flush=True)

if __name__=='__main__':main()
