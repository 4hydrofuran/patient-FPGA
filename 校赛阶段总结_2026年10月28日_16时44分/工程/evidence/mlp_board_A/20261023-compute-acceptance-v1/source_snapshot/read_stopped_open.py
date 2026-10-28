"""Exact parked A11 open failure: read-only process/driver evidence, no signals."""
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import zlib


def pack(b):
    assert len(b)<8*1024*1024
    return dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest(),zlib_base64=base64.b64encode(zlib.compress(b)).decode())


def main():
    root=Path('/var/lib/kv260-a11/a11-mlp-20261023-v1')
    assert os.geteuid()==0 and os.uname().release=='6.8.12-a10irq2'
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    assert boot=='8422f92f-d01f-4849-ad19-6e66b640a9ad'
    assert hashlib.sha256((root/'manifest.json').read_bytes()).hexdigest()=='3b3c46700f92565839abda962e07e557018b8fd1be9e7846613ff46ecf89f11c'
    rows=[json.loads(l) for l in (root/'lifecycle.jsonl').read_text().splitlines()]
    start=[r for r in rows if r['event']=='A11_WORKER_STARTED'];assert len(start)==1
    pid=start[0]['worker_pid'];parent=start[0]['manager_pid']
    assert pid==3308 and parent==3202
    p=Path('/proc')/str(pid)
    info=dict(stat=(p/'stat').read_text(),status=(p/'status').read_text(),maps=(p/'maps').read_text(),
        cmdline=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(),
        fds={f.name:dict(target=os.readlink(f),fdinfo=(p/'fdinfo'/f.name).read_text()) for f in (p/'fd').iterdir()},
        threads={q.name:dict(stat=(q/'stat').read_text(),wchan=(q/'wchan').read_text()) for q in (p/'task').iterdir()})
    assert str(root/'mlp_worker.py') in info['cmdline']
    assert info['stat'].split(') ',1)[1].split()[1]==str(parent)
    raw=subprocess.run(['dmesg','--raw'],capture_output=True,timeout=3);assert raw.returncode==0 and not raw.stderr
    sys.path.insert(0,str(root))
    from accelerator_release_gate_v2 import collect
    result=dict(status='STOPPED_OPEN_READONLY',boot_id=boot,monotonic_ns=time.monotonic_ns(),worker_pid=pid,
        worker=info,module_refcount=Path('/sys/module/zocl/refcnt').read_text().strip(),scan=collect(allow_ps_display=True),
        permits={p.name:json.loads(p.read_text()) for p in (root/'permits').glob('*.json')},
        temperatures_mC=[int(p.read_text()) for p in Path('/sys/class/hwmon').glob('hwmon*/temp*_input')],
        files={},active_lease=None,kernel_log=pack(raw.stdout),hardware_mutations=0,signals_sent=0)
    print(json.dumps(result))


if __name__=='__main__':
    import sys
    main()
