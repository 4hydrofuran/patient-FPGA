"""Independent standard-library scalar oracle. Never imports producer/HLS/C++.

Explicit binary32 rounding via struct, Python integer accumulators, scalar
row/group loops and direct byte addressing (not producer reshape/transpose).
"""
import math,struct


def f32(x):
    try:y=struct.unpack('<f',struct.pack('<f',x))[0]
    except OverflowError:raise ValueError('FP32 overflow') from None
    if not math.isfinite(y):raise ValueError('Nonfinite FP32')
    return y


def dims(n,k,t=1):
    if any(type(v) is not int for v in (n,k,t)) or not (1<=n<=4864 and 1<=k<=4864 and 1<=t<=8):raise ValueError('Invalid shape before sizing')
    return (n+31)//32*32,(k+127)//128*128


def quant_row(values,limit):
    v=[f32(x) for x in values];maximum=max(map(abs,v));s=f32(maximum/limit) if maximum else 1.0
    if s<=0:raise ValueError('Scale underflow')
    return [min(limit,max(-limit,round(f32(x/s)))) for x in v],s


def pack_weights(rows):
    n=len(rows);k=len(rows[0]);npad,kpad=dims(n,k);g=kpad//128
    if any(len(r)!=k for r in rows):raise ValueError('Ragged')
    w=bytearray(npad*kpad//2);sc=[1.0]*(npad*g)
    for row in range(n):
        for group in range(g):
            q,s=quant_row(rows[row][group*128:min(k,(group+1)*128)],7)
            sc[(row//32*g+group)*32+row%32]=s
            for j,code in enumerate(q):
                offset=((row//32*g+group)*128+j)*16+(row%32)//2
                w[offset]|=(code&15)<<(4*(row%2))
    return bytes(w),struct.pack('<'+'f'*len(sc),*sc)


def quant_activations(rows):
    t=len(rows);k=len(rows[0]);_,kp=dims(1,k,t);q=[];s=[]
    for row in rows:
        if len(row)!=k:raise ValueError('Ragged')
        codes,scale=quant_row(row,127);q.extend(codes+[0]*(kp-k));s.append(scale)
    return struct.pack('<'+'b'*len(q),*q),struct.pack('<'+'f'*t,*s)


def execute(n,k,t,w,sw,xq,sx):
    npad,kpad=dims(n,k,t);g=kpad//128
    if (len(w),len(sw),len(xq),len(sx))!=(npad*kpad//2,npad*g*4,t*kpad,t*4):raise ValueError('Exact buffer lengths required')
    scales=struct.unpack('<'+'f'*(npad*g),sw);xs=struct.unpack('<'+'f'*t,sx)
    x=memoryview(xq).cast('b')
    if any(not math.isfinite(v) or v<=0 for v in (*scales,*xs)):raise ValueError('Bad scale')
    if -128 in x:raise ValueError('Reserved A8 code')
    if any(x[row*kpad+j] for row in range(t) for j in range(k,kpad)):raise ValueError('A8 tail')
    y=[0.0]*(t*npad);sums=[0]*(t*npad*g)
    # Each (row, group) is decoded once, reused across T without calling DUT.
    for row in range(npad):
        for group in range(g):
            codes=[]
            for j in range(128):
                b=w[((row//32*g+group)*128+j)*16+(row%32)//2]
                v=(b>>(4*(row%2)))&15;v=v-16 if v>=8 else v
                if v==-8 or ((row>=n or group*128+j>=k) and v):raise ValueError('Reserved/tail W4')
                codes.append(v)
            scale=scales[(row//32*g+group)*32+row%32]
            if row>=n and scale!=1.0:raise ValueError('Padding scale')
            for token in range(t):
                base=token*kpad+group*128
                acc=sum(codes[j]*x[base+j] for j in range(128))
                sums[(token*npad+row)*g+group]=acc
                y[token*npad+row]=f32(y[token*npad+row]+f32(f32(float(acc)*scale)*xs[token]))
    return y,sums
