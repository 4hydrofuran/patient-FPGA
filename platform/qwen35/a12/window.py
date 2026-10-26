"""A12 platform owner. No PL/driver modification, implicit reset, or stale takeover.

Used by a future reviewed platform entry. It creates a NEW lease, holds both
canonical flocks and keeps the manager alive until strict finalization succeeds.
"""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from common import ROOT, sha, save
sys.path.insert(0,str(ROOT/'platform/qwen35/a10'))
from accelerator_release_gate_v2 import collect, require_release, require_no_users, start_ticks
from isolated_idle_policy import lock_owned, trusted_file
from kernel_log_gate import KernelLogGate
from supervisor import OwnedWorker

MACHINE='ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec'
CENTRAL=Path('/var/lock/kv260-a1')
LOCKS=(CENTRAL/'deployment.lock',Path('/run/lock/patient-qwen-linear.lock'))


class Window:
    def __init__(self,review,*,evidence):
        if os.geteuid()!=0 or os.uname().machine!='aarch64':raise RuntimeError('A12 window requires root on registered ARM64 board')
        if review.get('schema')!='A12_FRESH_WINDOW_V1' or review.get('authorized_compute') is not True:
            raise ValueError('fresh A12 window review required')
        self.boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        if (review.get('machine_sha256')!=MACHINE or sha('/etc/machine-id')!=MACHINE or
            review.get('boot_id')!=self.boot or os.uname().release!='6.8.12-a10irq2'):
            raise RuntimeError('board/boot/kernel differs')
        self.review=review;self.evidence=Path(evidence);trusted_file(self.evidence)
        self.locks=[];self.finished=False
        # Manager must not lose its flocks because an ordinary terminal closes.
        signal.pthread_sigmask(signal.SIG_BLOCK,{signal.SIGINT,signal.SIGTERM,signal.SIGHUP,signal.SIGQUIT})
        for path in LOCKS:
            trusted_file(path);fd=os.open(path,os.O_RDWR|os.O_NOFOLLOW|os.O_CLOEXEC)
            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);self.locks.append(fd)
        self.expires=time.monotonic_ns()+int(review['max_session_seconds'])*1_000_000_000
        baseline=Path(review['kernel_baseline_file']);trusted_file(baseline)
        if sha(baseline)!=review['kernel_baseline_sha256']:raise RuntimeError('kernel baseline hash differs')
        self.gate=KernelLogGate()
        observation=self.gate.observe(self.boot,baseline.read_text(),review['kernel_baseline_sha256'])
        if observation['allowed'] is not True:raise RuntimeError('kernel baseline rejected')
        if not 0<=time.monotonic_ns()-review['baseline_read_monotonic_ns']<=10_000_000_000:
            raise RuntimeError('stale platform baseline')
        self.health();snapshot=collect(allow_ps_display=True)
        require_no_users(snapshot,True,boot_id=self.boot)
        (CENTRAL/'active').mkdir() # any old/incomplete lease blocks admission
        lease=dict(schema='A12_MODEL_LEASE_V1',owner='A',scope=review['scope'],window=review['window_id'],
            identity=MACHINE+':'+self.boot,pid=os.getpid(),owner_start_ticks=start_ticks(Path('/proc')/str(os.getpid())),
            expires_monotonic_ns=self.expires,compute_authorized=True,
            max_runs=review['max_runs'],max_loads=review['max_loads'],
            explicit_bo_budget_bytes=review['explicit_bo_budget_bytes'])
        save(CENTRAL/'active/lease.json',lease);self.lease_hash=sha(CENTRAL/'active/lease.json')

    def health(self,*,closing=False):
        if Path('/proc/sys/kernel/random/boot_id').read_text().strip()!=self.boot:raise RuntimeError('boot changed')
        r=subprocess.run(['dmesg','--raw'],capture_output=True,text=True,timeout=3)
        if r.returncode or r.stderr or not self.gate.observe(self.boot,r.stdout)['allowed']:
            raise RuntimeError('unreadable or unreviewed kernel log')
        if not closing:
            temps=[int(p.read_text()) for p in Path('/sys/class/hwmon').glob('hwmon*/temp*_input')]
            mem={s.split(':')[0]:int(s.split()[1]) for s in Path('/proc/meminfo').read_text().splitlines()}
            if not temps or any(not 0<t<55000 for t in temps) or mem['MemAvailable']<1048576 or mem['CmaFree']<32768:
                raise RuntimeError('health reserve gate')

    def owner_check(self):
        if sha(CENTRAL/'active/lease.json')!=self.lease_hash or not all(lock_owned(p,os.getpid()) for p in LOCKS):
            raise RuntimeError('lease or canonical lock ownership changed')
        if 'libxrt_' in Path('/proc/self/maps').read_text():raise RuntimeError('manager must not map XRT')

    def profile_fields(self):
        self.owner_check()
        return dict(boot_id=self.boot,manager_pid=os.getpid(),
            manager_start_ticks=start_ticks(Path('/proc')/str(os.getpid())),
            inherited_device_lock_fd=self.locks[1],expires_monotonic_ns=self.expires)

    def start_worker(self,bundle,*,asset_root=Path('/opt/patient-qwen')):
        """Called only after a separate entry prepared the matching PL/driver.

        The candidate contains disabled configs. This method writes fresh private
        configs in this window, never modifies the original bundle or defaults.
        """
        self.owner_check();self.health();bundle=Path(bundle)
        manifest=json.loads((bundle/'manifest.json').read_text())
        if sha(bundle/'manifest.json')!=self.review['bundle_sha256']:
            raise RuntimeError('bundle differs from reviewed window')
        for item in manifest['files']:
            path=bundle/item['path'];trusted_file(path)
            if path.stat().st_size!=item['bytes'] or sha(path)!=item['sha256']:
                raise RuntimeError('bundle payload differs')
        model=asset_root/'artifacts/qwen35-0.8b/qwen35-text-Q4_K_M.gguf'
        acceptance=json.loads((bundle/'evidence/ACCEPTANCE.json').read_text())
        if sha(model)!=acceptance['model_sha256']:raise RuntimeError('model asset differs')
        profiles=json.loads((bundle/'evidence/RESOURCE_CALL_BUDGET.json').read_text())['profiles']
        selected=next(p for p in profiles if p['scope']==self.review['scope'])
        for key,budget_key in (('max_runs','max_successful_runs'),('max_loads','weight_load_limit'),
                               ('explicit_bo_budget_bytes','explicit_bo_limit_bytes')):
            if self.review[key]!=selected[budget_key]:raise RuntimeError('reviewed budget differs')
        profile=json.loads((bundle/'config/profile.pending.json').read_text())
        name=Path('/etc/xocl.txt')
        if name.exists():trusted_file(name);tokens=name.read_text().split();device=tokens[0]
        else:device='edge'
        profile.update(self.profile_fields(),status='A12_BOUNDED_MODEL_TRIAL_NOT_ACCEPTED',device_name=device,
            trial_bo_limit_bytes=self.review['explicit_bo_budget_bytes'],a12_max_runs=self.review['max_runs'],
            a12_max_loads=self.review['max_loads'])
        save(self.evidence/'runtime-profile.json',profile)
        cfg=json.loads((bundle/'config/backend.pending.json').read_text())
        cfg.update(allow_device_access=True,kernel_source=str(bundle/'KERNEL_SOURCE.json'),
            deployment_profile=str(self.evidence/'runtime-profile.json'),xclbin_path=str(bundle/'w4a8.xclbin'))
        save(self.evidence/'runtime-backend.json',cfg)
        router=dict(contract_sha256=cfg['contract_sha256'],fallback='disabled',fpga_required=True,
            scope=self.review['scope'],execution_kind='FPGA_REAL',trace_limit=4096,
            library=str(bundle/'bin/libsp_linear_a12_trial.so'),library_sha256=sha(bundle/'bin/libsp_linear_a12_trial.so'),
            backend_config=str(self.evidence/'runtime-backend.json'),backend_config_sha256=sha(self.evidence/'runtime-backend.json'))
        save(self.evidence/'runtime-route.json',router)
        env=dict(os.environ,SP_A12_CONFIG=str(self.evidence/'runtime-route.json'))
        return OwnedWorker([str(bundle/'bin/qwen35-a12'),str(model),'2','1024','all','TILED','2','8'],
            directory=self.evidence/'worker',env=env,inherited_fds=tuple(self.locks),health=self.health,
            max_runs=self.review['max_runs'],max_loads=self.review['max_loads'],
            expires=self.expires/1e9,real=True,owner_check=self.owner_check)

    def finish(self,worker):
        if not worker.closed or worker.process.returncode!=0:raise RuntimeError('normal worker exit not proven')
        self.owner_check();self.health(closing=True)
        snapshot=collect(allow_ps_display=True)
        ref=Path('/sys/module/zocl/refcnt')
        require_release(snapshot,int(ref.read_text()) if ref.exists() else 0,True,boot_id=self.boot)
        # Platform restoration belongs to the separate reviewed platform entry.
        # No lease release until independently readable default state is present.
        overlays=Path('/sys/kernel/config/device-tree/overlays')
        applied=[p for p in overlays.glob('k26-starter-kits*/status') if p.read_text().strip()=='applied']
        if ref.exists() or not applied or Path('/sys/class/fpga_manager/fpga0/state').read_text().strip()!='operating':
            raise RuntimeError('default PL restore not proven')
        r=subprocess.run(['systemctl','is-active','gdm'],capture_output=True,text=True,timeout=3)
        if r.returncode or r.stdout.strip()!='active':raise RuntimeError('GDM restore not proven')
        save(self.evidence/'final-resource-scan.json',snapshot)
        target=CENTRAL/'history'/self.review['window_id'];target.parent.mkdir(exist_ok=True)
        if target.exists():raise FileExistsError('consumed window')
        (CENTRAL/'active').rename(target)
        for fd in reversed(self.locks):os.close(fd)
        self.locks=[];self.finished=True

    def retain_until_finished(self,reason):
        save(self.evidence/'ISOLATED.json',dict(reason=reason,lease_retained=True,no_kill=True))
        while not self.finished:time.sleep(1)
