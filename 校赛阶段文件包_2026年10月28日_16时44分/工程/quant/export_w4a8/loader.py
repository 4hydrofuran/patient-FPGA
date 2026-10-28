"""Read-only, hash checked A-side sidecar. One tensor at a time; no XRT."""
import hashlib,json
from pathlib import Path
import numpy as np
from .core import shape
ROOT=Path(__file__).resolve().parents[2]


class Sidecar:
    def __init__(self,path):
        self.root=Path(path).resolve()
        self.manifest=json.loads((self.root/'manifest.json').read_text(encoding='utf-8'))
        m=self.manifest
        if m['schema']!='A_W4A8_SIDECAR_V1' or m['contract']!='SP_W4A8_128x32_V1' or m['endian']!='little':raise ValueError('Sidecar identity')
        contract=json.loads((ROOT/'contracts/qwen35/contracts.lock').read_text())
        model=json.loads((ROOT/'models/model.lock.json').read_text())
        if m['contract_sha256']!=contract['contract_sha256'] or m['source_revision']!=model['revision']:raise ValueError('Contract/revision mismatch')
        for key,p in [('model_lock_sha256','models/model.lock.json'),('tensor_map_sha256','quant/qwen35_tensor_map.json')]:
            if m[key]!=hashlib.sha256((ROOT/p).read_bytes()).hexdigest():raise ValueError('Input identity mismatch')
        self.entries={e['id']:e for e in m['entries']}
        if len(m['entries'])!=72 or len(self.entries)!=72:raise ValueError('72 unique entries required')
        if set(self.entries)!={f'l{l:02d}_{o}' for l in range(24) for o in ('gate','up','down')}:raise ValueError('Identity inventory')
        for e in self.entries.values():
            if [e['N'],e['K']]!=([1024,3584] if e['op']=='down' else [3584,1024]):raise ValueError('Model shape')
            if e['id']!=f"l{e['layer']:02d}_{e['op']}" or e['bias'] is not None:raise ValueError('Layer/bias identity')
        self.checked=set()

    def load(self,ident):
        e=self.entries[ident];npad,kpad=shape(e['N'],e['K']);g=kpad//128
        if (e['Np'],e['Kp'],e['G'])!=(npad,kpad,g):raise ValueError('Padding metadata')
        outputs=[]
        for key,size,dtype,dims in [('w.bin',npad*kpad//2,'u1',(npad//32,g,128,16)),('sw.bin',npad*g*4,'<f4',(npad//32,g,32))]:
            f=e['files'][key];name=f['file']
            if not isinstance(name,str) or Path(name).name!=name or '\\' in name or ':' in name:raise ValueError('Unsafe path')
            p=self.root/name
            if p.is_symlink() or not p.resolve().is_relative_to(self.root):raise ValueError('Link escape')
            if p.stat().st_size!=size or f['bytes']!=size:raise ValueError('File length')
            # Hash only once per loader instance; immutable local assets required.
            if name not in self.checked:
                if hashlib.sha256(p.read_bytes()).hexdigest()!=f['sha256']:raise ValueError('File hash')
                self.checked.add(name)
            outputs.append(np.memmap(p,mode='r',dtype=dtype,shape=dims))
        return tuple(outputs)
