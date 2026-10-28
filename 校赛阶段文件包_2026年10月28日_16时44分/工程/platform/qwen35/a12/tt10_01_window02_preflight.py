"""Fresh authorized window02 inventory and real nonblocking lock probe; no compute."""
import base64,contextlib,fcntl,gzip,hashlib,io,json,os,stat,subprocess,sys,time
from pathlib import Path
PREFLIGHT_B64=None
MACHINE='ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec'
BOOT='1d0499ab-f1f9-438c-969a-3e701a0d806f'
WINDOW='a12-tt10-01-20261025-v2'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    assert os.geteuid()==0 and sha('/etc/machine-id')==MACHINE and os.uname().release=='6.8.12-a10irq2'
    assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==BOOT
    stream=io.StringIO()
    with contextlib.redirect_stdout(stream):exec(compile(gzip.decompress(base64.b64decode(PREFLIGHT_B64)),'exact_existing_inventory','exec'),{'__name__':'__main__'})
    r=json.loads(stream.getvalue());r.update(scope='TT10_01_WINDOW02_FRESH_BASELINE_AND_LOCK_PROBE',lock_probe=[],lock_probe_released=False)
    r['namespace']={p:os.path.lexists(p) for p in ('/var/lib/kv260-a12/tt10-01-20261025-v2',
        '/var/lock/kv260-a1/history/'+WINDOW,'/lib/firmware/xilinx/'+WINDOW)}
    r['boot_and_driver_pins']={}
    from isolated_idle_policy import BOOT_FILES
    pins=dict(BOOT_FILES)
    pins['/usr/lib/modules/6.8.12-a10irq2/extra/zocl.ko']='38992846680c0ddbdad7a05f6506b66488473a96c52975fa35a126b8401344f8'
    for name,pin in pins.items():r['boot_and_driver_pins'][name]=dict(sha256=sha(name),matches=sha(name)==pin)
    mem={line.split(':')[0]:int(line.split()[1]) for line in r['memory_raw'].splitlines()}
    r['resource_review']=dict(MemAvailable_kib=mem['MemAvailable'],CmaFree_kib=mem['CmaFree'],
        required_initial_MemAvailable_kib=1114112+196608,original_remaining_CmaFree_kib=98304,
        planned_explicit_BO_bytes=140591104,disk_free_bytes=__import__('shutil').disk_usage('/var/lib/kv260-a12').free)
    fds=[]
    try:
        assert r['scans'][-1]['no_users_gate'] and not r['active_lease_exists'] and not any(r['locks'].values())
        assert not any(r['namespace'].values()) and not r['module_present']
        assert r['gdm_state']=='active' and r['overlays']=={'k26-starter-kits_image_1':'applied'} and r['fpga_state']=='operating'
        assert all(v['matches'] for v in r['boot_and_driver_pins'].values()) and all(v['matches'] for v in r['library_pins'].values())
        assert mem['MemAvailable']>=1114112+196608 and mem['CmaFree']>=98304
        assert r['resource_review']['disk_free_bytes']>=2147483648
        assert r['temperatures_mC'] and all(0<t<55000 for t in r['temperatures_mC'])
        for name in ('/var/lock/kv260-a1/a12-finalize-coordinator.lock','/var/lock/kv260-a1/deployment.lock','/run/lock/patient-qwen-linear.lock'):
            p=Path(name);s=p.lstat()
            assert stat.S_ISREG(s.st_mode) and s.st_uid==0 and not s.st_mode&0o022 and not p.is_symlink()
            fd=os.open(p,os.O_RDWR|os.O_NOFOLLOW);fds.append(fd)
            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            assert os.fstat(fd).st_ino==s.st_ino and os.fstat(fd).st_dev==s.st_dev
            info=Path('/proc/self/fdinfo',str(fd)).read_text();assert 'FLOCK' in info and 'WRITE' in info
            r['lock_probe'].append(dict(path=name,inode=s.st_ino,device=s.st_dev,pid=os.getpid(),fdinfo=info,exclusive_acquired=True))
        assert not Path('/var/lock/kv260-a1/active').exists()
        r['probe_status']='PASS_CURRENT_IDENTITY_RESOURCES_NAMESPACE_AND_DUAL_LOCKS'
    except Exception as exc:
        r['probe_status']='REFUSED_NO_COMPUTE';r['error']=type(exc).__name__+': '+str(exc)
    finally:
        for fd in reversed(fds):os.close(fd)
        r['lock_probe_released']=True
    assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==BOOT
    r['finished_monotonic_ns']=time.monotonic_ns()
    print(json.dumps(r),flush=True)
    return 0 if r['probe_status'].startswith('PASS_') else 2
if __name__=='__main__':raise SystemExit(main())
