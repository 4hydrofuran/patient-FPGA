"""Seal this independent scope without promoting A06/A07/BOARD acceptance."""
import hashlib,json,shutil,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
E=ROOT/'evidence/A07_independent/preboard-v1'
def read(p):return json.loads(p.read_text())
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def new(p,obj):
    with p.open('x',encoding='utf-8') as f:json.dump(obj,f,ensure_ascii=False,indent=2)

audit=read(E/'artifact-audit-v2/REPORT.json')
assert audit['status']=='PASS_INDEPENDENT_COMPILE_AND_HOST_GUARDS_ONLY'
assert all(t['assertions']==969 for t in audit['host_tests'])
archive=read(E/'archive-tests.json');assert archive['exit_code']==0 and 'Ran 8 tests' in archive['stderr']
before=read(E/'inputs.sha256.json')
mutable={'docs/PROJECT_STATUS.json','docs/status/A.md','docs/DESIGN_GAP.md','docs/TEST_MATRIX.md'}
for key,value in before.items():
    key=key.replace('\\','/')
    assert sha(E/'before'/key)==value
    if key not in mutable:assert sha(ROOT/key)==value,key
sidecar=ROOT/'models/sidecar_A/qwen35-v1';manifest=read(sidecar/'manifest.json');count=0
for entry in manifest['entries']:
    for item in entry['files'].values():
        p=sidecar/item['file'];assert sha(p)==item['sha256'];count+=1
old=read(ROOT/'modules/linear_A/manifest.json')
for name,item in old['files'].items():assert sha(Path(name))==item['sha256'],name
kernel=read(ROOT/'hw/linear_A/KERNEL_SOURCE.json');assert kernel['accepted'] is False and kernel['frozen'] is False
# Verify the final compiled host sources correspond to current code; documentation may be added later.
host_inputs=read(E/'artifact-audit-v2/host/input-sha256.json')
for name,value in host_inputs.items():
    if name.startswith('modules/linear_A/xrt/') or name.endswith('test_host.cpp'):
        assert sha(ROOT/name)==value,name
commands={}
for p in E.glob('*.json'):
    r=read(p)
    if isinstance(r,dict) and 'argv' in r and r.get('exit_code') is not None:
        commands[p.name]={'sha256':sha(p),'argv':r['argv'],'exit_code':r['exit_code']}
assert read(E/'host-run.json')['exit_code']==1
# Preserve first failed and initial non-relocatable build logs, not just successful reruns.
for label,filename in [('host-failed-v1','host-run.json'),('cross-original-v1','cross-run.json')]:
    receipt=json.loads(read(E/filename)['stdout']);directory=Path(receipt['cwd']);target=E/label;target.mkdir(exist_ok=False)
    for name in ('stdout.txt','stderr.txt'):shutil.copy2(directory/name,target/name)
    new(target/'queue-receipt.json',receipt)
report={'date':'2026-10-03','scope':'A06/A07 INDEPENDENT PREPARATION, USER AUTHORIZED NO-B WORK',
    'status':'PASS_INDEPENDENT_SCOPE_A06_AND_A07_NOT_PASSED','provider_kernel_accepted':False,
    'domains':{'PC':'PASS_HOST_GUARDS_969_PLUS_8_ARCHIVE_TEST_METHODS','PC_sanitizers':'PASS_SAME_969_ASAN_UBSAN',
        'ARM64_cross_build':'PASS_S1_CPU_XRT_CANDIDATE_SELFTEST_AND_LIBRARIES',
        'ARM64_execution':'NOT_TESTED','Csim':'NOT_TESTED_THIS_INCREMENT_PREVIOUS_A06_PRESERVED',
        'Cosim':'NOT_TESTED','synthesis':'NOT_TESTED','implementation':'NOT_TESTED','BOARD':'NOT_TESTED'},
    'tests':{'host_assertions':969,'sanitizer_same_assertions':969,'archive_test_methods':8,'device_calls':0},
    'compile_translation_units':audit['compile_translation_units'],'rootfs_sdk_library_exact_matches':len(audit['rootfs_sdk_checks']),
    'artifacts':audit['elf'],'staging':audit['staging'],'commands':commands,
    'preservation':{'before_files':len(before),'sidecar_payload_files':count,'CPU_default_binaries_unchanged':len(old['files']),
                    'model_and_contracts_unchanged':True,'received_B_files_modified':False},
    'failures_preserved':['First XRT link exit1: missing -luuid; fixed in v2.',
        'First ARM build compiled but llama RPATH held build-host absolute paths; v2 relinked with $ORIGIN.',
        'First audit output directory label shadowed by loop variable (host instead of v1); v2 corrected naming, original retained.',
        'First finalize exit1: Windows backslash keys not normalized under WSL. Reader fixed; original inputs manifest retained.'],
    'remaining':['B actual selected source/XO/embedded XML/raw simulation inputs not received as complete package; no A06 acceptance.',
        'No B-kernel v++ link/implementation/xclbin; no accepted-kernel ABI replay against new XO.',
        'Actual six-function XRT device/sync/timeout/BO lifetime behavior NOT_TESTED; PC tested shared pure host logic only.',
        'XRT 2.23 deprecated load_xclbin/device-kernel compatibility APIs retain compiler warnings.',
        'Common rootfs library match is not a verified KV260 boot bundle; EDF/DT discrepancy unresolved.',
        'BOARD memory/BO budget, device identity/lease/recovery, target runtime and quantization numerics pending.',
        'Driver state/sync hang hard deadline not proven; no automatic abort/recovery implemented.',
        'A12 actual model PL output consumption not implemented/tested; application still explicit S1 CPU.'],
    'bo_budget_bytes':None,'board_memory_bytes':None,'hardware_error':None,'xclbin_sha256':None,
    'new_commit':None,'remote_push':False,'model_setting_actual':'unknown','subagents':False,
    'skill':'llama-cpp: fixed source, isolated CPU/A53 build; no download or native-ISA assumptions'}
new(E/'REPORT.json',report)
print(json.dumps({'status':report['status'],'preserved_payloads':count,'artifacts':len(audit['elf']),'BOARD':'NOT_TESTED'}))
