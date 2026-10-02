"""Offline fixture preparation only: bounded anti-alias 24 kHz to 16 kHz conversion."""
import numpy as np


def resample_24k_to_16k(pcm):
    samples=np.frombuffer(pcm,dtype='<i2').astype(np.float64)
    if not len(samples): raise ValueError('Cannot resample empty PCM')
    count=round(len(samples)*2/3)
    output=np.empty(count,dtype=np.float64)
    radius=32
    cutoff=(8000/24000)*.95
    offsets=np.arange(-radius,radius+1)
    for begin in range(0,count,8192):
        positions=np.arange(begin,min(begin+8192,count))*1.5
        indexes=np.floor(positions).astype(np.int64)[:,None]+offsets
        delta=positions[:,None]-indexes
        window=np.where(np.abs(delta)<=radius,.5+.5*np.cos(np.pi*delta/radius),0)
        kernel=2*cutoff*np.sinc(2*cutoff*delta)*window
        kernel/=kernel.sum(axis=1)[:,None]
        output[begin:begin+len(positions)]=(samples[np.clip(indexes,0,len(samples)-1)]*kernel).sum(axis=1)
    return np.clip(np.rint(output),-32768,32767).astype('<i2').tobytes()
