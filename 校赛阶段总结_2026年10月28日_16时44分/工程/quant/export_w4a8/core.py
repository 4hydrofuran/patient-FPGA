"""Production vectorized packing; independent oracles live in quant/reference.

Precision: FP32 inputs/absmax, correctly rounded FP32 division for scales and
normalized values, nearest ties-to-even, clamp. No epsilon or FTZ shortcut.
"""
import numpy as np


def shape(n,k):
    if type(n) is not int or type(k) is not int or not 1<=n<=4864 or not 1<=k<=4864:
        raise ValueError('N/K must be integers in 1..4864 (before multiplication)')
    return (n+31)//32*32,(k+127)//128*128


def fp_input(x):
    if not isinstance(x,np.ndarray) or x.dtype!=np.dtype('float32') or x.ndim!=2 or not np.isfinite(x).all():
        raise ValueError('finite FP32 matrix required; no implicit narrowing')
    return x


def weights(w):
    w=fp_input(w);n,k=map(int,w.shape);npad,kpad=shape(n,k);g=kpad//128
    p=np.zeros((npad,kpad),dtype=np.float32);p[:n,:k]=w
    groups=p.reshape(npad,g,128)
    maxima=np.max(np.abs(groups),axis=2)
    with np.errstate(under='ignore',over='raise',invalid='raise',divide='raise'):
        sw=np.divide(maxima,np.float32(7),dtype=np.float32)
        sw[maxima==0]=np.float32(1)
        if not np.isfinite(sw).all() or not (sw>0).all():
            raise ValueError('FP32 weight scale underflow/nonpositive; do not clamp to epsilon')
        q=np.clip(np.rint(np.divide(groups,sw[:,:,None],dtype=np.float32)),-7,7).astype(np.int8)
    lanes=q.reshape(npad//32,32,g,128).transpose(0,2,3,1)
    bits=lanes.astype(np.uint8)&15
    packed=(bits[:,:,:,0::2]|(bits[:,:,:,1::2]<<4)).copy()
    scales=sw.reshape(npad//32,32,g).transpose(0,2,1).copy().astype('<f4')
    return packed.tobytes(),scales.tobytes()


def activations(x):
    x=fp_input(x);t,k=map(int,x.shape)
    if not 1<=t<=8:raise ValueError('T must be 1..8')
    _,kp=shape(1,k)
    mx=np.max(np.abs(x),axis=1)
    with np.errstate(under='ignore',over='raise',invalid='raise',divide='raise'):
        sx=np.divide(mx,np.float32(127),dtype=np.float32);sx[mx==0]=1
        if not np.isfinite(sx).all() or not (sx>0).all():raise ValueError('FP32 activation scale underflow')
        q=np.zeros((t,kp),dtype=np.int8)
        q[:,:k]=np.clip(np.rint(np.divide(x,sx[:,None],dtype=np.float32)),-127,127).astype(np.int8)
    return q.tobytes(),sx.astype('<f4').tobytes()
