"""Archive a proven prior-boot lease after authorized recovery; never compute."""
import ctypes,fcntl,hashlib,json,os,stat,subprocess,sys,time
from pathlib import Path
MACHINE='ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec'
BOOT='1d0499ab-f1f9-438c-969a-3e701a0d806f'
OLD_BOOT='86e4938b-0f65-4166-9237-c547b67e1451'
LEASE_SHA='568d525f398a30b931f1767f4eec6ac19303814e781b1602d5756062f2a248e7'
BASELINE_SHA='415ab969384f5bc81afef819e192f4e90672821e57117664791c5a957c3e16d9'
ROOT=Path('/var/lib/kv260-a12/tt10-01-20261024-v1')
CENTRAL=Path('/var/lock/kv260-a1')
OUT=Path('/var/lib/kv260-a12/recovery-20261025-stale-lease-v1')
ARCHIVE=CENTRAL/'history/a12-tt10-01-20261024-v1-priorboot-abnormal-20261025-v1'
PINS={'/boot/firmware/image.fit':'23a0ad7516d6f67f248f952653324c18a9c7d1db31fdf27a003f021adf0ca61e',
 '/boot/firmware/boot.scr.uimg':'f1eb9e841e100a64f59eed77bccd73396297ce93bbcb6ce4916a7b516793c685',
 '/boot/firmware/a10-candidate-irq2-20261021.fit':'e60d7f49033ef8efbd2396fafbe94a3bc684a478d5f5e31676626d1bc5f6ae2b',
 '/usr/lib/modules/6.8.12-a10irq2/extra/zocl.ko':'38992846680c0ddbdad7a05f6506b66488473a96c52975fa35a126b8401344f8',
 '/usr/lib/libxrt_core.so.2.18.0':'88ad9c1c0c4aba93573436a81b09bbb06ace1d6f1b1dc5285ff987143c1d32d4',
 '/usr/lib/libxrt_coreutil.so.2.18.0':'398f44b57956d19876fc2b547689898b8be51f809822c576ca26f7813c841563'}
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()
def validate_lease(lease,current_boot):
    assert current_boot==BOOT and current_boot!=OLD_BOOT
    assert lease['schema']=='A12_MODEL_LEASE_V1' and lease['owner']=='A' and lease['scope']=='all'
    assert lease['window']=='a12-tt10-01-20261024-v1'
    assert lease['identity']==MACHINE+':'+OLD_BOOT
    assert type(lease['pid']) is int and lease['pid']==167484
    assert lease['owner_start_ticks']==5216275
def archive_noreplace(source,dest):
    # Linux libc refuses an existing destination atomically; no overwrite fallback.
    libc=ctypes.CDLL(None,use_errno=True)
    fun=libc.renameat2
    fun.argtypes=(ctypes.c_int,ctypes.c_char_p,ctypes.c_int,ctypes.c_char_p,ctypes.c_uint)
    fun.restype=ctypes.c_int
    rc=fun(-100,os.fsencode(source),-100,os.fsencode(dest),1)
    if rc:raise OSError(ctypes.get_errno(),os.strerror(ctypes.get_errno()))
def trusted(p,*,directory=False):
    s=Path(p).lstat()
    assert s.st_uid==0 and not stat.S_ISLNK(s.st_mode) and not s.st_mode&0o022,str(p)
    assert stat.S_ISDIR(s.st_mode) if directory else stat.S_ISREG(s.st_mode)
    return s
def save(name,obj):
    with (OUT/name).open('x') as f:json.dump(obj,f);f.write('\n');f.flush();os.fsync(f.fileno())
