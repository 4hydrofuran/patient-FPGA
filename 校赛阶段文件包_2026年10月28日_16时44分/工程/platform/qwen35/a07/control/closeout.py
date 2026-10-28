"""Seal A07 after the actual isolated package check; no hardware claims."""
import hashlib,json,shutil,subprocess,sys
from pathlib import Path
R=Path(__file__).resolve().parents[4];E=R/'evidence/A07_closeout/20261004-v1'
P=R/'release/a07_b04_v3';W=Path(sys.argv[1]).resolve()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v,replace=False):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('w' if replace else 'x') as f:json.dump(v,f,indent=2)
def copy(s,d):d.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(s,d)
def command(argv,dest):
    q=subprocess.run(list(map(str,argv)),capture_output=True,text=True)
    save(dest,{'argv':list(map(str,argv)),'cwd':str(Path.cwd()),'exit_code':q.returncode,'stdout':q.stdout,'stderr':q.stderr})
    assert q.returncode==0,(dest,q.returncode)
    return q.stdout
receipt=json.loads((E/'clean-run.json').read_text());job=json.loads(receipt['stdout'])
assert receipt['exit_code']==job['exit_code']==0 and Path(job['cwd'])==W
assert (W/'delivery/files.sha256.json').read_bytes()==(P/'files.sha256.json').read_bytes()
copy(P/'files.sha256.json',E/'preclean.files.sha256.json')
copy(P/'a_delivery.json',E/'preclean.a_delivery.json')
for name in ['control-normal','control-sanitized']:
    s=json.loads((W/'control-build'/name/'SUMMARY.json').read_text())
    assert s=={'domain':'PC_CONTROL_DOUBLE_NOT_FPGA','cases':29,'checks':554,'mathematical_verification':False,'hardware_performance':None,'BOARD':'NOT_TESTED'}
    shutil.copytree(W/'control-build'/name,P/'reports/clean'/name)
text=(W/'stdout.txt').read_text()
records=[json.loads(line) for line in text.splitlines() if line.startswith('{') and line.endswith('}')]
host=[x for x in records if x.get('domain')=='PC_HOST_LOGIC_ONLY']
meta=[x for x in records if x.get('domain')=='PC_ARCHIVED_RTL_META_REPLAY']
assert len(host)==2 and all(x['assertions']==970 and x['device_calls']==0 for x in host)
assert len(meta)==2 and all(x['actual_meta_records']==66 and x['tamper_rejections']==396 and x['bad_build_ids']==4 and x['device_calls']==0 for x in meta)
for name in ['stdout.txt','stderr.txt','B-preflight.json']:copy(W/name,P/'reports/clean'/name)
copy(E/'clean-run.json',P/'reports/clean/queue-command.json')
original=json.loads((E/'control-v2/REPORT.json').read_text())
rebuilt={}
for name in ['libsp_linear_xrt_candidate.so','sp-linear-host']:
    p=W/'portable-build'/name
    elf=command(['readelf','-h','-d','--dyn-syms','--wide',p],P/'reports/clean'/(name+'.elf.json'))
    assert 'AArch64' in elf
    # Absolute build paths may be embedded; raw equality is reported, not assumed.
    rebuilt[name]={'sha256':sha(p),'original_sha256':original['artifacts'][name]['sha256'],
        'byte_identical':sha(p)==original['artifacts'][name]['sha256']}
    assert b'CONTROL_TEST_DOUBLE' not in p.read_bytes()
for name in ['cross-v2-run.json','cross-v2-submit.json']:
    copy(R/'evidence/A07_independent/preboard-v1'/name,P/'reports/previous-model'/name)
copy(R/'evidence/A07_independent/preboard-v1/artifact-audit-v2/REPORT.json',P/'reports/previous-model/ELF_ISA_DEPENDENCY_AUDIT.json')
copy(R/'platform/qwen35/a07/build_a53.sh',P/'reports/previous-model/build_a53.sh')
clean={'status':'PASS_CLEAN_DELIVERY_REBUILD','queue_job':job,'isolated_copy_hash_manifest_sha256':sha(W/'delivery/files.sha256.json'),
    'PC_host_checks':970,'PC_archived_meta':66,'PC_tamper_checks':396,'PC_build_checks':4,
    'PC_control_cases':29,'PC_control_checks':554,'same_tests_ASAN_UBSAN':'PASS',
    'ARM64_rebuilt':rebuilt,'ARM64_execution':'NOT_TESTED','BOARD':'NOT_TESTED',
    'model_scope':'Existing A53 full S1 model reused by exact artifact hashes; not recompiled or executed in this package check.',
    'original_delivery_manifest_sha256':sha(W/'delivery/a_delivery.json')}
save(P/'reports/clean/REPORT.json',clean)
d=json.loads((P/'a_delivery.json').read_text());d['status']='PASS_A07_OFFLINE'
d['clean_reproduction']={'path':'reports/clean/REPORT.json','sha256':sha(P/'reports/clean/REPORT.json')}
d['deployment_status']='DEPLOYMENT_PENDING_BOARD';d['B04_joint_signoff']='NOT_CLAIMED'
save(P/'a_delivery.json',d,replace=True)
b=P/'hw/linear_B_received/B04-scope-9a75600-20261003'
command(['python3',b/'tools/b04_a_preflight.py',P,'--readelf','/usr/bin/readelf','--receipt',P/'reports/B-preflight-final.json'],P/'reports/B-preflight-final-command.json')
save(P/'files.sha256.json',{p.relative_to(P).as_posix():{'bytes':p.stat().st_size,'sha256':sha(p)} for p in P.rglob('*') if p.is_file() and p!=P/'files.sha256.json' and '__pycache__' not in p.parts},replace=True)
command(['python3',R/'platform/qwen35/a07/control/verify_hashes.py',P],E/'package-final-verification.json')
impl=json.loads((P/'reports/implementation/REVIEW.json').read_text())
save(E/'REPORT.json',{'status':'PASS_A07_OFFLINE','date':'2026-10-04','owner':'A','BOARD':'NOT_TESTED',
    'delivery':'release/a07_b04_v3','delivery_manifest_sha256':sha(P/'a_delivery.json'),'delivery_seal_sha256':sha(P/'files.sha256.json'),
    'implementation':impl,'control_and_ARM64':original,'clean_reproduction':clean,
    'A06_status':'ACCEPTED_A06_OFFLINE','B04_git_revision':'9a75600e0df8816f4b9134b5c39d67965310dcd3',
    'B04_joint_signoff':'NOT_CLAIMED','deployment_status':'DEPLOYMENT_PENDING_BOARD',
    'failures_retained':['control-v1: PC OpenSSL headers missing; privately extracted matching dev/runtime packages, v2 pass',
        'audit-v1: absent scalable clock section; use actual fixed clocks',
        'audit-v2: SYSTEM_METADATA requires RAW dump; v3 actual audit pass',
        'package-v2: contract bundle/header hash scope mixup; unchanged header/contract, package-v3 pass'],
    'remaining':['KV260 boot/firmware/DT/kernel/XRT pairing','Actual Linux/CMA/BO groups/address range/budget','ARM execution/real XRT numerical tests/timeout recovery','A12 full model consumes real PL results','A09 other outstanding system/voice deployment work'],
    'P2_NOT_IMPLEMENTED':['Larger arena/async prefetch','Additional compute parallelism or DSP pipeline optimization','Permanent fixed-MAC Linux environment migration'],
    'new_commit':None,'remote_push_this_increment':False,'settings_changed':False})
print(json.dumps({'status':'PASS_A07_OFFLINE','package':str(P),'BOARD':'NOT_TESTED'}))
