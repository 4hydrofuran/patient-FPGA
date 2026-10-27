"""Stage-aware A12 BO admission; RSS/PSS and CMA are separate views."""
import hashlib
import os
from pathlib import Path
import stat

MEM_FLOOR_KIB=1048576
CMA_FLOOR_KIB=32768
EXTRA_RESERVE_KIB=65536

def admission(memory,total_bo_bytes,*,already_charged_bo_bytes=0):
    if any(type(x) is not int or x<0 for x in (total_bo_bytes,already_charged_bo_bytes)):
        raise ValueError('invalid BO charge')
    if already_charged_bo_bytes>total_bo_bytes:raise ValueError('charged BO exceeds total')
    pending=total_bo_bytes-already_charged_bo_bytes;extra=(pending+1023)//1024
    values={k:memory[k] for k in ('MemAvailable','CmaFree')}
    if any(type(v) is not int or v<0 for v in values.values()):raise ValueError('invalid memory reading')
    available=values['MemAvailable']-extra;cma=values['CmaFree']-extra
    return dict(allowed=available>=MEM_FLOOR_KIB+EXTRA_RESERVE_KIB and cma>=CMA_FLOOR_KIB+EXTRA_RESERVE_KIB,
       memory_kib=values,total_bo_bytes=total_bo_bytes,already_charged_bo_bytes=already_charged_bo_bytes,
       pending_bo_bytes=pending,MemAvailable_after_pending_kib=available,CmaFree_after_pending_kib=cma,
       required_MemAvailable_kib=MEM_FLOOR_KIB+EXTRA_RESERVE_KIB,required_CmaFree_kib=CMA_FLOOR_KIB+EXTRA_RESERVE_KIB,
       accounting='Deduct only not-yet-allocated BO. Existing BO is already reflected in current memory. No RSS/PSS+CMA sum.')

def review_archive_cache(rows):
    """Only exact caller-pinned artifacts. Never scan, delete, drop_caches or touch model pages."""
    result=[]
    for row in rows:
        path=Path(row['path']);fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
        try:
            before=os.fstat(fd)
            if not stat.S_ISREG(before.st_mode) or before.st_size!=row['bytes']:
                raise RuntimeError('archive identity/size differs')
            digest=hashlib.sha256()
            while True:
                b=os.read(fd,1048576)
                if not b:break
                digest.update(b)
            if digest.hexdigest()!=row['sha256']:raise RuntimeError('archive bytes differ')
            current=os.fstat(fd)
            if (before.st_ino,before.st_size,before.st_mtime_ns)!=(current.st_ino,current.st_size,current.st_mtime_ns):
                raise RuntimeError('archive changed while verifying')
            os.fsync(fd);os.posix_fadvise(fd,0,0,os.POSIX_FADV_DONTNEED)
            after=os.fstat(fd)
            if (before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns):
                raise RuntimeError('archive identity changed')
            result.append(dict(row,hash_verified_before_advice=True,identity_size_mtime_unchanged=True,
               advice='FSYNC_AND_FADV_DONTNEED_ONLY',file_deleted=False))
        finally:os.close(fd)
    return result