def main():
    assert os.geteuid()==0 and os.uname().release=='6.8.12-a10irq2' and sha('/etc/machine-id')==MACHINE
    assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==BOOT
    assert not OUT.exists() and not os.path.lexists(ARCHIVE)
    trusted(CENTRAL,directory=True);trusted(CENTRAL/'history',directory=True)
    active=CENTRAL/'active';trusted(active,directory=True)
    assert [p.name for p in active.iterdir()]==['lease.json']
    trusted(active/'lease.json');assert sha(active/'lease.json')==LEASE_SHA
    lease=json.loads((active/'lease.json').read_text());validate_lease(lease,BOOT)
    assert sha(ROOT/'control/support/accelerator_release_gate_v2.py')=='1db0bfbac7623309a922c0a56978b0bd3d519a68904884d86d578ef872363668'
    assert sha(ROOT/'control/support/kernel_log_gate.py')=='2a9e5bb2a0cae4454277df1118103754ac043298cf729f98a1c9e4fd8a1ef396'
    sys.path.insert(0,str(ROOT/'control/support'))
    from accelerator_release_gate_v2 import collect,require_no_users
    from kernel_log_gate import KernelLogGate
    OUT.mkdir(mode=0o700);fds=[]
    try:
        lock_records=[]
        for name,create in ((CENTRAL/'a12-finalize-coordinator.lock',False),(CENTRAL/'deployment.lock',False),
                             (Path('/run/lock/patient-qwen-linear.lock'),True)):
            fd=os.open(name,os.O_RDWR|os.O_NOFOLLOW|(os.O_CREAT|os.O_EXCL if create else 0),0o600);fds.append(fd)
            st=os.fstat(fd);assert stat.S_ISREG(st.st_mode) and st.st_uid==0 and not st.st_mode&0o022 and st.st_nlink==1
            assert name.lstat().st_ino==st.st_ino and name.lstat().st_dev==st.st_dev
            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            lock_records.append(dict(path=str(name),inode=st.st_ino,device=st.st_dev,fd=fd,owner_pid=os.getpid()))
        raw=subprocess.check_output(['dmesg','--raw']).decode()
        assert hashlib.sha256(raw.encode()).hexdigest()==BASELINE_SHA,'Recovery-only reviewed baseline changed'
        gate=KernelLogGate();assert gate.observe(BOOT,raw,BASELINE_SHA)['allowed']
        save('baseline-review.json',dict(raw_sha256=BASELINE_SHA,scope='RECOVERY_ONLY_NO_COMPUTE',
             baseline_limitations_still_open=True,comparison='Original TT10-01 preflight: only CPU3->CPU1 and one x22 register differ; all other startup diagnostic messages already present'))
        def gates(lease_path):
            assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==BOOT
            assert sha(lease_path)==LEASE_SHA
            assert not Path('/sys/module/zocl').exists() and not Path('/state.txt').exists()
            assert not Path('/lib/firmware/xilinx/a12-tt10-01-20261024-v1').exists()
            overlays={p.name:(p/'status').read_text().strip() for p in Path('/sys/kernel/config/device-tree/overlays').iterdir() if p.is_dir()}
            assert overlays=={'k26-starter-kits_image_1':'applied'}
            assert Path('/sys/class/fpga_manager/fpga0/state').read_text().strip()=='operating'
            assert subprocess.check_output(['systemctl','is-active','gdm.service']).strip()==b'active'
            assert all(sha(name)==pin for name,pin in PINS.items())
            for p in Path('/proc').iterdir():
                if not p.name.isdecimal():continue
                argv=(p/'cmdline').read_bytes().split(b'\0')
                assert not any(str(ROOT).encode() in a for a in argv),'Old window process remains'
            assert not any(Path('/proc',str(pid)).exists() for pid in (167484,167575))
            scan=collect(allow_ps_display=True)
            k=gate.observe(BOOT,subprocess.check_output(['dmesg','--raw']).decode())
            require_no_users(scan,k['allowed'],boot_id=BOOT)
            return dict(scan=scan,kernel_gate=k,default_overlay=overlays,GDM='active',ZOCL='absent',locks=lock_records,
                        observed_monotonic_ns=time.monotonic_ns())
        before=gates(active/'lease.json');save('before.json',before)
        assert sha(active/'lease.json')==LEASE_SHA and not os.path.lexists(ARCHIVE)
        save('archive-reserved.json',dict(source=str(active),archive=str(ARCHIVE),lease_sha256=LEASE_SHA,
             method='renameat2_RENAME_NOREPLACE',old_manager_exit_code=None,old_worker_exit_code=None,normal_exit_claimed=False))
        archive_noreplace(active,ARCHIVE)
        # Persist directory movement before reporting. On any failure keep every artifact.
        for directory in (CENTRAL,CENTRAL/'history'):
            fd=os.open(directory,os.O_RDONLY|os.O_DIRECTORY)
            try:os.fsync(fd)
            finally:os.close(fd)
        after=gates(ARCHIVE/'lease.json');assert not os.path.lexists(active)
        result=dict(status='PRIOR_BOOT_FAILED_WINDOW_ARCHIVED_RECOVERY_ONLY',archive=str(ARCHIVE),lease_sha256=LEASE_SHA,
            old_boot=OLD_BOOT,current_boot=BOOT,old_manager_exit_code=None,old_worker_exit_code=None,
            old_window_compute_status='FAILED_CPU_RESERVE_GATE_PRESERVED',normal_old_owner_exit=False,
            signals=0,pl_loads=0,compute_runs=0,postcheck=after,locks_released_on_process_exit=True)
        save('result.json',result);print(json.dumps(result),flush=True)
    except Exception as exc:
        save('stopped.json',dict(error=type(exc).__name__+': '+str(exc),active_exists=active.exists(),archive_exists=ARCHIVE.exists(),retry=False))
        raise
    finally:
        for fd in reversed(fds):os.close(fd)
if __name__=='__main__':main()
