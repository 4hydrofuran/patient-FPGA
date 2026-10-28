"""Derive independent no-compute diagnostic package. PC only; no board access."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[3]
OLD=ROOT/'platform/local/a11-mlp-20261023-v1'
EV=ROOT/'evidence/mlp_board_A/20261023-integration-v1'


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def change(s, old, new, count=1):
    if s.count(old)!=count: raise ValueError('unexpected source seam: '+old)
    return s.replace(old,new)


def prepare(out):
    man=json.loads((OLD/'manifest.json').read_text())
    if sha(OLD/'manifest.json')!='3b3c46700f92565839abda962e07e557018b8fd1be9e7846613ff46ecf89f11c':
        raise ValueError('old manifest changed')
    out.mkdir(parents=True,exist_ok=False)
    names=('accelerator_release_gate_v2.py','isolated_idle_policy.py','idle_board_trial.py',
           'kernel_log_gate.py','xrt_worker_boundary.py','mlp_base.py','mlp_kernel_gate.py',
           'managed_unused','mlp_manager_entry.py','manager_support.py','mlp_boundary_v2.py',
           'a11-mlp.bit.bin','a11-mlp.dtbo','w4a8.xclbin','zocl.refcount.ko',
           'KERNEL_SOURCE.json','prior-a10-audit.json','shell.json','trial-config.json',
           'trial-profile-template.json','vectors/manifest.json')
    for name in names:
        if name=='managed_unused': continue
        p=OLD/name
        if sha(p)!=man['files'][name]['sha256']: raise ValueError('old payload changed: '+name)
        dst=out/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dst)
    p=EV/'backend-diagnostic-v2/libsp_linear_a11_trial.so'
    if sha(p)!='2cc36ae8aecf5860f1ff49018cc61de3242addb5a8ef6db2b64aebcc144ee8c1': raise ValueError('diagnostic library changed')
    shutil.copyfile(p,out/p.name)
    shutil.copyfile(Path(__file__).with_name('open_only_worker.py'),out/'open_only_worker.py')
    # Private protocol only. Public ABI/math/old manifests remain byte identical.
    s=(OLD/'mlp_policy.py').read_text()
    s=s.replace('A11_MINIMAL_MLP_23_ONCE','A11_OPEN_DIAGNOSTIC_ONCE_NO_COMPUTE')
    s=s.replace('a11-minimal-mlp-worker-v1','a11-open-only-worker-v1')
    s=s.replace('A11_MLP_REVIEW_V1','A11_OPEN_REVIEW_V1').replace('A11_MLP_BUNDLE_V1','A11_OPEN_BUNDLE_V1')
    s=change(s,"('authorized','compute_authorized','allow_gdm_stop_restore')","('authorized','allow_gdm_stop_restore')")
    s=change(s,"for key,val in (('max_submissions',23)","need(r.get('compute_authorized') is False,'compute forbidden')\n    for key,val in (('max_submissions',0)")
    s=s.replace("r'a11-mlp-20261023-v[1-9][0-9]*'","r'a11-open-20261023-v[1-9][0-9]*'")
    s=change(s,"man['max_submissions']==23","man['max_submissions']==0")
    s=change(s,"'mlp_engine.py'","'open_only_worker.py'")
    s=change(s,"'liba11_quant.so',",'')
    s=change(s,"lease.get('compute_authorized') is True and lease.get('max_submissions')==23",
             "lease.get('compute_authorized') is False and lease.get('max_submissions')==0")
    (out/'mlp_policy.py').write_text(s)
    # Retain all original worker boot/hash/owner/baseline checks and health gate.
    s=(OLD/'mlp_worker.py').read_text()
    s=change(s,'from mlp_engine import NativeAPI,run_plan','from open_only_worker import execute')
    start=s.index('    try:\n        api=NativeAPI(source)')
    end=s.index('\n\n\nif __name__', start)
    s=s[:start]+'''    return execute(source, identity, checkpoint, write, quarantine)
'''+s[end:]
    (out/'mlp_worker.py').write_text(s)
    # Boundary uses waitpid and existing post-exit release gate; no fake MLP pass.
    s=(OLD/'mlp_boundary_v2.py').read_text()
    s=s.replace("PROTOCOL='a11-minimal-mlp-worker-v1'","PROTOCOL='a11-open-only-worker-v1'")
    start=s.index('def validate_result(');end=s.index('\n\nclass MlpBoundary',start)
    validator='''def validate_result(result,identity,pid):
    for key,value in dict(identity,worker_pid=pid,status='OPEN_DIAGNOSTIC_RETURNED_NO_COMPUTE',
                          real_submissions=0,release_proven=False,A11='NOT_PASSED').items():
        need(type(result.get(key)) is type(value) and result[key]==value,'diagnostic identity differs: '+key)
    rc=result.get('open_status_code')
    need(type(rc) is int and rc in range(10),'invalid diagnostic return')
    need(result.get('normal_handles_closed') is (rc==0),'unexpected context ownership')
    need(result.get('close_status_code')==0 if rc==0 else result.get('close_status_code') is None,
         'close result differs')
    need(result.get('explicit_bo_allocations') is None and result.get('physical_bo_peak_bytes') is None,
         'unmeasured BO fields')
    return result
'''
    s=s[:start]+validator+s[end:]
    # v2 wait loop calls pulse; open-only needs health only, never compute permits.
    (out/'mlp_boundary_v2.py').write_text(s)
    s=(OLD/'mlp_manager.py').read_text()
    s=s.replace('compute_authorized=True','compute_authorized=False').replace('max_submissions=23','max_submissions=0')
    s=change(s,'self.worker.pulse = lambda: pulse(self)','self.worker.pulse = lambda: self.guard()')
    s=change(s,'self.worker.wait_normal(240)','self.worker.wait_normal(20)')
    s=change(s,"status='PASS_MLP_23_AND_NORMAL_RELEASE_REQUIRES_INDEPENDENT_AUDIT'",
             "status='OPEN_DIAGNOSTIC_AND_RELEASE_REQUIRES_INDEPENDENT_AUDIT'")
    s=change(s,'compute_runs=23','compute_runs=0')
    s=change(s,'explicit_requested_peak_bytes=2154496','explicit_requested_peak_bytes=None')
    s=s.replace('MLP_LIFECYCLE_COMPLETE_DEFAULT_PL_RESTORED','OPEN_DIAGNOSTIC_COMPLETE_DEFAULT_PL_RESTORED')
    s=s.replace('--execute-authorized-mlp-once','--execute-authorized-open-once').replace('args.execute_authorized_mlp_once','args.execute_authorized_open_once')
    (out/'mlp_manager.py').write_text(s)
    # Reuse the reviewed strict scan; allow only known transient observations.
    # No global process-set equality, no waived FD/VMA/permission/driver errors.
    s=(out/'mlp_base.py').read_text()
    s=change(s,'    def observation(self):','    def observation_once(self):')
    pos=s.index('    def no_users(')
    wrapper='''    def observation(self):
        for attempt in range(4):
            scan,refs,allowed=self.observation_once()
            if scan.get('scan_complete') is True: return scan,refs,allowed
            need(allowed and scan.get('boot_id')==self.boot==scan.get('boot_id_after') and
                 scan.get('device_holders')==[] and scan.get('device_mappings')==[] and
                 refs in (None,0),'unsafe incomplete observation')
            issues=scan.get('scan_issues')
            need(type(issues) is list and issues,'unknown incomplete scan')
            for row in issues:
                reason=row.get('reason','')
                missing=re.fullmatch(r"FileNotFoundError: \\[Errno 2\\] No such file or directory: '/proc/(\\d+)/(?:stat|maps|fd(?:/\\d+)?)'",reason)
                need(reason in ('PROCESS_SET_CHANGED','ValueError: PROCESS_OR_FD_TABLE_CHANGED') or
                     (missing and row.get('pid')==int(missing.group(1))),'nontransient scan')
            if attempt<3: time.sleep(.15)
        raise RuntimeError('INCOMPLETE_OBSERVATIONS_NO_ACTION_STARTED')

'''
    s=s[:pos]+wrapper+s[pos:]
    (out/'mlp_base.py').write_text(s)
    files={str(p.relative_to(out)).replace('\\','/'):dict(bytes=p.stat().st_size,sha256=sha(p))
           for p in sorted(out.rglob('*')) if p.is_file()}
    (out/'manifest.json').write_text(json.dumps(dict(schema='A11_OPEN_BUNDLE_V1',
        scope='A11_OPEN_DIAGNOSTIC_ONCE_NO_COMPUTE',authorization_included=False,board_accepted=False,
        max_submissions=0,files=files),indent=2))
    print(json.dumps(dict(status='PC_CANDIDATE',manifest_sha256=sha(out/'manifest.json'),files=len(files),BOARD='NOT_TESTED')))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True)
    prepare(ap.parse_args().out.resolve())
