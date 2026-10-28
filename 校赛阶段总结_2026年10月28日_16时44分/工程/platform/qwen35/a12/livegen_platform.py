"""Bind existing original platform objects; no lease acquisition or Board entry."""
import ast
import importlib.util
import json
import hashlib
import os
from pathlib import Path
import sys
import time
from livegen_evidence import BUNDLE,bundle_pin,read,sha
from livegen_source import MutationInterlock,NodePins
from fresh_identity_io import FreshCheckedFile,pin as file_pin
from request_journal_audit import strict_json
from plm_journal import need
from plm_manager import ticks

MACHINE='ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec'
KERNEL='6.8.12-a10irq2'
LOCKS=(Path('/var/lock/kv260-a1/deployment.lock'),Path('/run/lock/patient-qwen-linear.lock'))
LEASE=Path('/var/lock/kv260-a1/active/lease.json')
_ORIGINAL=None

def original_bo_validator():
    need(__debug__,'original BO assertion policy requires unoptimized Python')
    p=bundle_pin('control/resource_probe_manager.py');text=p.read_text(encoding='utf-8')
    node=next(n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef) and n.name=='validate_bo')
    code='\n'.join(text.splitlines()[node.lineno-1:node.end_lineno]);scope={}
    exec(compile(code,str(p)+'#unaltered-validate-bo','exec'),scope);return scope['validate_bo']

def interlocked_platform(original):
    class Platform(original.Platform):
        def __init__(self,*args,window_id=None,**kwargs):
            self.generation_interlock=MutationInterlock();super().__init__(*args,**kwargs)
            if window_id is not None:
                import re
                need(type(window_id) is str and re.fullmatch(r'a12-[a-z0-9-]{1,80}',window_id),'fresh flat candidate window name required')
                self.package=window_id;self.target=Path('/lib/firmware/xilinx')/window_id
        def _generation_release_check(self):
            # Do NOT consume release_checked or a prior JSON scan as authority.
            original.Platform.no_users(self,module_loaded=Path('/sys/module/zocl').exists())
        def command(self,argv,state_changing=False):
            if state_changing:self.generation_interlock.before('command '+repr(argv),release_check=self._generation_release_check)
            return super().command(argv,state_changing)
        def service(self,action):
            self.generation_interlock.before('GDM '+str(action),release_check=self._generation_release_check)
            return super().service(action)
    return Platform

def load_original():
    # Explicit call only. Importing this module does not import/run the Board entry.
    need(os.name=='posix' and os.geteuid()==0 and os.uname().machine=='aarch64','Board adapter requires registered root ARM64; no PC override')
    return import_original_verified()

def import_original_verified():
    """Import-only audit on PC is allowed; no Original object is constructed."""
    global _ORIGINAL
    need(__debug__,'original gate assertions require unoptimized Python')
    if _ORIGINAL is not None:return _ORIGINAL
    from livegen_import import load
    module=load()
    module.InterlockedPlatform=interlocked_platform(module);_ORIGINAL=module;return module

def bounded_text(path):
    p=Path(path)
    with p.open('rb') as f:data=f.read(4097)
    need(0<len(data)<=4096,'generation attribute missing/oversize: '+str(p));return data.decode('utf-8').strip()

def bounded_sha(path):
    with Path(path).open('rb') as f:data=f.read(4097)
    need(0<len(data)<=4096,'generation identity missing/oversize');return hashlib.sha256(data).hexdigest()

def inherited_lock_proof(paths,fds,worker_pid,parent_pid):
    """Borrow proof only; never opens/acquires/unlocks either canonical lock."""
    import re
    import stat
    need(len(paths)==len(fds)==2,'both inherited device locks required')
    for path,fd in zip(paths,fds):
        a=Path(path).lstat();b=os.fstat(fd);child=Path('/proc',str(worker_pid),'fd',str(fd)).stat()
        need(stat.S_ISREG(a.st_mode) and (a.st_dev,a.st_ino)==(b.st_dev,b.st_ino)==(child.st_dev,child.st_ino),
            'native inherited canonical lock inode differs')
        for pid in (parent_pid,worker_pid):
            text=Path('/proc',str(pid),'fdinfo',str(fd)).read_text()
            need(re.search(r'(?m)^lock:\s+\d+:\s+FLOCK\s+ADVISORY\s+WRITE\s+'+str(parent_pid)+r'\s',text),
                'native/manager inherited FLOCK ownership differs')

