"""Bounded ELF64/AArch64 section hashes. No loading, importing, or executing input."""
import hashlib,json,struct,sys
from pathlib import Path

def inspect(d):
    if not 64<=len(d)<=16777216 or d[:7]!=b'\x7fELF\x02\x01\x01':
        raise ValueError('Unsupported ELF or size')
    if struct.unpack_from('<H',d,18)[0]!=183:
        raise ValueError('Not AArch64')
    off=struct.unpack_from('<Q',d,40)[0]
    ent,num,idx=struct.unpack_from('<HHH',d,58)
    if ent!=64 or not 0<idx<num<=256 or off<64 or off+ent*num>len(d):
        raise ValueError('Invalid section table')
    table=[struct.unpack_from('<IIQQQQIIQQ',d,off+i*ent) for i in range(num)]
    def payload(s):
        if s[4]+s[5]>len(d):raise ValueError('Section out of bounds')
        return d[s[4]:s[4]+s[5]]
    if table[idx][1]!=3:raise ValueError('Invalid section names table')
    names=payload(table[idx]);rows=[]
    for s in table:
        if s[0]>=len(names) or names.find(b'\0',s[0])<0:raise ValueError('Invalid section name')
        name=names[s[0]:names.index(b'\0',s[0])].decode('ascii')
        if s[1] not in (0,8):
            rows.append(dict(name=name,flags=s[2],address=s[3],offset=s[4],bytes=s[5],sha256=hashlib.sha256(payload(s)).hexdigest()))
    return dict(bytes=len(d),sha256=hashlib.sha256(d).hexdigest(),sections=rows)

if __name__=='__main__':
    if not 1<=len(sys.argv[1:])<=2:raise ValueError('One or two explicit paths required')
    for arg in sys.argv[1:]:
        with Path(arg).open('rb') as f:d=f.read(16777217)
        print(json.dumps(dict(path=arg,**inspect(d))))
