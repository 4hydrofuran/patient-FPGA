"""Persistent native ABI caller. Pure helpers injectable for PC tests.

Actual outputs are copied ONLY from sp_linear_run's guarded destination.
References are consulted after timing and never passed to the native backend.
An exception after entry parks without closing or freeing native handles.
"""
import ctypes as C
import hashlib
import json
import math
from pathlib import Path
import struct
import time


def need(ok,reason):
    if not ok:raise RuntimeError(reason)


def sha(data):return hashlib.sha256(data).hexdigest()


def resources(report,loads,previous_io=None):
    addresses=report['a11_io_bo_addresses'];sizes=report['a11_io_bo_charged_sizes']
    need(len(addresses)==len(sizes)==4 and sizes==[40960,8192,155648,8192],'IO BO layout differs')
    need(report['a11_argument_groups']==[3]*6,'MLP BO group differs')
    need(report['a11_explicit_bo_allocations_host_counter']==4+2*loads,'unexpected explicit BO creation')
    if previous_io is not None:need(addresses==previous_io,'IO workspace not reused')
    spans=list(zip(addresses,sizes))
    for weight in report['a11_live_weights']:
        need(len(weight['addresses'])==len(weight['charged_sizes'])==2,'weight BO layout differs')
        spans+=list(zip(weight['addresses'],weight['charged_sizes']))
    for i,(address,size) in enumerate(spans):
        need(type(address) is int and type(size) is int and size>=8192 and size%8192==0 and address>=0 and
             address+size<=0x80000000,'BO not in metadata low-address window')
        need(all(address+size<=a or a+s<=address for a,s in spans[:i]),'overlapping BO addresses')
    need(sum(s for a,s in spans)==report['owned_bo_charged_bytes']<=4194304,'BO budget/accounting differs')
    return addresses


class NativeAPI:
    def __init__(self,source):
        self.lib=C.CDLL(str(source/'libsp_linear_a11_trial.so'))
        self.quant=C.CDLL(str(source/'liba11_quant.so'))
        p,u,q=C.c_void_p,C.c_uint32,C.c_uint64
        signatures={
            'open':([C.c_char_p,C.POINTER(p)]),
            'load':([p,u,u,p,q,p,q,C.POINTER(q)]),
            'run':([p,q,u,p,q,p,q,p,q,q,u]),
            'report':([p,p,q,C.POINTER(q)]),'unload':([p,q]),'close':([p])}
        for name,args in signatures.items():
            f=getattr(self.lib,'sp_linear_'+name+'_v1');f.restype=C.c_int32;f.argtypes=args
            setattr(self,name,f)
        self.quant.a11_quant.argtypes=[u,u,u,p,q,p,q,p,q]
        self.quant.a11_quant.restype=C.c_int
        self.quantize=self.quant.a11_quant


