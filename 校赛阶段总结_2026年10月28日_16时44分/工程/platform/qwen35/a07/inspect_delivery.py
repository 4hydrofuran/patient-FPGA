"""Read-only ZIP/XO inventory, not A06 numerical acceptance. Never executes/extracts files."""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import stat
import zipfile
import xml.etree.ElementTree as ET

MAX_TOTAL = 8 * 1024**3
MAX_XO = 256 * 1024**2

def safe_name(name):
    if not name or '\\' in name or ':' in name or '\x00' in name or name.startswith('/'):
        raise ValueError('unsafe archive path')
    parts = PurePosixPath(name).parts
    if not parts or any(p in ('..', '.') or p.endswith((' ', '.')) for p in parts):
        raise ValueError('unsafe archive component')
    for p in parts:
        if re.fullmatch(r'(CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9])(?:\..*)?', p, re.I):
            raise ValueError('Windows reserved component')
    if '// ' in name or any(p in ('.','..','') for p in name.rstrip('/').split('/')):
        raise ValueError('noncanonical archive path')
    return '/'.join(parts)

def entries(archive):
    found=set();total=0
    if len(archive.infolist())>20000:raise ValueError('file-count bound')
    for info in archive.infolist():
        safe_name(info.orig_filename)  # Reject raw names before platform normalization.
        key=safe_name(info.filename).casefold()
        if key in found:raise ValueError('duplicate/case-colliding member')
        found.add(key)
        mode=info.external_attr>>16
        if stat.S_ISLNK(mode) or stat.S_IFMT(mode) not in (0,stat.S_IFREG,stat.S_IFDIR):
            raise ValueError('link or special member refused')
        if info.flag_bits&1:raise ValueError('encrypted archive unsupported')
        total+=info.file_size
        if total>MAX_TOTAL:raise ValueError('uncompressed-size bound')
        if not info.is_dir():yield info

def inspect(path,expected=None):
    sha=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(8*1024**2),b''):sha.update(b)
    if expected and sha.hexdigest()!=expected:raise ValueError('outer SHA256 mismatch')
    files={};xo=[]
    with zipfile.ZipFile(path) as z:
        for info in entries(z):
            h=hashlib.sha256()
            with z.open(info) as f:
                for b in iter(lambda:f.read(1024**2),b''):h.update(b)
            files[info.filename]={'bytes':info.file_size,'sha256':h.hexdigest()}
            if info.filename.lower().endswith('.xo'):
                if info.file_size>MAX_XO:raise ValueError('XO size bound')
                with zipfile.ZipFile(io.BytesIO(z.read(info))) as nested:
                    candidates=[i for i in entries(nested) if PurePosixPath(i.filename).name=='kernel.xml']
                    if not candidates:raise ValueError('missing embedded kernel.xml')
                    canonical=[i for i in candidates if len(PurePosixPath(i.filename).parts)==2]
                    if len(candidates)==1:
                        xml=candidates[0]
                    elif len(canonical)==1:
                        xml=canonical[0]
                    else:raise ValueError('ambiguous embedded kernel.xml')
                    if xml.file_size>2*1024**2:raise ValueError('XML size bound')
                    data=nested.read(xml)
                    for copy in candidates:
                        if copy.file_size>2*1024**2 or nested.read(copy)!=data:
                            raise ValueError('conflicting embedded kernel.xml copies')
                    if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():raise ValueError('DTD refused')
                    root=ET.fromstring(data)
                    kernels=[]
                    for kernel in root.iter('kernel'):
                        kernels.append({'attributes':dict(kernel.attrib),
                            'args':[dict(e.attrib) for e in kernel.iter('arg')],
                            'ports':[dict(e.attrib) for e in kernel.iter('port')]})
                    xo.append({'path':info.filename,'sha256':h.hexdigest(),'embedded_metadata_path':xml.filename,
                        'embedded_metadata_sha256':hashlib.sha256(data).hexdigest(),
                        'identical_metadata_copies':[i.filename for i in candidates],'kernels':kernels})
    return {'scope':'ARCHIVE_INVENTORY_ONLY','archive_sha256':sha.hexdigest(),'files':files,'xo':xo,
        'missing_actual_xo':not xo,'accepted':False,'frozen':False,'BOARD':'NOT_TESTED',
        'note':'Inventory/hash/XML extraction cannot prove source/XO correspondence, numerical simulation or acceptance.'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('zip');p.add_argument('--sha256');p.add_argument('--out',required=True)
    a=p.parse_args();result=inspect(a.zip,a.sha256)
    with Path(a.out).open('x',encoding='utf-8') as f:json.dump(result,f,indent=2,ensure_ascii=False)
    print(json.dumps({'files':len(result['files']),'xo_count':len(result['xo']),'accepted':False}))
