"""PC regressions: wrong ownership and archive collisions preserve original evidence."""
import copy,errno,json,tempfile
from pathlib import Path
from tt10_01_stale_lease import BOOT,OLD_BOOT,MACHINE,archive_noreplace,validate_lease
lease=dict(schema='A12_MODEL_LEASE_V1',owner='A',scope='all',window='a12-tt10-01-20261024-v1',
           identity=MACHINE+':'+OLD_BOOT,pid=167484,owner_start_ticks=5216275)
validate_lease(lease,BOOT);checks=1
for key,value in [('owner','B'),('identity',MACHINE+':'+BOOT),('pid',167485),
                  ('owner_start_ticks',5216276),('window','another-window')]:
    bad=copy.deepcopy(lease);bad[key]=value
    try:validate_lease(bad,BOOT)
    except AssertionError:checks+=1
    else:raise AssertionError(key)
try:validate_lease(lease,OLD_BOOT)
except AssertionError:checks+=1
else:raise AssertionError('Current live boot was treated as stale')
with tempfile.TemporaryDirectory(prefix='tt10-stale-lease-') as folder:
    root=Path(folder);source=root/'active';source.mkdir();raw=b'original-failed-lease\n'
    (source/'lease.json').write_bytes(raw);dest=root/'history';dest.mkdir();(dest/'keep').write_bytes(b'protected')
    try:archive_noreplace(source,dest)
    except OSError as exc:assert exc.errno==errno.EEXIST;checks+=1
    else:raise AssertionError('Archive overwritten')
    assert (source/'lease.json').read_bytes()==raw and (dest/'keep').read_bytes()==b'protected'
    target=root/'fresh-history';inode=(source/'lease.json').stat().st_ino
    archive_noreplace(source,target)
    assert not source.exists() and (target/'lease.json').read_bytes()==raw and (target/'lease.json').stat().st_ino==inode
    checks+=1
print(json.dumps(dict(status='PASS_PC_STALE_OWNER_AND_NO_CLOBBER',checks=checks,BOARD=False)))
