"""Bounded PC export rehearsal and full-byte numerical verification of diagnostics.

Export is deliberately PC-only/unbound for BOARD. No model/device/network calls;
the future board exporter requires separate release/authorization binding.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import stat
import zipfile

CHUNK = 1048576
MAX_FILE = 32 * CHUNK
MAX_MANIFEST = CHUNK
MAX_INDEX = 8 * CHUNK
MAX_FILES = 24576
MAX_TOTAL = 3 * 1024**3
MAX_ARCHIVE = MAX_TOTAL + 64 * CHUNK
CASES = ('full', 'warm', 'hit')
LOGITS_BYTES = 248320 * 4
STREAM_IDS = {f'l{layer:02}_{op}' for layer in range(24) for op in ('gate','up','down')}


class HandoffBlocked(RuntimeError):
    pass


def need(value, message):
    if not value:
        raise HandoffBlocked(message)


def leaf(name):
    need(type(name) is str and name not in ('','.','..') and not any(ord(c)<32 for c in name) and
         not any(c in name for c in ('/','\\','\x00',':')), 'unsafe filename')
    return name


def signature(st):
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns,
            st.st_uid, st.st_mode, st.st_nlink)


def directory(path):
    need(os.name == 'posix' and hasattr(os, 'O_NOFOLLOW'), 'Linux no-follow directory support required')
    path = Path(path)
    need(path.is_absolute() and '..' not in path.parts, 'absolute directory required')
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for name in path.parts[1:]:
            nxt = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd);fd = nxt
        st = os.fstat(fd)
        need(st.st_uid == os.geteuid() and not st.st_mode & 0o022, 'private owned source/output directory required')
        return fd
    except BaseException:
        os.close(fd)
        raise


def regular(st):
    need(stat.S_ISREG(st.st_mode) and st.st_uid == os.geteuid() and st.st_nlink == 1 and
         not st.st_mode & 0o022, 'private single-link regular file required')
    return signature(st)


def manifest_plan(raw):
    need(len(raw) <= MAX_MANIFEST, 'manifest too large')
    m = json.loads(raw)
    need(type(m) is dict and type(m.get('projections')) is list and type(m.get('logits')) is list,
         'manifest arrays absent')
    allowed = {'manifest.json':len(raw)}
    ids = set()
    def add(name, size):
        leaf(name)
        need(name not in allowed and type(size) is int and 0 < size <= MAX_FILE, 'duplicate/oversize raw file')
        allowed[name] = size
    for row in m['projections']:
        need(row.get('id') in STREAM_IDS, 'unknown projection stream')
        ids.add(row['id'])
        need(type(row.get('T')) is int and 1 <= row['T'] <= 8 and
             all(type(row.get(k)) is int and 1 <= row[k] <= 4864 for k in ('K','N')), 'invalid projection shape')
        add(row['input'],row['T']*row['K']*4)
        add(row['output'],row['T']*row['N']*4)
    need(ids == STREAM_IDS, 'complete 24-layer gate/up/down coverage required')
    positions = set()
    for row in m['logits']:
        p = row.get('position')
        need(type(p) is int and 0 <= p < 264 and p not in positions, 'invalid/duplicate logits position')
        positions.add(p)
        add(row['file'], LOGITS_BYTES)
    need(positions, 'logits absent')
    # State size comes from the actual completed file/archive inventory, never a guessed struct layout.
    return m, allowed


class DirectoryCase:
    def __init__(self, path):
        self.fd = directory(path)
        self.path = Path(path)
        self.files = {}
        self.signatures = {}
        self.read_bytes = 0
        self.advice_calls = 0
        self.failed = False
        try:
            self.manifest_raw = self.read('manifest.json', capture=True, maximum=MAX_MANIFEST)
            self.manifest, self.allowed = manifest_plan(self.manifest_raw)
            state = os.stat('hybrid-state.bin',dir_fd=self.fd,follow_symlinks=False)
            regular(state)
            need(0 < state.st_size <= MAX_FILE, 'hybrid state absent/oversize')
            self.allowed['hybrid-state.bin'] = state.st_size
            need(set(os.listdir(self.fd)) == set(self.allowed), 'unlisted/missing source diagnostics')
        except BaseException:
            os.close(self.fd)
            raise

    def read(self, name, *, capture=False, maximum=MAX_FILE, update=None):
        need(not self.failed, 'source reader latched')
        fd = None
        try:
            leaf(name)
            need(name not in self.files, 'second raw read forbidden')
            fd = os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=self.fd)
            before = regular(os.fstat(fd))
            need(0 < before[2] <= maximum, 'source file size outside bound')
            if hasattr(self,'allowed'):
                need(name in self.allowed and before[2] == self.allowed[name], 'file shape/length differs')
            os.fsync(fd)
            h = hashlib.sha256();total = 0;pieces = []
            while True:
                block = os.read(fd,CHUNK)
                if not block:break
                total += len(block)
                need(total <= before[2], 'source grew')
                h.update(block)
                if update:update(block)
                if capture:pieces.append(block)
            need(total == before[2] and regular(os.fstat(fd)) == before and
                 regular(os.stat(name,dir_fd=self.fd,follow_symlinks=False)) == before, 'source changed/truncated')
            os.posix_fadvise(fd,0,0,os.POSIX_FADV_DONTNEED)
            self.advice_calls += 1
            need(regular(os.fstat(fd)) == before, 'source changed after cache advice')
            self.read_bytes += total
            self.files[name] = dict(bytes=total,sha256=h.hexdigest())
            self.signatures[name] = before
            return b''.join(pieces) if capture else self.files[name]
        except BaseException:
            self.failed = True
            raise
        finally:
            if fd is not None:os.close(fd)

    def verify(self):
        need(not self.failed and set(self.files) == set(self.allowed) == set(os.listdir(self.fd)),
             'incomplete source consumption')
        for name, pin in self.signatures.items():
            need(regular(os.stat(name,dir_fd=self.fd,follow_symlinks=False)) == pin, 'source replaced after read')

    def close(self):os.close(self.fd)


class HashWriter:
    """Sequential ZIP sink: hash while writing, no reread of the completed archive."""
    def __init__(self,path):
        self.parent = directory(Path(path).parent)
        self.fd = None
        try:
            self.fd = os.open(leaf(Path(path).name),os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,
                              0o600,dir_fd=self.parent)
            self.h = hashlib.sha256();self.size = 0;self.advised = 0;self.advice_calls = 0
            os.fsync(self.parent)
        except BaseException:
            if self.fd is not None:os.close(self.fd)
            os.close(self.parent)
            raise

    def tell(self):return self.size
    def seek(self,*args):raise io.UnsupportedOperation('sequential hashing sink')
    def flush(self):os.fsync(self.fd)
    def write(self,data):
        need(self.size+len(data) <= MAX_ARCHIVE, 'archive byte budget exceeded')
        pending = memoryview(data)
        while pending:
            n = os.write(self.fd,pending)
            need(n > 0,'archive short write without progress')
            pending = pending[n:]
        self.h.update(data);self.size += len(data)
        if self.size-self.advised >= 16*CHUNK:
            self.flush()
            end = self.size//os.sysconf('SC_PAGE_SIZE')*os.sysconf('SC_PAGE_SIZE')
            if end > self.advised:
                os.posix_fadvise(self.fd,self.advised,end-self.advised,os.POSIX_FADV_DONTNEED)
                self.advised=end;self.advice_calls+=1
        return len(data)
    def close(self):
        os.close(self.fd);os.close(self.parent)


def zip_info(name):
    info=zipfile.ZipInfo(name,(2026,10,25,0,0,0))
    info.create_system=3
    info.external_attr=(stat.S_IFREG|0o600)<<16
    info.compress_type=zipfile.ZIP_DEFLATED
    return info


def export_pc(paths,archive):
    need(platform.machine().lower() in ('x86_64','amd64') and os.name=='posix',
         'BOARD exporter unbound: PC-only rehearsal permitted')
    sources={}
    writer=None
    try:
        for name in CASES:sources[name]=DirectoryCase(paths[name])
        total=sum(sum(s.allowed.values()) for s in sources.values())
        count=sum(len(s.allowed) for s in sources.values())
        need(count<=MAX_FILES and total<=MAX_TOTAL,'diagnostic transfer budget exceeded')
        writer=HashWriter(archive)
        index={}
        with zipfile.ZipFile(writer,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1) as z:
            for case,source in sources.items():
                z.writestr(zip_info(case+'/manifest.json'),source.manifest_raw)
                for name in source.allowed:
                    if name=='manifest.json':continue
                    with z.open(zip_info(case+'/'+name),'w',force_zip64=True) as dest:
                        source.read(name,update=dest.write)
                source.verify()
                index.update({case+'/'+n:row for n,row in source.files.items()})
            handoff=dict(schema='FULL_DIAGNOSTIC_HANDOFF_PC_V1',scope='24_LAYER_MLP_FULL_RAW_BYTES',
                         domain='PC_EXPORT_REHEARSAL_NOT_BOARD_RELEASE',files=index,
                         source_read_passes_per_file=1,advice_is_not_recovery_proof=True)
            payload=json.dumps(handoff,sort_keys=True,separators=(',',':')).encode()
            need(len(payload)<=MAX_INDEX,'handoff index exceeds bound')
            z.writestr(zip_info('HANDOFF.json'),payload)
        writer.flush()
        return dict(status='PC_EXPORT_COMPLETE_NOT_BOARD_AUTHORIZED',archive=str(archive),
            archive_sha256=writer.h.hexdigest(),archive_bytes=writer.size,raw_files=count,raw_bytes=total,
            source_read_passes_per_file=1,archive_hash_pass='DURING_WRITE_NO_REREAD',
            source_advice_calls=sum(s.advice_calls for s in sources.values()),archive_advice_calls=writer.advice_calls,
            full_originals_retained=True,BOARD='NOT_TESTED',CMA_recovery='NOT_TESTED')
    finally:
        for source in sources.values():source.close()
        if writer:writer.close()


class ArchiveSource:
    def __init__(self,path,expected_sha):
        self.parent=None;self.fd=None;self.z=None;self.stream=None
        self.path=Path(path);self.files={}
        try:
            self.parent=directory(Path(path).parent)
            self.fd=os.open(leaf(Path(path).name),os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=self.parent)
            self.pin=regular(os.fstat(self.fd))
            need(0 < self.pin[2] <= MAX_ARCHIVE,'archive exceeds bound')
            self.stream=os.fdopen(os.dup(self.fd),'rb')
            h=hashlib.sha256()
            for block in iter(lambda:self.stream.read(CHUNK),b''):h.update(block)
            need(h.hexdigest()==expected_sha,'archive checksum differs from trusted export receipt')
            self.stream.seek(0);self.z=zipfile.ZipFile(self.stream)
            infos=self.z.infolist();names=[i.filename for i in infos]
            need(len(names)==len(set(names)) and len(names)<=MAX_FILES+1,'duplicate/excess archive members')
            total=0
            for info in infos:
                name=PurePosixPath(info.filename)
                need(not name.is_absolute() and '..' not in name.parts and '\\' not in info.filename and
                     ':' not in info.filename and not info.is_dir() and
                     stat.S_IFMT(info.external_attr>>16) in (0,stat.S_IFREG), 'unsafe archive member')
                if info.filename=='HANDOFF.json':need(info.file_size<=MAX_INDEX,'handoff index too large')
                else:
                    need(len(name.parts)==2 and name.parts[0] in CASES,'unknown archive scope')
                    leaf(name.parts[1]);need(0<info.file_size<=MAX_FILE,'archive member size exceeds bound')
                    total+=info.file_size
            need(total<=MAX_TOTAL and names.count('HANDOFF.json')==1,'archive scope/budget differs')
            self.handoff=json.loads(self.z.read('HANDOFF.json'))
            need(self.handoff.get('schema')=='FULL_DIAGNOSTIC_HANDOFF_PC_V1','unknown handoff schema')
            self.expected=self.handoff['files']
            need(set(self.expected)==set(names)-{'HANDOFF.json'},'missing/unlisted raw archive member')
        except BaseException:
            self.close()
            raise

    def read(self,case,name,*,capture=False,update=None):
        full=case+'/'+leaf(name)
        need(full in self.expected and full not in self.files,'unknown/repeated raw read')
        pin=self.expected[full]
        need(type(pin.get('bytes')) is int and pin['bytes']==self.z.getinfo(full).file_size,
             'raw size/header mismatch')
        if capture:need(pin['bytes']<=MAX_MANIFEST,'manifest too large to capture')
        h=hashlib.sha256();total=0;parts=[]
        with self.z.open(full) as stream:
            while True:
                block=stream.read(CHUNK)
                if not block:break
                total+=len(block);need(total<=pin['bytes'],'raw size overflow')
                h.update(block)
                if update:update(block)
                if capture:parts.append(block)
        need(total==pin['bytes'] and h.hexdigest()==pin['sha256'],'raw byte checksum mismatch')
        self.files[full]=dict(bytes=total,sha256=h.hexdigest())
        return b''.join(parts) if capture else self.files[full]

    def verify(self):
        need(set(self.files)==set(self.expected),'not all raw bytes consumed')
        need(regular(os.fstat(self.fd))==self.pin and
             regular(os.stat(self.path.name,dir_fd=self.parent,follow_symlinks=False))==self.pin,
             'archive changed while verifying')

    def close(self):
        if getattr(self,'z',None):self.z.close()
        if getattr(self,'stream',None):self.stream.close()
        if getattr(self,'fd',None) is not None:os.close(self.fd);self.fd=None
        if getattr(self,'parent',None) is not None:os.close(self.parent);self.parent=None


class Numerical:
    def __init__(self):
        self.projections={};self.logits={};self.state=None;self.records=0;self.shapes={}
    def scan(self,source,case):
        raw=source.read(case,'manifest.json',capture=True)
        manifest,allowed=manifest_plan(raw)
        expected_names={n.split('/',1)[1] for n in source.expected if n.startswith(case+'/')}
        need(expected_names==set(allowed)|{'hybrid-state.bin'},'manifest/raw inventory differs')
        need(0<source.expected[case+'/hybrid-state.bin']['bytes']<=MAX_FILE,'state size outside bound')
        for row in manifest['projections']:
            shape=(row['K'],row['N'])
            need(self.shapes.setdefault(row['id'],shape)==shape,'projection shape changed across chunks')
            for kind in ('input','output'):
                key=str((row['id'],kind))
                digest=self.projections.setdefault(key,hashlib.sha256())
                result=source.read(case,row[kind],update=digest.update)
                need(result['bytes']==allowed[row[kind]],'raw shape bytes mismatch')
            self.records+=1
        for row in manifest['logits']:
            key=str(row['position']);need(key not in self.logits,'duplicate prefix/suffix logit position')
            value=source.read(case,row['file'])
            need(value['bytes']==LOGITS_BYTES,'logits bytes mismatch')
            self.logits[key]=value['sha256']
        self.state=source.read(case,'hybrid-state.bin')['sha256']
    def compare(self,joined):
        need(set(self.shapes)==set(joined.shapes)==STREAM_IDS and self.shapes==joined.shapes,'projection coverage differs')
        positions={int(x) for x in self.logits}
        need(positions==set(range(max(positions)+1)),'full logits positions incomplete')
        a={k:h.hexdigest() for k,h in self.projections.items()}
        b={k:h.hexdigest() for k,h in joined.projections.items()}
        delta={k:[a.get(k),b.get(k)] for k in a.keys()|b.keys() if a.get(k)!=b.get(k)}
        logits={k:[self.logits.get(k),joined.logits.get(k)] for k in self.logits.keys()|joined.logits.keys()
                if self.logits.get(k)!=joined.logits.get(k)}
        return dict(equal=not delta and not logits and self.state==joined.state,
            projection_difference=delta,logits_difference=logits,prefill_state_equal=self.state==joined.state,
            projection_streams=len(a),full_logit_vectors=len(self.logits),reference_projection_records=self.records,
            actual_projection_records=joined.records,reference_projection_sha256=a,restored_projection_sha256=b,
            reference_logits_sha256=self.logits,restored_logits_sha256=joined.logits,
            reference_state_sha256=self.state,restored_state_sha256=joined.state)


def verify_archive(path,expected_sha):
    source=ArchiveSource(path,expected_sha)
    try:
        full,joined=Numerical(),Numerical()
        full.scan(source,'full');joined.scan(source,'warm');joined.scan(source,'hit')
        result=full.compare(joined);source.verify()
        need(result['equal'],'full-byte numerical comparison failed')
        return dict(status='PASS_PC_FULL_RAW_NUMERICAL_COMPARISON',comparison=result,
            raw_files=len(source.files),raw_bytes=sum(r['bytes'] for r in source.files.values()),
            decompressed_read_passes_per_raw_file=1,full_originals_retained_in_archive=True,
            archive_sha256=expected_sha,BOARD='NOT_TESTED',model_runs=0,PL_calls=0)
    finally:source.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['plan','export-pc','verify'])
    for name in CASES:parser.add_argument('--'+name,type=Path)
    parser.add_argument('--archive',type=Path)
    parser.add_argument('--sha256')
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    try:
        if args.action=='verify':result=verify_archive(args.archive,args.sha256)
        else:
            paths={name:getattr(args,name) for name in CASES}
            need(all(paths.values()),'all three completed case directories required')
            if args.action=='export-pc':result=export_pc(paths,args.archive)
            else:
                sources={}
                try:
                    for name,path in paths.items():sources[name]=DirectoryCase(path)
                    result=dict(status='PLAN_ONLY_NO_RAW_READ',files=sum(len(s.allowed) for s in sources.values()),
                        raw_bytes=sum(sum(s.allowed.values()) for s in sources.values()),BOARD='NOT_TESTED')
                finally:
                    for source in sources.values():source.close()
        payload=result
    except BaseException as exc:
        payload=dict(status='FAIL_LATCHED_NO_RETRY',reason=type(exc).__name__+': '+str(exc),BOARD='NOT_TESTED')
        with args.report.open('x',encoding='utf-8') as f:json.dump(payload,f,indent=2);f.write('\n')
        raise
    with args.report.open('x',encoding='utf-8') as f:json.dump(payload,f,indent=2);f.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k!='comparison'},indent=2))


if __name__=='__main__':main()
