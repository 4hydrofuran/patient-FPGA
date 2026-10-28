"""Exercise the real shared C ABI against independent A04 bytes, no model mock."""
import argparse,ctypes as C,json,sys,threading,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--library',default='/home/member-a/qwen35-a05/build-v3/libsp_linear_cpu.so');args=p.parse_args()
OUT=ROOT/args.output;OUT.mkdir(exist_ok=False)
lib=C.CDLL(args.library)
ptr=C.c_void_p;u64=C.c_uint64;u32=C.c_uint32;i32=C.c_int32
signatures={'open':([C.c_char_p,C.POINTER(ptr)],i32),'load':([ptr,u32,u32,ptr,u64,ptr,u64,C.POINTER(u64)],i32),
 'run':([ptr,u64,u32,ptr,u64,ptr,u64,ptr,u64,u64,u32],i32),'report':([ptr,ptr,u64,C.POINTER(u64)],i32),
 'unload':([ptr,u64],i32),'close':([ptr],i32)}
for name,(args,result) in signatures.items():f=getattr(lib,'sp_linear_'+name+'_v1');f.argtypes=args;f.restype=result;globals()[name]=f
checks=[];reports=[]
def check(name,ok):checks.append({'name':name,'pass':bool(ok)})
def buf(raw):return C.create_string_buffer(raw,len(raw))
def load_case(ctx,w,sw,n,k):
    wa,sa=buf(w),buf(sw);h=u64();rc=load(ctx,n,k,wa,len(w),sa,len(sw),C.byref(h));return rc,h.value,wa,sa
def report_json(ctx):
    n=u64();assert report(ctx,None,0,C.byref(n))==0;a=C.create_string_buffer(n.value);assert report(ctx,a,n.value,C.byref(n))==0;return json.loads(a.value)
ctx=ptr();check('open',open(str(ROOT/'modules/linear_A/cpu_config.json').encode(),C.byref(ctx))==0)
cases=ROOT/'eval/qwen35/a04/vectors-v1';job=0
try:
    for name in ['hand','ties','zero','subnormal','max_integer','fp32_order']+[f'tail_t{t}' for t in range(1,9)]:
        d=cases/name;n,k,t=(2,2,1)
        if name=='ties':n,k,t=2,7,1
        elif name=='zero':n,k,t=33,129,1
        elif name=='max_integer':n,k,t=1,128,1
        elif name=='fp32_order':n,k,t=1,257,1
        elif name.startswith('tail_'):n,k,t=33,129,int(name[-1])
        w=(d/'w.bin').read_bytes();sw=(d/'sw.bin').read_bytes();x=(d/'xq.bin').read_bytes();sx=(d/'sx.bin').read_bytes();gold=(d/'gold_y.bin').read_bytes()
        rc,h,wa,sa=load_case(ctx,w,sw,n,k);check(name+' load',rc==0)
        # Caller data can be overwritten/freed immediately after successful load.
        C.memset(wa,0,len(w));C.memset(sa,0,len(sw));xa,sca=buf(x),buf(sx);y=buf(b'\xa5'*len(gold));job+=1
        rc=run(ctx,h,t,xa,len(x),sca,len(sx),y,len(gold),job,30000)
        check(name+' independent output',rc==0 and y.raw==gold);reports.append(report_json(ctx))
        check(name+' unload',unload(ctx,h)==0);check(name+' double unload rejected',unload(ctx,h)==1)
    d=cases/'hand';w=(d/'w.bin').read_bytes();sw=(d/'sw.bin').read_bytes();x=(d/'xq.bin').read_bytes();sx=(d/'sx.bin').read_bytes();gold=(d/'gold_y.bin').read_bytes()
    rc,h,wa,sa=load_case(ctx,w,sw,2,2);xa,sca=buf(x),buf(sx);y=buf(b'\xa5'*len(gold))
    for tag,hh,tt,xx,ss,yy,jj,timeout,expect in [('zero_handle',0,1,len(x),len(sx),len(gold),job+1,30000,1),
       ('zero_job',h,1,len(x),len(sx),len(gold),0,30000,1),('old_job',h,1,len(x),len(sx),len(gold),job,30000,1),
       ('T0',h,0,len(x),len(sx),len(gold),job+1,30000,1),('T9',h,9,len(x),len(sx),len(gold),job+1,30000,1),
       ('x_short',h,1,len(x)-1,len(sx),len(gold),job+1,30000,3),('sx_short',h,1,len(x),len(sx)-1,len(gold),job+1,30000,3),
       ('y_short',h,1,len(x),len(sx),len(gold)-1,job+1,30000,3),('timeout0',h,1,len(x),len(sx),len(gold),job+1,0,1)]:
        rc=run(ctx,hh,tt,xa,xx,sca,ss,y,yy,jj,timeout);check(tag,rc==expect and y.raw==b'\xa5'*len(gold))
    for name in ('w_minus8','w_tail','sw_zero','sw_nan','pad_scale','w_short','w_long','sw_short','sw_long'):
        d=cases/'negative'/name;rc,bh,*_=load_case(ctx,(d/'w.bin').read_bytes(),(d/'sw.bin').read_bytes(),2,2)
        check(name+' load rejects',rc in (1,3,9) and bh==0)
    for name in ('a_minus128','a_tail','sx_negative','sx_inf'):
        d=cases/'negative'/name;xx=(d/'xq.bin').read_bytes();ss=(d/'sx.bin').read_bytes()
        rc=run(ctx,h,1,buf(xx),len(xx),buf(ss),len(ss),y,len(gold),job+1,30000);check(name+' rejects',rc==9 and y.raw==b'\xa5'*len(gold))
    need=u64();check('report query',report(ctx,None,0,C.byref(need))==0 and need.value>1)
    small=buf(b'Z'*10);check('report no partial JSON',report(ctx,small,10,C.byref(need))==3 and small.raw==b'Z'*10)
    for n,k in [(0,1),(1,0),(4865,1),(2**32-1,2**32-1)]:
        hh=u64();check('size rejected before pointer read '+str((n,k)),load(ctx,n,k,wa,1,sa,1,C.byref(hh))==1)
    for field in ('device_id','xclbin_sha256','kernel_build_id','hardware_done_count','measured_bus_bytes','cycles','kernel_ms'):
        check('CPU not hardware '+field,report_json(ctx)[field] is None)
    check('all max T<=8',all(r['execution_kind']=='CPU_REFERENCE' for r in reports))
