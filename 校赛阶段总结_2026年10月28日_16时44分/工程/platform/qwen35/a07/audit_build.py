"""Collect actual ARM build receipts, ISA flags, ELF dependency closure and input identities."""
import hashlib,json,re,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
E=ROOT/'evidence/A07_independent/preboard-v1'
label=sys.argv[1] if len(sys.argv)>1 else 'v1'
assert re.fullmatch(r'v[0-9]+',label)
OUT=E/('artifact-audit-'+label)
SDK=Path('/home/member-a/kv260-sdk-2026.1-common')
SYS=SDK/'sysroots/cortexa72-cortexa53-amd-linux'

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def new(p,obj):
    with p.open('x',encoding='utf-8') as f:json.dump(obj,f,ensure_ascii=False,indent=2)
def cmd(argv):
    p=subprocess.run(argv,text=True,capture_output=True)
    r={'argv':argv,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
    commands.append(r)
    new(OUT/f'command-{len(commands):03}.json',r)
    if p.returncode:raise RuntimeError(f'command failed: {argv}')
    return p.stdout
def receipt(name):
    r=json.loads((E/name).read_text());assert r['exit_code']==0
    q=json.loads(r['stdout']);assert q['exit_code']==0
    return Path(q['cwd']),q

OUT.mkdir(exist_ok=False);commands=[]
cross,cr=receipt('cross-v2-run.json');host,hr=receipt('host-v2-run.json')
for kind,work,r in [('cross',cross,cr),('host',host,hr)]:
    (OUT/kind).mkdir()
    for n in ('stdout.txt','stderr.txt'):shutil.copy2(work/n,OUT/kind/n)
    new(OUT/kind/'queue-receipt.json',r)
    new(OUT/kind/'input-sha256.json',json.loads((work/'inputs/sha256.json').read_text()))

# Only the explicitly modified source snapshots are consulted, not any B/C workspace.
source=Path('/home/member-a/qwen35-a05/source-v3')
patch=json.loads((ROOT/'eval/qwen35/a05/batch-fix-v1/attention-source-patch.json').read_text())
assert sha(source/'ggml/src/ggml-cpu/ops.cpp')==patch['after_sha256']
patch=json.loads((ROOT/'eval/qwen35/a05/batch-fix-v1/source-patch.json').read_text())
assert sha(source/'src/llama-graph.cpp')==patch['new_graph_sha256']
compile_rows=[]
for part in ('llama','s1'):
    rows=json.loads((cross/part/'compile_commands.json').read_text())
    shutil.copy2(cross/part/'compile_commands.json',OUT/f'{part}-compile-commands.json')
    shutil.copy2(cross/part/'CMakeCache.txt',OUT/f'{part}-CMakeCache.txt')
    for row in rows:
        command=row['command']
        assert '-mcpu=cortex-a53' in command
        assert not re.search(r'-(?:march|mcpu)=native|cortex-a72|\+(?:dotprod|i8mm|sve|fp16)',command),command
        compile_rows.append({'file':row['file'],'sha256':sha(Path(row['file']))})
cache=(cross/'llama/CMakeCache.txt').read_text()
assert 'GGML_NATIVE:BOOL=OFF' in cache and 'GGML_CPU_ARM_ARCH:STRING=armv8-a' in cache
new(OUT/'compiled-source-sha256.json',compile_rows)

artifacts=[cross/'s1/qwen35-s1',cross/'s1/libsp_linear_cpu.so',host/'libsp_linear_xrt_candidate.so',host/'host-test-a53']
artifacts += [p for p in (cross/'llama/bin').glob('*.so.*') if not p.is_symlink()]
elf={};local={p.name:p for p in artifacts}
def inspect_elf(p):
    h=cmd(['readelf','-h',str(p)]);assert re.search(r'Machine:\s+AArch64',h),p
    dynamic=cmd(['readelf','-d',str(p)])
    needed=re.findall(r'\(NEEDED\).*\[(.*?)\]',dynamic)
    soname=re.findall(r'\(SONAME\).*\[(.*?)\]',dynamic)
    runpath=re.findall(r'\((?:RUNPATH|RPATH)\).*\[(.*?)\]',dynamic)
    assert not any('/home/' in s or '/mnt/' in s for s in runpath),runpath
    versions=cmd(['readelf','-V',str(p)])
    return {'sha256':sha(p),'bytes':p.stat().st_size,'needed':needed,'soname':soname,'runpath':runpath,'version_information':versions}
for p in artifacts:
    elf[p.name]=inspect_elf(p)
    for name in elf[p.name]['soname']:local[name]=p

dependencies={};pending=[n for v in elf.values() for n in v['needed']]
while pending:
    name=pending.pop()
    if name in dependencies:continue
    if name in local:
        dependencies[name]={'kind':'project','path':str(local[name]),'sha256':sha(local[name])};continue
    found=next((p for p in (SYS/'usr/lib'/name,SYS/'lib'/name,SYS/'lib64'/name) if p.is_file()),None)
    assert found is not None,('missing SDK dependency',name)
    real=found.resolve();assert real.is_relative_to(SYS)
    v=inspect_elf(real);dependencies[name]={'kind':'sdk','path':str(real),'sha256':v['sha256'],'needed':v['needed']}
    pending+=v['needed']

# Compare the SDK dependencies to the already downloaded Common rootfs, without mount or writes to the image.
debugfs=Path('/home/member-a/kv260-build/e2fsprogs-1.47.3-audit/build/debugfs/debugfs')
rootfs=Path('/home/member-a/kv260-build/common-audit-20260927/rootfs.ext4')
(OUT/'rootfs-libraries').mkdir()
rootfs_checks=[];seen=set()
for name,item in dependencies.items():
    if item['kind']!='sdk' or item['path'] in seen:continue
    seen.add(item['path']);p=Path(item['path']);image_path='/'+p.relative_to(SYS).as_posix()
    target=OUT/'rootfs-libraries'/p.name
    text=cmd([str(debugfs),'-R',f'dump {image_path} {target}',str(rootfs)])
    matched=target.is_file() and sha(target)==item['sha256']
    rootfs_checks.append({'path':image_path,'sdk_sha256':item['sha256'],'rootfs_sha256':sha(target) if target.exists() else None,'matched':matched})
assert all(x['matched'] for x in rootfs_checks),rootfs_checks

# Keep only a local staging directory, never an install command or automatically distributed package.
package=ROOT/('platform/build/a07-independent-a53-'+label)
package.mkdir(exist_ok=False);bins=package/'bin';bins.mkdir()
for p in artifacts:shutil.copy2(p,bins/p.name)
for name,p in local.items():
    if not (bins/name).exists():shutil.copy2(p,bins/name)
shutil.copy2(source/'LICENSE',package/'llama.cpp.LICENSE')
new(package/'manifest.json',{'status':'CROSS_COMPILED_NOT_BOARD_TESTED','default_backend_changed':False,
    'llama_base_commit':'81e39ad34368329b5db77620721510fd91107e80','source':'A05 source-v3, unchanged',
    'files':{p.relative_to(package).as_posix():{'sha256':sha(p),'bytes':p.stat().st_size} for p in package.rglob('*') if p.is_file()},
    'dependencies':dependencies,'BOARD':'NOT_TESTED','boot_bundle_verified':False})
symbols=cmd(['readelf','--dyn-syms','--wide',str(host/'libsp_linear_xrt_candidate.so')])
for name in ('open','load','run','report','unload','close'):assert re.search(r'\bsp_linear_'+name+r'_v1\b',symbols)
tests=[json.loads(line) for line in (host/'stdout.txt').read_text().splitlines() if line.startswith('{"domain":')]
assert len(tests)==2 and all(t['device_calls']==0 for t in tests)
report={'status':'PASS_INDEPENDENT_COMPILE_AND_HOST_GUARDS_ONLY','compile_translation_units':len(compile_rows),
    'host_tests':tests,'elf':elf,'dependency_closure':dependencies,'rootfs_sdk_checks':rootfs_checks,
    'staging':str(package),'model_changed':False,'default_backend_changed':False,
    'BOARD':'NOT_TESTED','target_execution':'NOT_TESTED','xclbin':None,'boot_bundle_verified':False,
    'budget_bytes':None,'hardware_error':None,'commands':commands}
new(OUT/'REPORT.json',report)
print(json.dumps({'status':report['status'],'translation_units':len(compile_rows),'rootfs_matches':len(rootfs_checks),
    'host_checks':tests[0]['assertions'],'artifacts':len(artifacts),'BOARD':'NOT_TESTED'}))
