"""Real CPU arrays through the new adapter; optional second DSO mapping."""
import ctypes as c
import json
import os
from pathlib import Path
import shutil
import sys
import time
from native_cpu_abi_probe import bind,report,emit

def main():
    cfg=json.loads(Path(sys.argv[1]).read_text());a=bind(cfg['adapter']);ctx=c.c_void_p()
    rc=a.open(cfg['adapter_config'].encode(),c.byref(ctx))
    if rc:emit(dict(type='open_refused',rc=rc));return
    core=bind(cfg['cpu']);reference=c.c_void_p();assert core.open(cfg['cpu_config'].encode(),c.byref(reference))==0
    n,k=32,128;w=(c.c_uint8*(n*k//2))(*([0x76]*(n*k//2)));sw=(c.c_float*n)(*([.125]*n))
    golden=c.c_uint64();assert core.load(reference,n,k,w,len(w),sw,c.sizeof(sw),c.byref(golden))==0
    def load(lib,context):
        handle=c.c_uint64();assert lib.load(context,n,k,w,len(w),sw,c.sizeof(sw),c.byref(handle))==0;return handle
    handles={'a':(a,ctx,load(a,ctx))}
    emit(dict(type='ready',report=report(a,ctx)))
    for line in sys.stdin:
        q=json.loads(line)
        if q['op']=='exit':break
        if q['op']=='clone':
            target=Path(sys.argv[1]).parent/'liba12_second_mapping.so';shutil.copyfile(cfg['adapter'],target)
            second=bind(str(target));context=c.c_void_p();assert second.open(cfg['adapter_config'].encode(),c.byref(context))==0
            handles['b']=(second,context,load(second,context));emit(dict(type='cloned',report=report(second,context)));continue
        lib,context,handle=handles[q.get('context','a')];t=q.get('T',1);job=q['job']
        if q.get('wait_parent_exit_pid'):
            until=time.monotonic()+5
            while os.getppid()==q['wait_parent_exit_pid'] and time.monotonic()<until:time.sleep(.001)
            assert os.getppid()!=q['wait_parent_exit_pid'],'test manager did not exit'
        x=(c.c_int8*(t*k))(*[(i%7)-3 for i in range(t*k)]);sx=(c.c_float*t)(*([.25]*t))
        y=(c.c_float*(t*n))(*([123.5]*(t*n)));before=bytes(y);expected=(c.c_float*(t*n))()
        size=1 if q.get('bad_size') else c.sizeof(y)
        rc=lib.run(context,handle,t,x,len(x),sx,c.sizeof(sx),y,size,job,30000)
        oracle=core.run(reference,golden,t,x,len(x),sx,c.sizeof(sx),expected,c.sizeof(expected),job,30000) if rc==0 else None
        row=dict(type='result',rc=rc,oracle_rc=oracle,bit_exact=bytes(y)==bytes(expected) if rc==0 else None,
            unchanged=bytes(y)==before if rc else None,report=report(lib,context),PL_calls=0)
        if q.get('parent_exit_report'):
            row.update(probe_pid=os.getpid(),observed_parent=os.getppid(),old_manager=q['wait_parent_exit_pid'])
            Path(q['parent_exit_report']).write_text(json.dumps(row));break
        emit(row)
    for lib,context,handle in handles.values():lib.unload(context,handle);lib.close(context)
    core.unload(reference,golden);core.close(reference)

if __name__=='__main__':main()