finally:check('close quiescent',close(ctx)==0)
# Real long scalar computation: timeout detection after synchronous CPU quiescence.
c=ptr();check('open scalar',open(str(ROOT/'modules/linear_A/cpu_scalar_config.json').encode(),C.byref(c))==0)
try:
    base=ROOT/'models/sidecar_A/qwen35-v1';w=(base/'l00_up.w.bin').read_bytes();sw=(base/'l00_up.sw.bin').read_bytes()
    rc,h,*_=load_case(c,w,sw,3584,1024);check('timeout load',rc==0)
    x=buf(bytes([1])*(8*1024));sx=buf(__import__('struct').pack('<8f',*([1]*8)));y=buf(bytes(8*3584*4))
    completed=[];entered=threading.Event()
    def compute():
        entered.set();completed.append(run(c,h,8,x,len(x),sx,len(sx),y,len(y),1,30000))
    thread=threading.Thread(target=compute);thread.start();entered.wait(1);observed=False
    deadline=time.monotonic()+2
    while thread.is_alive() and time.monotonic()<deadline:
        need=u64()
        if report(c,None,0,C.byref(need))==7:observed=True;break
        time.sleep(.0001)
    if observed:
        check('in-flight run BUSY',run(c,h,8,x,len(x),sx,len(sx),y,len(y),2,30000)==7)
        check('in-flight close BUSY retains ownership',close(c)==7)
    thread.join(5);check('real concurrency observed',observed and completed==[0] and not thread.is_alive())
    rc=run(c,h,8,x,len(x),sx,len(sx),y,len(y),2,1);check('real CPU deadline',rc==5);reports.append(report_json(c))
    check('poison rejects subsequent',run(c,h,8,x,len(x),sx,len(sx),y,len(y),3,30000)==6)
    check('CPU quiescence explicit',report_json(c)['cpu_quiescent'] is True)
finally:check('quiescent CPU timeout close',close(c)==0)
result={'domain':'PC','checks':checks,'reports':reports,'passed':all(c['pass'] for c in checks),'BOARD':'NOT_TESTED'}
with (OUT/'summary.json').open('x') as f:json.dump(result,f,indent=2)
print(json.dumps({'checks':len(checks),'failed':[c['name'] for c in checks if not c['pass']]}));raise SystemExit(not result['passed'])