def comparison(actual,golden,n,t):
    need(len(actual)==len(golden) and len(actual)%4==0,'output/reference size mismatch')
    a=struct.unpack('<'+'f'*(len(actual)//4),actual)
    b=struct.unpack('<'+'f'*(len(golden)//4),golden)
    np=(n+31)//32*32
    need(len(a)==t*np,'output shape mismatch')
    bad=[];padding=[];max_abs=0.;max_rel=0.
    for i,(x,y) in enumerate(zip(a,b)):
        delta=abs(x-y)
        if math.isfinite(delta):
            max_abs=max(max_abs,delta);max_rel=max(max_rel,delta/max(abs(y),1e-30))
        if not math.isfinite(x) or not math.isfinite(y) or delta>1e-4+1e-5*abs(y):bad.append(i)
        if i%np>=n and x!=0:padding.append(i)
    return dict(numeric_pass=not bad and not padding,max_abs_error=max_abs,max_rel_error=max_rel,
                mismatch_count=len(bad),first_mismatch_indices=bad[:16],padding_errors=padding[:16],
                atol=1e-4,rtol=1e-5,bit_exact=actual==golden)


class GuardedBuffer:
    def __init__(self,size):
        self.size=size;self.raw=(C.c_ubyte*(size+128))()
        self.ptr=C.c_void_p(C.addressof(self.raw)+64)
        C.memset(C.addressof(self.raw),0xA5,size+128)
    def intact(self):return bytes(self.raw[:64])==bytes([0xA5])*64 and bytes(self.raw[-64:])==bytes([0xA5])*64


def run_plan(api,source,plan,permit,emit,quarantine,*,clock=time.perf_counter_ns):
    ctx=C.c_void_p();handle=C.c_uint64();current=None;loads=[];calls=[]
    # Reused caller workspace; backend separately reuses all four IO BOs.
    output=GuardedBuffer(8*4864*4);xq=C.create_string_buffer(8*4864);sx=C.create_string_buffer(8*4)
    report_buffer=C.create_string_buffer(65536)
    ms=lambda a,b:(b-a)/1e6
    def ok(rc,name):need(type(rc) is int and rc==0,name+' failed status='+str(rc))
    def report():
        size=C.c_uint64();ok(api.report(ctx,report_buffer,len(report_buffer),C.byref(size)),'report')
        need(0<size.value<=len(report_buffer),'invalid report size')
        return json.loads(report_buffer.value)
    def read(path,meta):
        data=(source/path).read_bytes()
        need(len(data)==meta['bytes'] and sha(data)==meta['sha256'],'frozen file changed: '+str(path))
        return data
    try:
        permit('open',0)
        before=clock();ok(api.open(str(source/'trial-config.json').encode(),C.byref(ctx)),'open');opened=clock()
        need(ctx.value,'null context')
        initial_report=report();io_addresses=resources(initial_report,0)
        emit('CONTEXT_OPENED',open_ms=ms(before,opened),report=initial_report)
        for item in plan['schedule']:
            case=plan['cases'][item['case']];n,k,t=case['N'],case['K'],case['T']
            xb=t*k*4;qb=t*((k+127)//128*128);sb=t*4;yb=t*((n+31)//32*32)*4
            # Preload frozen activation and reference outside the service timer.
            inp=read(Path('vectors/inputs')/item['case']/'x.f32',case['files']['x.f32'])
            expected_q=read(Path('vectors/inputs')/item['case']/'xq.bin',case['files']['xq.bin'])
            expected_s=read(Path('vectors/inputs')/item['case']/'sx.bin',case['files']['sx.bin'])
            golden=read(Path('vectors/pc_reference')/item['case']/'y.bin',case['golden']['y.bin'])
            x=C.create_string_buffer(inp,len(inp))
            if current!=item['weight']:
                permit('weight',item['job_id'])
                if current is not None:ok(api.unload(ctx,handle),'unload')
                weight=plan['weights'][item['weight']]
                load_start=clock()
                w=read(Path('vectors/inputs')/item['weight']/'w.bin',weight['files']['w.bin'])
                sw=read(Path('vectors/inputs')/item['weight']/'sw.bin',weight['files']['sw.bin'])
                read_end=clock()
                wbuf=C.create_string_buffer(w,len(w));sbuf=C.create_string_buffer(sw,len(sw))
                copy_end=clock()
                ok(api.load(ctx,n,k,wbuf,len(w),sbuf,len(sw),C.byref(handle)),'load');load_end=clock()
                need(handle.value,'zero weight handle');current=item['weight']
                loads.append(dict(weight=current,weight_handle=handle.value,read_ms=ms(load_start,read_end),
                    caller_copy_ms=ms(read_end,copy_end),api_load_ms=ms(copy_end,load_end),
                    cold_total_ms=ms(load_start,load_end),post_load_report=report()))
                resources(loads[-1]['post_load_report'],len(loads),io_addresses)
                resident_bos=loads[-1]['post_load_report']['a11_live_weights']
                emit('WEIGHT_LOADED',**loads[-1])
            permit('submit',item['job_id'])
            # Poison complete caller output; check suffix directly after actual Y
            # as well as the fixed workspace canaries, outside measured service.
            C.memset(output.ptr,0xA5,output.size)
            begin=clock()
            ok(api.quantize(n,k,t,x,xb,xq,qb,sx,sb),'quantize');quant_end=clock()
            ok(api.run(ctx,handle,t,xq,qb,sx,sb,output.ptr,yb,item['job_id'],5000),'run');api_end=clock()
            actual=C.string_at(output.ptr,yb);end=clock()
            report_start=clock();r=report();report_end=clock()
            # Dump actual output before checking anything; never replace by golden.
            dest=source/'outputs'/f"job-{item['job_id']:02}.f32"
            with dest.open('xb') as f:f.write(actual)
            cmp=comparison(actual,golden,n,t)
            guards=output.intact() and C.string_at(output.ptr.value+yb,output.size-yb)==bytes([0xA5])*(output.size-yb)
            valid=(r.get('status')=='READY' and r.get('execution_kind')=='FPGA_REAL' and
                   r.get('output_consumable') is True and r.get('job_id')==item['job_id'] and
                   r.get('kernel_build_id')==0xB3030002 and r.get('last_status_code')==0 and
                   r.get('host_verified_completions')==item['job_id'] and
                   r.get('private_meta_host_seeded_count')==1 and r.get('weight_load_count')==len(loads))
            row=dict(item,**cmp,guards_intact=guards,status_code=0,completion_validated=valid,
                kernel_build_id=r.get('kernel_build_id'),output_consumable=r.get('output_consumable'),
                host_verified_completions=r.get('host_verified_completions'),actual_output_sha256=sha(actual),
                actual_output_file=str(dest.relative_to(source)),input_quant_ms=ms(begin,quant_end),
                api_run_ms=ms(quant_end,api_end),output_copy_ms=ms(api_end,end),service_ms=ms(begin,end),
                report_ms=ms(report_start,report_end),hardware_cycles=None,measured_AXI_bytes=None,pure_kernel_ms=None,
                service_scope='quantization plus complete ABI call including sync and caller output copies; excludes golden, diagnostics, permit wait',
                quant_bytes_match=C.string_at(xq,qb)==expected_q and C.string_at(sx,sb)==expected_s,
                native_report=r,weight_handle=handle.value)
            calls.append(row);emit('ACTUAL_CALL_RESULT',**row)
            resources(r,len(loads),io_addresses)
            need(r['a11_live_weights']==resident_bos,'warm call replaced weight BOs')
            need(valid and guards and cmp['numeric_pass'] and row['quant_bytes_match'],'result gate failed; no next submission')
            permit('completed',item['job_id'])
        permit('close',23)
        ok(api.unload(ctx,handle),'final unload');ok(api.close(ctx),'close')
        ctx=C.c_void_p()
        return dict(calls=calls,loads=loads,real_submissions=len(calls),weight_loads=len(loads),
                    normal_handles_closed=True,status='NORMAL_CLOSED_A11_MINIMAL',
                    output_guard_scope='caller buffer prefix/suffix plus padded output; not arbitrary DMA address proof',
                    hardware_integer_debug='NOT_TESTED_INTERFACE_ABSENT')
    except BaseException as exc:
        # Do not unwind stack/ctypes handles if native completion is unknown.
        quarantine(type(exc).__name__+': '+str(exc),ctx,handle,api,calls)
        raise RuntimeError('QUARANTINE_RETURNED')
