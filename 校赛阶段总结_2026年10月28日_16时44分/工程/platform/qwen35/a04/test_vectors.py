"""Independent golden and negative input regression. All inputs/commands kept."""
import argparse,json,struct,subprocess,time,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
import numpy as np
from quant.export_w4a8.core import weights,activations
from quant.reference import scalar as ref
PKG=ROOT/'docs/plan_qwen35/KV260_Qwen35_A_详细设计增强任务包_20261002/KV260_Qwen35_A_设计增强包_20261002'


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);ap.add_argument('--binary',required=True);a=ap.parse_args()
    a.output.mkdir(parents=True,exist_ok=False);checks=[];commands=[]
    def check(name,ok):
        checks.append({'name':name,'passed':bool(ok)})
    def run(argv,expect=0):
        r=subprocess.run([a.binary,*map(str,argv)],capture_output=True,text=True)
        commands.append({'argv':[a.binary,*map(str,argv)],'exit_code':r.returncode,'stdout':r.stdout,'stderr':r.stderr,'expected_exit':expect})
        check('command_'+str(len(commands)),r.returncode==expect)
        return r
    def write(p,raw):
        with p.open('xb') as f:f.write(raw)
    def compare(name,n,k,t,w,sw,xq,sx,xf=None):
        d=a.output/name;d.mkdir()
        for nm,data in [('w',w),('sw',sw),('xq',xq),('sx',sx)]:write(d/(nm+'.bin'),data)
        if xf is not None:
            write(d/'xf.bin',xf.astype('<f4').tobytes());args=['run',n,k,t,d/'w.bin',d/'sw.bin',d/'xf.bin',d/'cpp']
        else:args=['run-q',n,k,t,d/'w.bin',d/'sw.bin',d/'xq.bin',d/'sx.bin',d/'cpp']
        y,sums=ref.execute(n,k,t,w,sw,xq,sx)
        write(d/'gold_y.bin',struct.pack('<'+'f'*len(y),*y));write(d/'gold_sums.bin',struct.pack('<'+'i'*len(sums),*sums))
        r=run(args)
        if r.returncode==0:
            for nm,expected in [('y',(d/'gold_y.bin').read_bytes()),('sums',(d/'gold_sums.bin').read_bytes()),('xq',xq),('sx',sx)]:
                check(name+'_'+nm+'_bit_exact',(d/'cpp'/(nm+'.bin')).read_bytes()==expected)
        return d
    fixture=PKG/'fixtures';h=json.loads((fixture/'hand_sample.json').read_text())
    d=compare('hand',2,2,1,*[(fixture/n).read_bytes() for n in ('w_packed.bin','sw.bin','xq.bin','sx.bin')])
    check('hand_outputs_expected',(d/'gold_y.bin').read_bytes()==(fixture/'expected_y.bin').read_bytes())
    check('hand_nibbles',(fixture/'w_packed.bin').read_bytes()[0]==0x97 and (fixture/'w_packed.bin').read_bytes()[16]==0x2f)
    rng=np.random.default_rng(402)
    cases=[('ties',np.array([[7,.5,1.5,2.5,-.5,-1.5,-2.5],[-7,-.5,-1.5,-2.5,.5,1.5,2.5]],dtype=np.float32),
                   np.array([[127,.5,1.5,2.5,-.5,-1.5,-2.5]],dtype=np.float32)),
           ('zero',np.zeros((33,129),np.float32),np.zeros((1,129),np.float32)),
           ('subnormal',np.full((2,2),np.float32(1e-40)),np.full((1,2),np.float32(1e-35))),
           ('max_integer',np.full((1,128),7,np.float32),np.full((1,128),127,np.float32))]
    for t in range(1,9):
        w=rng.normal(size=(33,129)).astype(np.float32);w[:,:128]*=np.float32(.03125);w[:,128]*=32
        x=rng.normal(size=(t,129)).astype(np.float32);cases.append((f'tail_t{t}',w,x))
    for name,w,x in cases:
        n,k=map(int,w.shape);t=int(x.shape[0]);expected=ref.pack_weights(w.tolist());actual=weights(w)
        check(name+'_producer_W',actual==expected)
        xd=ref.quant_activations(x.tolist());check(name+'_producer_A',activations(x)==xd)
        d=compare(name,n,k,t,*expected,*xd,xf=x)
        write(d/'wf.bin',w.astype('<f4').tobytes());r=run(['pack',n,k,d/'wf.bin',d/'cpp-pack'])
        if r.returncode==0:check(name+'_independent_cpp_pack',((d/'cpp-pack/w.bin').read_bytes(),(d/'cpp-pack/sw.bin').read_bytes())==expected)
        if name=='max_integer':check('group_bound_113792',struct.unpack('<i',(d/'gold_sums.bin').read_bytes()[:4])[0]==113792)
    # Fixed-order cancellation example: ((2^24 + 1) - 2^24) == 0 in FP32,
    # whereas regrouping terms or accumulating in FP64 produces 1.
    n,k,t=1,257,1;npad,kp=ref.dims(n,k);g=kp//128
    wb=bytearray(npad*kp//2);sc=[1.0]*(npad*g);xb=bytearray(kp)
    for group in range(3):wb[group*128*16]=1 if group<2 else 15;xb[group*128]=1
    sc[0]=2**24;sc[32]=1;sc[64]=2**24
    d=compare('fp32_order',n,k,t,bytes(wb),struct.pack('<'+'f'*len(sc),*sc),bytes(xb),struct.pack('<f',1))
    check('fp32_sequential_not_double',struct.unpack('<f',(d/'gold_y.bin').read_bytes()[:4])[0]==0)
    # Reject invalid producer inputs instead of silently clipping nonfinite/tiny values.
    bad=a.output/'negative';bad.mkdir()
    for tag,value in [('nan',np.nan),('posinf',np.inf),('neginf',-np.inf),('scale_underflow',np.nextafter(np.float32(0),np.float32(1)))]:
        w=np.array([[value]],np.float32);write(bad/(tag+'.bin'),w.tobytes())
        for label,fn in [('producer_W',lambda:weights(w)),('producer_A',lambda:activations(w)),('oracle',lambda:ref.pack_weights(w.tolist()))]:
            try:fn();ok=False
            except (ValueError,FloatingPointError):ok=True
            check(tag+'_'+label,ok)
        run(['pack',1,1,bad/(tag+'.bin'),bad/(tag+'-pack')],2)
        hand=d=a.output/'hand'
        # Shape1 files are independently constructed with the oracle, no producer expected values.
        one_w,one_s=ref.pack_weights([[1.0]])
        for nm,data in [('onew',one_w),('ones',one_s)]:
            if not (bad/(nm+'.bin')).exists():write(bad/(nm+'.bin'),data)
        run(['run',1,1,1,bad/'onew.bin',bad/'ones.bin',bad/(tag+'.bin'),bad/(tag+'-run')],2)
    base=[(fixture/n).read_bytes() for n in ('w_packed.bin','sw.bin','xq.bin','sx.bin')]
    variants={}
    for i,nm in enumerate(('w','sw','xq','sx')):
        for sign in ('short','long'):
            v=list(base);v[i]=v[i][:-1] if sign=='short' else v[i]+b'\0';variants[nm+'_'+sign]=v
    for name,index,offset,value in [('w_minus8',0,0,0x98),('w_tail',0,1,1),('a_minus128',2,0,128),('a_tail',2,4,1)]:
        v=list(base);b=bytearray(v[index]);b[offset]=value;v[index]=bytes(b);variants[name]=v
    for name,index,offset,value in [('sw_zero',1,0,0),('sw_nan',1,0,float('nan')),('sx_negative',3,0,-1),('sx_inf',3,0,float('inf')),('pad_scale',1,8,2),('restore_overflow',1,0,float(np.finfo(np.float32).max))]:
        v=list(base);b=bytearray(v[index]);b[offset:offset+4]=struct.pack('<f',value);v[index]=bytes(b);variants[name]=v
    for name,v in variants.items():
        d=bad/name;d.mkdir()
        for nm,b in zip(('w','sw','xq','sx'),v):write(d/(nm+'.bin'),b)
        try:ref.execute(2,2,1,*v);ok=False
        except ValueError:ok=True
        check(name+'_oracle_reject',ok)
        run(['run-q',2,2,1,*[d/(nm+'.bin') for nm in ('w','sw','xq','sx')],d/'cpp'],2)
        check(name+'_no_output',not (d/'cpp/y.bin').exists())
    for n,k,t in [(0,2,1),(2,0,1),(2,2,0),(2,2,9),(4865,2,1),(1,4865,1),(2**64-1,2**64-1,8)]:
        run(['run-q',n,k,t,'NOT_OPENED','NOT_OPENED','NOT_OPENED','NOT_OPENED',bad/f'dim{n}-{k}-{t}'],2)
        try:ref.dims(n,k,t);ok=False
        except ValueError:ok=True
        check(f'dim_{n}_{k}_{t}_oracle',ok)
    result={'domain':'PC','checks':checks,'commands':commands,'passed':all(c['passed'] for c in checks),
        'independence':'expected bytes/numerics from pure Python scalar, never DUT/HLS; fixed hand expected binary supplied by task package',
        'BOARD':'NOT_TESTED','binary':a.binary}
    with (a.output/'summary.json').open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps({'checks':len(checks),'failed':[c['name'] for c in checks if not c['passed']]}))
    return 0 if result['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
