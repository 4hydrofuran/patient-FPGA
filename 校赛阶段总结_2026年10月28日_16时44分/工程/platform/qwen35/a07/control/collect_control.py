"""Collect actual PC control tests and production ARM ELF; no hardware claims."""
import hashlib,json,re,shutil,subprocess,sys
from pathlib import Path
R=Path(__file__).resolve().parents[4]
E=R/'evidence/A07_closeout/20261004-v1'
W=Path(sys.argv[1]).resolve()
OUT=E/'control-v2'
SDK=Path('/home/member-a/kv260-sdk-2026.1-common/sysroots/cortexa72-cortexa53-amd-linux')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):
    with p.open('x') as f:json.dump(v,f,indent=2)
def command(argv,p):
    q=subprocess.run(list(map(str,argv)),capture_output=True,text=True)
    save(p,{'argv':list(map(str,argv)),'exit_code':q.returncode,'stdout':q.stdout,'stderr':q.stderr})
    assert q.returncode==0
    return q.stdout
receipt=json.loads((E/'control-v2-run.json').read_text())
assert receipt['exit_code']==0
job=json.loads(receipt['stdout']);assert job['exit_code']==0 and Path(job['cwd'])==W
OUT.mkdir(exist_ok=False)
for name in ['control-normal','control-sanitized']:shutil.copytree(W/name,OUT/name)
for name in ['stdout.txt','stderr.txt']:shutil.copyfile(W/name,OUT/name)
for name in ['source_manifest.json','control-build-inputs.json']:shutil.copyfile(W/'inputs'/name,OUT/name)
summaries=[json.loads((W/name/'SUMMARY.json').read_text()) for name in ['control-normal','control-sanitized']]
assert all(s['cases']==29 and s['checks']==554 and s['domain']=='PC_CONTROL_DOUBLE_NOT_FPGA' for s in summaries)
manifest=json.loads((W/'inputs/control-build-inputs.json').read_text())
# Source snapshots remain in the queue workdir and will be included in the release.
expected={f'sp_linear_{s}_v1' for s in ['open','load','run','report','unload','close']}
need=[];deps={};artifacts={}
for name in ['libsp_linear_xrt_candidate.so','sp-linear-host']:
    p=W/name;data=command(['readelf','-h','-d','--dyn-syms','--wide',p],OUT/(name+'.elf.json'))
    assert 'AArch64' in data
    assert not re.search(r'\((?:RUNPATH|RPATH)\).*\[(?:/mnt|/home)',data)
    if name.endswith('.so'):
        defined={line.split()[7].split('@')[0] for line in data.splitlines() if len(line.split())>=8 and line.split()[3:6]==['FUNC','GLOBAL','DEFAULT'] and line.split()[6]!='UND'}
        assert expected.issubset(defined)
        raw=p.read_bytes()
        assert b'CONTROL_ONLY' not in raw and b'CONTROL_TEST_DOUBLE' not in raw and b'CONTROL_TEST_ONLY.lock' not in raw
    need+=re.findall(r'Shared library: \[(.*?)\]',data)
    artifacts[name]={'sha256':sha(p),'bytes':p.stat().st_size}
while need:
    n=need.pop()
    if n in deps or n=='libsp_linear_xrt_candidate.so':continue
    p=next((d/n for d in (SDK/'usr/lib',SDK/'lib',SDK/'lib64') if (d/n).is_file()),None)
    assert p is not None,n
    data=command(['readelf','-h','-d',p],OUT/(n+'.dependency.json'))
    assert 'AArch64' in data
    deps[n]={'sdk_relative':str(p.resolve().relative_to(SDK)),'sha256':sha(p)}
    need+=re.findall(r'Shared library: \[(.*?)\]',data)
save(OUT/'REPORT.json',{'status':'PASS_PC_CONTROL_AND_ARM64_BUILD','control':summaries,'artifacts':artifacts,
    'dependencies':deps,'production_stubs_absent':True,'target':'Cortex-A53','ARM_execution':'NOT_TESTED','BOARD':'NOT_TESTED'})
save(OUT/'files.sha256.json',{p.relative_to(OUT).as_posix():sha(p) for p in OUT.rglob('*') if p.is_file()})
print(json.dumps({'control_cases_each':29,'checks_each':554,'dependencies':len(deps),'production_stubs_absent':True,'BOARD':'NOT_TESTED'}))
