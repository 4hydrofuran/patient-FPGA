"""Owned PC child exercising the adapter and pinned CPU ABI on real arrays."""
import ctypes as c
import json
import sys


def bind(path):
    lib=c.CDLL(path)
    signatures={
        'open':[c.c_char_p,c.POINTER(c.c_void_p)],
        'load':[c.c_void_p,c.c_uint32,c.c_uint32,c.POINTER(c.c_uint8),c.c_uint64,c.POINTER(c.c_float),c.c_uint64,c.POINTER(c.c_uint64)],
        'run':[c.c_void_p,c.c_uint64,c.c_uint32,c.POINTER(c.c_int8),c.c_uint64,c.POINTER(c.c_float),c.c_uint64,
               c.POINTER(c.c_float),c.c_uint64,c.c_uint64,c.c_uint32],
        'report':[c.c_void_p,c.c_void_p,c.c_uint64,c.POINTER(c.c_uint64)],
        'unload':[c.c_void_p,c.c_uint64],'close':[c.c_void_p]}
    for name,args in signatures.items():
        f=getattr(lib,'sp_linear_'+name+'_v1');f.argtypes=args;f.restype=c.c_int32;setattr(lib,name,f)
    return lib


def report(lib,ctx):
    n=c.c_uint64();assert lib.report(ctx,None,0,c.byref(n))==0 and 1<n.value<=65536
    out=c.create_string_buffer(n.value);assert lib.report(ctx,out,n.value,c.byref(n))==0
    return json.loads(out.value)


def emit(value):print(json.dumps(value),flush=True)


def main():
    config=json.load(open(sys.argv[1],encoding='utf-8'));adapter=bind(config['adapter'])
    ctx=c.c_void_p();rc=adapter.open(config['adapter_config'].encode(),c.byref(ctx))
    if rc!=0:
        emit(dict(type='abi_open_refused',rc=rc,context_null=ctx.value is None,PL_calls=0));return
    core=bind(config['cpu']);base=c.c_void_p();assert core.open(config['cpu_config'].encode(),c.byref(base))==0
    n,k=32,128;w=(c.c_uint8*(n*k//2))(*([0x76]*(n*k//2)));sw=(c.c_float*n)(*([0.125]*n))
    handle=c.c_uint64();golden_handle=c.c_uint64()
    assert core.load(base,n,k,w,len(w),sw,c.sizeof(sw),c.byref(golden_handle))==0
    assert adapter.load(ctx,n,k,w,len(w),sw,c.sizeof(sw),c.byref(handle))==0
    emit(dict(type='abi_ready',report=report(adapter,ctx),domain='PC_NATIVE_ABI_ARRAYS'))
    for line in sys.stdin:
        req=json.loads(line)
        if req['op']=='shutdown':break
        t=req.get('T',1);job=req['job'];x=(c.c_int8*(t*k))(*[(i%7)-3 for i in range(t*k)])
        sx=(c.c_float*t)(*([0.25]*t));y=(c.c_float*(t*n))(*([123.5]*(t*n)));before=bytes(y)
        golden=(c.c_float*(t*n))()
        size=1 if req.get('bad_size') else c.sizeof(y)
        rc=adapter.run(ctx,handle,t,x,len(x),sx,c.sizeof(sx),y,size,job,30000)
        reference_rc=core.run(base,golden_handle,t,x,len(x),sx,c.sizeof(sx),golden,c.sizeof(golden),job,30000) if rc==0 else None
        emit(dict(type='abi_result',rc=rc,reference_rc=reference_rc,bit_exact=bytes(y)==bytes(golden) if rc==0 else None,
            output_unchanged_on_error=bytes(y)==before if rc!=0 else None,report=report(adapter,ctx),PL_calls=0))
    unloaded=adapter.unload(ctx,handle);closed=adapter.close(ctx)
    core.unload(base,golden_handle);core.close(base)
    emit(dict(type='abi_closed',unload_rc=unloaded,close_rc=closed,PL_calls=0))


if __name__=='__main__':main()
