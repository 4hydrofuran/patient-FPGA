"""Fresh A11 window policy, independent from consumed A10 authorizations."""
import os
from pathlib import Path
import re
import time
import uuid
from accelerator_release_gate_v2 import start_ticks
from isolated_idle_policy import (BOOT_FILES,CENTRAL,DEFAULT,KERNEL,LIBRARIES,LOCKS,MACHINE,
                                  digest,load_json,lock_owned,need,trusted_file)

SCOPE='A11_MINIMAL_MLP_23_ONCE'
PROTOCOL='a11-minimal-mlp-worker-v1'
DRIVER_SHA='388c45a0edefe221615d71ea948de00d0ef68190bdd8497b053dddf788f72b2c'
PLAN_SHA='63d13c5bb7888eb93fbf35ca5d7d6ff70d09d370f88143640bc6e457504b1604'
ASSETS={'zocl.refcount.ko':DRIVER_SHA}


def schedule():
    items=[('hand',1),('tails_double_scale',3)]
    for op in ('gate','up','down'):items += [(f'l00_{op}',t) for t in (1,8,3,1,8,1,8)]
    return [dict(job_id=i+1,weight=w,case=f'{w}_T{t}',T=t) for i,(w,t) in enumerate(items)]


def validate_review(r):
    need(r.get('schema')=='A11_MLP_REVIEW_V1' and r.get('scope')==SCOPE,'wrong A11 review')
    for key in ('authorized','compute_authorized','allow_gdm_stop_restore'):
        need(r.get(key) is True,'missing authorization: '+key)
    for key,val in (('max_submissions',23),('explicit_bo_budget_bytes',4194304)):
        need(type(r.get(key)) is int and r[key]==val,'wrong trial limit')
    boot=r.get('boot_id');need(type(boot) is str and str(uuid.UUID(boot))==boot,'invalid boot')
    need(r.get('kernel')==KERNEL and r.get('machine_sha256')==MACHINE,'wrong platform')
    need(re.fullmatch(r'a11-mlp-20261023-v[1-9][0-9]*',r.get('window_id','')),'wrong window')
    for key in ('baseline_sha256','bundle_sha256','prior_a10_audit_sha256'):
        need(re.fullmatch('[0-9a-f]{64}',r.get(key,'')) is not None,'missing pin '+key)
    need(type(r.get('baseline_read_uptime_ns')) is int and r['baseline_read_uptime_ns']>0,'no fresh baseline')
    return r


def verify_bundle(source,expected):
    source=Path(source)
    need(digest(source/'manifest.json')==expected,'bundle manifest changed')
    man=load_json(source/'manifest.json')
    need(man.get('schema')=='A11_MLP_BUNDLE_V1' and man.get('scope')==SCOPE and
         man.get('authorization_included') is False and man.get('board_accepted') is False and
         type(man.get('max_submissions')) is int and man['max_submissions']==23,'invalid candidate manifest')
    files=man['files']
    required={'mlp_worker.py','mlp_manager.py','mlp_engine.py','mlp_policy.py','mlp_boundary_v2.py',
              'a11-mlp.dtbo','a11-mlp.bit.bin','w4a8.xclbin','libsp_linear_a11_trial.so',
              'liba11_quant.so','zocl.refcount.ko','vectors/manifest.json','prior-a10-audit.json'}
    need(required<=set(files),'missing candidate files')
    for name,entry in files.items():
        p=source/name
        need(not Path(name).is_absolute() and '..' not in Path(name).parts and '\\' not in name,'unsafe payload path')
        need(p.resolve().is_relative_to(source.resolve()) and not p.is_symlink() and p.is_file() and
             p.stat().st_size==entry['bytes'] and digest(p)==entry['sha256'],'payload differs: '+name)
    need(files['zocl.refcount.ko']['sha256']==DRIVER_SHA and files['vectors/manifest.json']['sha256']==PLAN_SHA,
         'frozen driver/plan differs')
    need(load_json(source/'vectors/manifest.json')['schedule']==schedule(),'schedule changed')
    return man


def verify_owner(identity,review,*,parent=False):
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    need(os.geteuid()==0 and os.uname().machine=='aarch64' and os.uname().release==KERNEL,'wrong root/kernel')
    need(boot==identity['boot_id']==review['boot_id'] and identity['window_id']==review['window_id'],'wrong boot/window')
    need(identity['protocol']==PROTOCOL,'wrong protocol')
    pid=identity['manager_pid'];need(type(pid) is int and pid==(os.getppid() if parent else os.getpid()),'wrong parent')
    path=CENTRAL/'active/lease.json'
    for p in (CENTRAL,CENTRAL/'active',path,*LOCKS):trusted_file(p)
    need(digest(path)==identity['lease_sha256'],'lease changed')
    lease=load_json(path)
    need(lease.get('scope')==SCOPE and lease.get('compute_authorized') is True and lease.get('max_submissions')==23 and
         lease.get('window')==review['window_id'] and lease.get('pid')==pid and
         lease.get('identity')==MACHINE+':'+boot,'wrong lease')
    need(lease['owner_start_ticks']==start_ticks(Path('/proc')/str(pid)),'PID reused')
    need(type(lease.get('expires_monotonic_ns')) is int and time.monotonic_ns()<lease['expires_monotonic_ns'],'expired')
    need(all(lock_owned(p,pid) for p in LOCKS),'lost manager lock')
    need('libxrt_' not in (Path('/proc')/str(pid)/'maps').read_text(),'manager loaded XRT')
    return True
