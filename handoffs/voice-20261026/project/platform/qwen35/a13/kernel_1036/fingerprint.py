"""Read-only full header-tree digest, shared by board export and PC check."""
import hashlib
import json
import os
from pathlib import Path
import stat

NAMES=('linux-headers-6.8.0-1036-xilinx','linux-xilinx-headers-6.8.0-1036')


def fingerprint(root):
    root=Path(root);rows=[];total=0
    for name in NAMES:
        directory=root/name
        assert directory.is_dir() and not directory.is_symlink()
        for p in sorted(directory.rglob('*')):
            info=p.lstat();relative=p.relative_to(root).as_posix()
            if stat.S_ISDIR(info.st_mode):continue
            assert len(rows)<50000
            row={'path':relative,'mode':stat.S_IMODE(info.st_mode)}
            if stat.S_ISLNK(info.st_mode):row.update(kind='symlink',target=os.readlink(p))
            else:
                assert stat.S_ISREG(info.st_mode);total+=info.st_size;assert total<268435456
                digest=hashlib.sha256()
                with p.open('rb') as stream:
                    for raw in iter(lambda:stream.read(1048576),b''):digest.update(raw)
                row.update(kind='file',bytes=info.st_size,sha256=digest.hexdigest())
            rows.append(row)
    canonical=json.dumps(rows,sort_keys=True,separators=(',',':')).encode()
    return {'schema':'A13_MATCHED_1036_HEADER_TREE_V1','roots':list(NAMES),'files':len(rows),
        'file_bytes':total,'tree_sha256':hashlib.sha256(canonical).hexdigest()}


def board_main():
    assert os.geteuid()==0 and os.uname().machine=='aarch64' and os.uname().release=='6.8.0-1036-xilinx'
    assert hashlib.sha256(Path('/etc/machine-id').read_bytes()).hexdigest()=='ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec'
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    assert boot=='c31cdf7b-bc10-40b0-b459-22878582062d'
    result=fingerprint('/usr/src');result.update(boot_id=boot,board_writes=0,hardware_operations=0)
    result['selected_hashes']={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in
        [Path('/usr/src')/NAMES[0]/name for name in
         ('.config','Module.symvers','include/generated/autoconf.h','include/generated/utsrelease.h','include/generated/compile.h')] if p.is_file()}
    assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==boot
    print(json.dumps(result),flush=True)