class BoardPorts:
    domain='BOARD_LIVE_OWNER_SOURCE_V1'
    def __init__(self,owner,original):
        self.reader=None;self.nodes=None
        try:self._prepare(owner,original)
        except BaseException:
            self.close_observers();raise
    def _prepare(self,owner,original):
        # No constructor creates an Owner, touches a device, or obtains a lease.
        need(os.name=='posix' and os.geteuid()==0 and os.uname().machine=='aarch64' and os.uname().release==KERNEL,
            'Board source requires exact existing root ARM64 kernel')
        need(__debug__ and original is _ORIGINAL,'verified original module and unoptimized gate interpreter required')
        need(type(owner) is original.Owner and type(owner.platform) is original.InterlockedPlatform,'original Owner/interlocked Platform objects required')
        self.owner=owner;self.original=original;self.platform=owner.platform;self.expires=owner.expires
        self.boot=bounded_text('/proc/sys/kernel/random/boot_id');need(self.boot==owner.boot and bounded_sha('/etc/machine-id')==MACHINE,'registered Board/boot differs')
        need(not owner.finished and self.platform.owner is owner and self.platform.worker is None,'live pre-worker original owner required')
        original.Owner.owner_check(owner)
        need(tuple(Path(x) for x in original.Window.owner_check.__globals__['LOCKS'])==LOCKS and len(owner.locks)==2,'original canonical dual-lock policy differs')
        self.lease_sha256=owner.lease_hash;self.reader=FreshCheckedFile(LEASE,self.lease_sha256,max_bytes=16384,chunk=4096)
        lease=strict_json(LEASE.read_bytes());r=owner.review
        need(lease['schema']=='A12_MODEL_LEASE_V1' and lease['owner']=='A' and lease['compute_authorized'] is True and
            lease['pid']==os.getpid() and lease['owner_start_ticks']==ticks(os.getpid()) and lease['identity']==MACHINE+':'+self.boot and
            lease['expires_monotonic_ns']==owner.expires and lease['scope']==r['scope']=='all' and lease['window']==r['window_id']==self.platform.package and
            lease['max_runs']==r['max_runs']==5000 and lease['max_loads']==r['max_loads']==72 and
            lease['explicit_bo_budget_bytes']==r['explicit_bo_budget_bytes']==140591104,'original reviewed lease/budgets differ')
        # Original idle, topology and IRQ gates, before any native device/BO open.
        self.platform.no_users(module_loaded=True);self.platform.verify_irq_dt()
        snapshot=self.platform.snapshot('generation_source_before_worker');original.check_topology(snapshot,self.platform.package)
        self.preallocation_admission=original.admission(snapshot['memory_kib'],140591104)
        need(self.preallocation_admission['allowed'] is True,'original full BO preallocation admission refused')
        need(original.sha(self.platform.driver)==self.platform.driver_sha256=='388c45a0edefe221615d71ea948de00d0ef68190bdd8497b053dddf788f72b2c','driver artifact differs')
        self.profile=read(bundle_pin('config/profile.pending.json'))
        name=Path('/etc/xocl.txt');self.device_name=bounded_text(name).split()[0] if name.exists() else 'edge'
        if name.exists():original.trusted_file(name)
        self.device_name_file_present=name.exists()
        self.srcversion=bounded_text('/sys/module/zocl/srcversion')
        need(self.srcversion=='15F2AC2306CB3CB7257CFCB','original loaded driver srcversion differs')
        paths=[Path('/sys/module/zocl'),Path('/sys/class/fpga_manager/fpga0')]
        self.overlays=[]
        for name in snapshot['overlays']:
            p=Path('/sys/kernel/config/device-tree/overlays')/name;paths.append(p);self.overlays.append(p)
        for row in snapshot['zocl_binding_details']:
            p=Path(row['path']);paths.extend((p,p/'driver',p/'driver/module'))
        for node in snapshot['render_nodes']:paths.append(Path(node)) # O_PATH only, never DRM open
        self.nodes=NodePins(paths);self.identity_check()
    def owner_check(self):
        # Keep the original fresh full lease SHA exactly once. Anchor its path
        # to the held inode before/after, rather than hashing the same bytes twice.
        self._lease_metadata();self.original.Owner.owner_check(self.owner);self._lease_metadata()
        need(not self.owner.finished and self.platform.owner is self.owner,'original owner detached/finished')
    def _lease_metadata(self):
        import stat
        r=self.reader;need(not r.closed and not r.blocked,'held original lease reader closed/blocked')
        parent=r.path.parent.lstat()
        need(stat.S_ISDIR(parent.st_mode) and parent.st_uid==os.geteuid() and not parent.st_mode&0o022 and
            (parent.st_dev,parent.st_ino)==(r.parent_pin.st_dev,r.parent_pin.st_ino),'original lease parent generation changed')
        need(file_pin(os.fstat(r.fd))==r.identity and file_pin(os.stat(r.path.name,dir_fd=r.parent,follow_symlinks=False))==r.identity,
            'original lease inode/metadata changed')
    def identity_check(self):
        need(os.geteuid()==0 and os.uname().machine=='aarch64' and os.uname().release==KERNEL and bounded_sha('/etc/machine-id')==MACHINE and
            bounded_text('/proc/sys/kernel/random/boot_id')==self.boot,'live Board machine/boot/kernel changed')
        need(bounded_text('/sys/module/zocl/srcversion')==self.srcversion and bounded_text('/sys/module/zocl/initstate')=='live','live driver generation changed')
        need(bounded_text('/sys/class/fpga_manager/fpga0/state')=='operating','FPGA not operating')
        actual=[]
        for node in Path('/sys/kernel/config/device-tree/overlays').iterdir():
            actual.append(node);need(len(actual)<=len(self.overlays),'unexpected extra overlay')
        need(len(actual)==len(self.overlays) and set(actual)==set(self.overlays) and all(bounded_text(p/'status')=='applied' for p in self.overlays),'overlay generation changed')
        p=Path('/etc/xocl.txt');need(p.exists()==self.device_name_file_present,'device-name policy changed')
        if self.device_name_file_present:
            self.original.trusted_file(p);need(bounded_text(p).split()[0]==self.device_name,'device name changed')
    def health(self):return self.original.Owner._health_observation(self.owner,closing=False)
    def validate_context(self,facts,pid,start_ticks):
        if type(self) is BoardPorts:inherited_lock_proof(LOCKS,self.owner.locks,pid,os.getpid())
        p=self.profile
        need(facts['schema']=='A12_PL_CONTEXT_UNBOUND_V1' and facts['production_enabled'] is False and facts['board_generation_approval']=='UNBOUND' and
            facts['worker_pid']==pid and facts['worker_start_ticks']==start_ticks and facts['boot_id'].strip()==self.boot and
            type(facts['context_generation']) is str and len(facts['context_generation'])>=16 and
            facts['xclbin_sha256']==p['xclbin_sha256'] and facts['xclbin_uuid']==p['xclbin_uuid'] and facts['kernel_build_id']==p['kernel_build_id'] and
            facts['device_name']==self.device_name and facts['device_index']==0 and facts['groups']==[3]*6 and facts['windows']==[[0,2147483648]]*6,
            'native context differs from independent live Board source')
        spans=list(zip(facts['io_addresses'],facts['io_sizes']))
        need(len(facts['io_addresses'])==len(facts['io_sizes'])==4 and [n for _,n in spans]==[40960,8192,155648,8192],'native initial IO geometry differs')
        for i,(a,n) in enumerate(spans):
            need(type(a) is int and 0<=a and a+n<=2147483648 and all(a+n<=b or b+m<=a for b,m in spans[:i]),'native initial IO spans overlap/outside low2GiB')
    def validate_resident(self,route,context):
        spans=original_bo_validator()(route) # original 148 BO/72 weight/140591104/8192/low2GiB/nonoverlap checks
        need(route['a11_io_bo_addresses']==context['io_addresses'] and route['a11_io_bo_charged_sizes']==context['io_sizes'],
            'resident initial IO generation changed')
        return spans
    def mark_resident(self):self.owner.full_resident=True
    def close_observers(self):
        if self.reader is not None:self.reader.close()
        if self.nodes is not None:self.nodes.close()
        # Borrower: no original locks/lease/device close.
