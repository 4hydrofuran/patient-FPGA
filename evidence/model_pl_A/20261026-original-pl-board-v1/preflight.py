import hashlib,json,os,subprocess,sys,time,urllib.request,zipfile
from pathlib import Path
ROOT=Path('/var/lib/kv260-a12/original-pl-20261026-v1')
assert os.geteuid()==0 and os.uname().release=='6.8.12-a10irq2'
assert hashlib.sha256(Path('/etc/machine-id').read_bytes()).hexdigest()=='ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec'
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()=='8a0276fb-86d1-4ef8-b067-adcc903a999a'
assert not Path('/var/lock/kv260-a1/active').exists() and not Path('/sys/module/zocl').exists()
ROOT.mkdir(mode=0o700)
archive=ROOT/'original-bundle.zip';h=hashlib.sha256()
with archive.open('xb') as out:
    with urllib.request.urlopen('http://192.168.2.1:8765/bundle.zip',timeout=20) as incoming:
        while True:
            b=incoming.read(65536)
            if not b:break
            out.write(b);h.update(b)
assert h.hexdigest()=='acd578ddd66140a3d0507d71ea9a1d30245c632c7537f0a940227935cc17a7fa'
bundle=ROOT/'bundle';bundle.mkdir(mode=0o700)
with zipfile.ZipFile(archive) as z:z.extractall(bundle)
sys.path.insert(0,str(bundle/'control/support'))
from accelerator_release_gate_v2 import collect,require_no_users
from kernel_log_gate import diagnostics
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
scan=collect(allow_ps_display=True);require_no_users(scan,True,boot_id=boot)
lock=Path('/run/lock/patient-qwen-linear.lock')
if not lock.exists():
    with lock.open('xb'):pass
    lock.chmod(0o600)
spec=json.loads((bundle/'control/window-spec.json').read_text())
spec.update(window_id='a12-original-pl-20261026-v1',authorization_included=True,max_session_seconds=600)
(bundle/'control/window-spec.json').write_text(json.dumps(spec,indent=2))
raw=subprocess.check_output(['dmesg','--raw']).decode()
baseline=hashlib.sha256(raw.encode()).hexdigest()
(bundle/'control/preflight.json').write_text(json.dumps(dict(boot_id=boot,kernel_raw=raw,kernel_sha256=baseline)))
(bundle/'control/activation.json').write_text(json.dumps(dict(status='BOUND_TO_USER_ORIGINAL_PL_ACCEPTANCE',execution_enabled=True,authorization_included=True)))
authorization=dict(user_request='按原验收流程完成一次PL端验收，25分钟以内',boot_id=boot,kernel=os.uname().release,
                   window_id=spec['window_id'],max_runs=5000,max_loads=72,max_session_seconds=600,
                   no_heavy_diagnostics=True,original_bundle_sha256=h.hexdigest(),single_attempt=True)
(bundle/'control/authorization.json').write_text(json.dumps(authorization,ensure_ascii=False,indent=2))
manifest=json.loads((bundle/'manifest.json').read_text());manifest.update(module_id='A12_ORIGINAL_FLOW_BOUND_20261026_V1',authorization_included=True,budget=spec)
manifest['files']=[dict(path=p.relative_to(bundle).as_posix(),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(bundle.rglob('*')) if p.is_file() and p!=bundle/'manifest.json']
(bundle/'manifest.json').write_text(json.dumps(manifest,indent=2))
result=dict(status='ORIGINAL_FLOW_STAGED_PENDING_EXACT_BASELINE_REVIEW',boot_id=boot,kernel=os.uname().release,
            baseline_sha256=baseline,kernel_raw=raw,diagnostics=diagnostics(raw),scan_complete=scan['scan_complete'],
            process_count=scan.get('process_count'),memory={r.split(':')[0]:int(r.split()[1]) for r in Path('/proc/meminfo').read_text().splitlines() if r.startswith(('MemAvailable:','CmaFree:'))},
            original_main_body_unchanged=True,PL_mutations=0)
(ROOT/'preflight.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print('__PL_BEGIN__',flush=True);print(json.dumps(result),flush=True);print('__PL_END__',flush=True)
