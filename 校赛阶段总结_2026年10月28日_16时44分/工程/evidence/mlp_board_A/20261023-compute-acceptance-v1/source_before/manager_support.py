"""A11 per-operation permits. No native libraries, device or mutation commands."""
import json
import os
import time
from mlp_policy import schedule,load_json,need


def operations():
    result=[('open',0)];current=None
    for row in schedule():
        if row['weight']!=current:
            result.append(('weight',row['job_id']));current=row['weight']
        result += [('submit',row['job_id']),('completed',row['job_id'])]
    return result+[('close',23)]


def pulse(manager):
    need(not (manager.source/'STOP.json').exists(),'worker stop latch')
    manager.guard()
    manager.kernel_checkpoint('worker_external_observer')
    index=getattr(manager,'permit_index',0)
    if index>=len(operations()):return
    path=manager.source/'permits'/f'ready-{index+1:03}.json'
    if not path.exists():return
    phase,job=operations()[index]
    expected=dict(manager.worker.identity,sequence=index+1,phase=phase,job=job)
    need(not path.is_symlink() and load_json(path)==expected,'unexpected worker operation')
    out=manager.source/'permits'/f'allow-{index+1:03}.json'
    pending=out.with_name(out.name+'.pending')
    with pending.open('x',encoding='utf-8') as f:
        json.dump(expected,f);f.flush();os.fsync(f.fileno())
    os.link(pending,out);pending.unlink()
    manager.permit_index=index+1
    manager.emit('NEXT_OPERATION_PERMITTED',sequence=index+1,phase=phase,job=job)


def latch_stop(manager,reason):
    path=manager.source/'STOP.json'
    if not path.exists():
        with path.open('x',encoding='utf-8') as f:
            json.dump(dict(reason=reason,resources_retained=True,monotonic_ns=time.monotonic_ns()),f)
            f.flush();os.fsync(f.fileno())
