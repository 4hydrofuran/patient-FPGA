"""Fixed cleanup transport helpers; no native accelerator imports or compute.

Staging creates five reviewed files in one NEW private directory only. Readback
does not open devices, acquire locks, signal processes or invoke mutations.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import time
import zlib

INSTALL = Path('/var/lib/kv260-a11/cleanup-v3-20261023')
ROOT = Path('/var/lib/kv260-a11/a11-mlp-20261023-v1')
BOOT = '8422f92f-d01f-4849-ad19-6e66b640a9ad'
MACHINE = 'ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec'
PIN = 'e60bba1d6dccbaa8acd3c60e962630e2d7041463f2a478cc7a75bbd6832e9611'
ORIGINAL = '3b3c46700f92565839abda962e07e557018b8fd1be9e7846613ff46ecf89f11c'
NAMES = {'candidate.json','cleanup_board_v3.py','cleanup_controller_v3.py',
         'cleanup_control_v3.py','reviewed-kernel.raw.txt'}
READY = '__A11_CLEANUP_V3_PAYLOAD_READY__'


def sha(raw): return hashlib.sha256(raw).hexdigest()


def identity():
    assert os.geteuid() == 0 and os.uname().machine == 'aarch64'
    assert sha(Path('/etc/machine-id').read_bytes()) == MACHINE
    assert Path('/proc/sys/kernel/random/boot_id').read_text().strip() == BOOT
    assert os.uname().release == '6.8.12-a10irq2'


def validate_payload(payload):
    assert type(payload) is dict and set(payload) == NAMES
    files = {n: base64.b64decode(v, validate=True) for n, v in payload.items()}
    assert sum(map(len, files.values())) < 1024 * 1024
    assert sha(files['candidate.json']) == PIN
    manifest = json.loads(files['candidate.json'])
    assert set(manifest['files']) == NAMES - {'candidate.json'}
    for name, entry in manifest['files'].items():
        assert len(files[name]) == entry['bytes'] and sha(files[name]) == entry['sha256']
    return files


def trusted_directory(path):
    info = path.lstat()
    assert stat.S_ISDIR(info.st_mode) and info.st_uid == 0 and not info.st_mode & 0o022


def stage():
    identity()
    for path in reversed(INSTALL.parent.parents): trusted_directory(path)
    trusted_directory(INSTALL.parent)
    assert not os.path.lexists(INSTALL), 'existing directory: do not overwrite or rerun'
    print(READY, flush=True)
    raw = sys.stdin.buffer.readline(1500000)
    assert raw.endswith(b'\n') and len(raw) < 1500000
    files = validate_payload(json.loads(raw))  # All data checked before mkdir.
    os.umask(0o077)
    INSTALL.mkdir(mode=0o700)
    for name in sorted(files):
        with (INSTALL/name).open('xb') as f:
            f.write(files[name]); f.flush(); os.fsync(f.fileno())
        assert sha((INSTALL/name).read_bytes()) == sha(files[name])
    fd = os.open(INSTALL, os.O_DIRECTORY | os.O_RDONLY)
    try: os.fsync(fd)
    finally: os.close(fd)
    print(json.dumps(dict(status='STAGED_HASH_VERIFIED_NO_EXECUTION', files={
        n: dict(bytes=len(b), sha256=sha(b)) for n,b in files.items()}, hardware_commands=0)), flush=True)


def pack(raw):
    assert len(raw) < 64*1024*1024
    return dict(bytes=len(raw), sha256=sha(raw), zlib_base64=base64.b64encode(zlib.compress(raw)).decode())


def optional_digest(path):
    # Match the frozen A10/A11 snapshot: absent VART config is null, not failure.
    return sha(path.read_bytes()) if path.exists() else None


def readback():
    identity()
    assert sha((ROOT/'manifest.json').read_bytes()) == ORIGINAL
    manifest = json.loads((ROOT/'manifest.json').read_bytes())
    imports = ('accelerator_release_gate_v2.py','isolated_idle_policy.py')
    for name in imports:
        assert sha((ROOT/name).read_bytes()) == manifest['files'][name]['sha256']
    sys.path.insert(0,str(ROOT))
    from accelerator_release_gate_v2 import collect
    from isolated_idle_policy import LOCKS, BOOT_FILES, LIBRARIES
    files = {}
    for prefix, directory, names in (
        ('v3', INSTALL/'state', ('lifecycle.jsonl','result.json')),
        ('original', ROOT, ('lifecycle.jsonl','worker.stdout.jsonl','worker.stderr.txt',
                           'STOP.json','worker-result.json','mlp-receipt.json')),
        ('old_cleanup', ROOT/'recovery-continuation-20261023-v1', ('lifecycle.jsonl','result.json')),
    ):
        for name in names:
            p=directory/name
            files[prefix+'/'+name] = pack(p.read_bytes()) if p.is_file() else None
    central=Path('/var/lock/kv260-a1')
    for name,p in (
        ('active-lease.json',central/'active/lease.json'),
        ('archived-lease.json',central/'history/a11-mlp-20261023-v1-aborted-open/lease.json'),
    ): files[name] = pack(p.read_bytes()) if p.is_file() else None
    # No flock acquisition: identify exact lock inodes in the kernel lock table.
    locktext=Path('/proc/locks').read_text()
    lock_rows={}
    for p in LOCKS:
        info=p.stat()
        wanted=(os.major(info.st_dev),os.minor(info.st_dev),info.st_ino)
        rows=[]
        for line in locktext.splitlines():
            fields=line.split()
            for field in fields:
                if field.count(':')==2:
                    try:
                        a,b,c=field.split(':'); key=(int(a,16),int(b,16),int(c))
                    except ValueError: continue
                    if key==wanted: rows.append(line)
        lock_rows[str(p)]=rows
    pids={3202,3308,5322,6174}
    lifecycle=INSTALL/'state/lifecycle.jsonl'
    if lifecycle.is_file():
        rows=[json.loads(line) for line in lifecycle.read_text().splitlines()]
        pids.update(row['pid'] for row in rows if row.get('event')=='RECOVERY_RESERVED')
    processes={}
    for pid in sorted(pids):
        p=Path('/proc')/str(pid)
        if not p.exists(): processes[str(pid)]=None; continue
        try:
            processes[str(pid)]=dict(stat=(p/'stat').read_text(),status=(p/'status').read_text(),
                maps=(p/'maps').read_text(),cmdline=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(),
                children=(p/'task'/str(pid)/'children').read_text(),
                fds={q.name:os.readlink(q) for q in (p/'fd').iterdir()})
        except FileNotFoundError as exc: processes[str(pid)]=dict(observation_incomplete=str(exc))
    klog=subprocess.run(['dmesg','--raw'],capture_output=True,timeout=3)
    assert klog.returncode==0 and not klog.stderr
    gdm=subprocess.run(['systemctl','is-active','gdm.service'],capture_output=True,timeout=3)
    pins={p:sha(Path(p).read_bytes()) for p in (*BOOT_FILES,*LIBRARIES,
        '/lib/firmware/xilinx/k26-starter-kits/k26_starter_kits.bit.bin',
        '/lib/firmware/xilinx/k26-starter-kits/k26_starter_kits.dtbo')}
    ref=Path('/sys/module/zocl/refcnt')
    scan=collect(allow_ps_display=True)
    result=dict(schema='A11_CLEANUP_V3_INDEPENDENT_READBACK',boot_id=BOOT,
        kernel=os.uname().release,monotonic_ns=time.monotonic_ns(),files=files,
        kernel_log=pack(klog.stdout),scan=scan,processes=processes,locks=lock_rows,
        control_socket_present=os.path.lexists(INSTALL/'state/control.sock'),
        module_present=Path('/sys/module/zocl').exists(),module_refcount=ref.read_text().strip() if ref.exists() else None,
        overlays={p.name:(p/'status').read_text().strip() for p in Path('/sys/kernel/config/device-tree/overlays').iterdir() if p.is_dir()},
        render_nodes=[str(p) for p in Path('/dev/dri').glob('render*')],
        zocl_bound=[p.name for p in Path('/sys/bus/platform/devices').iterdir() if (p/'driver/module').exists() and (p/'driver/module').resolve().name=='zocl'],
        fpga_state=Path('/sys/class/fpga_manager/fpga0/state').read_text().strip(),
        gdm_state=gdm.stdout.decode().strip(),gdm_exit_code=gdm.returncode,
        temperatures_mC=[int(p.read_text()) for p in Path('/sys/class/hwmon').glob('hwmon*/temp*_input')],
        memory_raw=Path('/proc/meminfo').read_text(),pins=pins,
        default_firmware=Path('/etc/dfx-mgrd/default_firmware').read_text().strip(),
        vart_sha256=optional_digest(Path('/etc/vart.conf')),
        outputs=[p.name for p in (ROOT/'outputs').iterdir()],
        permits={p.name:sha(p.read_bytes()) for p in (ROOT/'permits').iterdir()},hardware_mutations=0)
    assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==BOOT
    print(json.dumps(result),flush=True)


if __name__=='__main__':
    assert len(sys.argv)==2 and sys.argv[1] in ('stage','readback')
    {'stage':stage,'readback':readback}[sys.argv[1]]()
