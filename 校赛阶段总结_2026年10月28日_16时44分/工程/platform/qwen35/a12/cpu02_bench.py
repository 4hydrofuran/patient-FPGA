"""Bounded Linux PC component timings, never a BOARD performance substitute."""
import argparse
import errno
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import statistics
import sys
import tempfile
import threading
import time
import types

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'evidence/model_pl_A/20261024-cpu-opt-02-v1'
BASE=ROOT/'evidence/model_pl_A/20261024-cpu-opt-01-integrated-v1/integrated/bundle-v1'


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('variant',choices=['baseline','candidate']);p.add_argument('--tag',default='');args=p.parse_args()
    source=BASE/'platform/qwen35/a12' if args.variant=='baseline' else OUT/'source'
    sys.path.insert(0,str(source));sys.path.insert(1,str(BASE/'control/support'))
    from cpu01b_health import PersistentKmsg
    from cpu01b_kernel_gate import MinimalGate
    from cpu01b_healthrecord import compact_kernel_record
    from cpu01b_supervisor_base import OwnedWorker
    from isolated_idle_policy import lock_owned
    paths=list((ROOT/'evidence/model_pl_A/20261024-cpu-opt-01-integrated-v1/integrated/readback-v1/run-v1/kernel').glob('*.raw'))
    raw=max(paths,key=lambda p:p.stat().st_size).read_text(encoding='utf-8');pin=hashlib.sha256(raw.encode()).hexdigest()
    rows=[]
    with tempfile.TemporaryDirectory() as d:
        directory=Path(d);gate=MinimalGate();assert gate.observe_action('boot',raw,pin,'none')['allowed']
        def read():raise BlockingIOError(errno.EAGAIN,'empty')
        reader=PersistentKmsg(read=read);reader.raw=raw
        compact_kernel_record(directory,dict(raw_log=raw))
        for repeat in range(5):
            cpu=time.process_time();begin=time.perf_counter()
            for _ in range(300):
                current=reader.drain();result=gate.observe_action('boot',current,None,'none');assert result['allowed']
                compact_kernel_record(directory,dict(raw_log=current,**result))
            rows.append(dict(component='kernel_drain_gate_archive',repeat=repeat,calls=300,wall_s=time.perf_counter()-begin,cpu_s=time.process_time()-cpu))
        paths=[directory/'lock1',directory/'lock2'];fds=[]
        for path in paths:
            fd=os.open(path,os.O_CREAT|os.O_RDWR,0o600);fcntl.flock(fd,fcntl.LOCK_EX);fds.append(fd)
        if args.variant=='candidate':
            from cpu02_support import owned_lock_fds
            check=lambda:owned_lock_fds(paths,fds,os.getpid())
        else:check=lambda:all(lock_owned(path,os.getpid()) for path in paths)
        for repeat in range(5):
            cpu=time.process_time();begin=time.perf_counter()
            for _ in range(300):assert check()
            rows.append(dict(component='fresh_canonical_locks',repeat=repeat,calls=300,wall_s=time.perf_counter()-begin,cpu_s=time.process_time()-cpu))
        for fd in fds:os.close(fd)
        for repeat in range(5):
            folder=directory/('record'+str(repeat));folder.mkdir();w=OwnedWorker.__new__(OwnedWorker);w.directory=folder;w.records=[];w._lock=threading.Lock()
            cpu=time.process_time();begin=time.perf_counter()
            for i in range(100):w.record(event='PERMISSION',allow=True,request=dict(sequence=i,job=i,pid=1234,phase='submit'),health_observation=dict(checked_monotonic_ns=i,checks_skipped=False,kernel=dict(allowed=True,sha256=pin)))
            rows.append(dict(component='durable_record_real_fsync',repeat=repeat,calls=100,wall_s=time.perf_counter()-begin,cpu_s=time.process_time()-cpu))
            assert len([json.loads(s) for s in (folder/'events.jsonl').read_text().splitlines()])==100
            if hasattr(w,'_journal'):w._journal.close()
    result=dict(status='PC_COMPONENT_MEASUREMENT_ONLY',variant=args.variant,kernel_snapshot_bytes=len(raw.encode()),rows=rows,BOARD='NOT_TESTED')
    with (OUT/('BENCH_'+args.variant+('_'+args.tag if args.tag else '')+'.json')).open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps(dict(variant=args.variant,median_ms_per_call={name:statistics.median(r['wall_s']/r['calls']*1000 for r in rows if r['component']==name) for name in sorted({r['component'] for r in rows})})))
