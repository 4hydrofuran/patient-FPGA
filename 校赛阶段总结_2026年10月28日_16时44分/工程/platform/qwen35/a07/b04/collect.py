"""Collect real artifacts into a portable PARTIAL delivery, never fabricate missing roles."""
import hashlib,json,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
WORK=Path(sys.argv[1]).resolve()
OUT=ROOT/'release/a07_b04_v1'
E=ROOT/'evidence/A07_B04/v1'
SDK=Path('/home/member-a/kv260-sdk-2026.1-common/sysroots/cortexa72-cortexa53-amd-linux')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(v,f,indent=2,ensure_ascii=False)
def run(argv,p):
    r=subprocess.run(list(map(str,argv)),capture_output=True,text=True)
    save(p,{'argv':list(map(str,argv)),'cwd':str(Path.cwd()),'exit_code':r.returncode,'stdout':r.stdout,'stderr':r.stderr})
    return r
def main():
    import re
    receipt=json.loads((E/'run-retry.json').read_text())
    if receipt['exit_code']!=0:raise ValueError('build not complete')
    q=json.loads(receipt['stdout'])
    if q['exit_code']!=0 or Path(q['cwd']).resolve()!=WORK:raise ValueError('queue/work mismatch')
    inputs=json.loads((WORK/'inputs/source_manifest.json').read_text())
    for name,item in inputs.items():
        if sha(WORK/'inputs'/name)!=item['sha256']:raise ValueError('build snapshot changed')
    shutil.copytree(WORK/'inputs',OUT)
    (OUT/'artifacts').mkdir();(OUT/'reports').mkdir()
    for name in ('libsp_linear_xrt_candidate.so','sp-linear-host'):
        shutil.copyfile(WORK/name,OUT/'artifacts'/name)
    for name in ('stdout.txt','stderr.txt'):shutil.copyfile(WORK/name,OUT/'reports'/name)
    shutil.copyfile(E/'run-retry.json',OUT/'reports/build-command.json')
    for name in ('README.md','DESIGN_GAP.md','link.cfg','link_offline.py','platform_profile.pending.json'):
        shutil.copyfile(Path(__file__).with_name(name),OUT/'platform/qwen35/a07/b04'/name)
    shutil.copyfile(Path(__file__).with_name('README.md'),OUT/'README.md')
    reports=[json.loads(line) for line in (WORK/'stdout.txt').read_text().splitlines() if line.startswith('{')]
    control=[r for r in reports if r.get('domain') in ('PC_HOST_LOGIC_ONLY','PC_ARCHIVED_RTL_META_REPLAY')]
    if len(control)!=4:raise ValueError('required actual test output missing')
    save(OUT/'reports/control.json',{'results':control,'XRT_integration':'NOT_TESTED','BOARD':'NOT_TESTED'})
    expected={'sp_linear_open_v1','sp_linear_load_v1','sp_linear_run_v1','sp_linear_report_v1','sp_linear_unload_v1','sp_linear_close_v1'}
    dependencies={};need=[]
    for name in ('libsp_linear_xrt_candidate.so','sp-linear-host'):
        r=run(['readelf','-h','-d','--dyn-syms','--wide',OUT/'artifacts'/name],OUT/'reports'/(name+'.elf.json'))
        if r.returncode or 'AArch64' not in r.stdout:raise ValueError('wrong ELF')
        if name.endswith('.so'):
            defined={line.split()[7].split('@')[0] for line in r.stdout.splitlines() if len(line.split())>=8 and line.split()[3:6]==['FUNC','GLOBAL','DEFAULT'] and line.split()[6]!='UND'}
            if not expected.issubset(defined):raise ValueError('missing public symbol')
        if re.search(r'\((?:RUNPATH|RPATH)\).*\[(?:/mnt|/home)',r.stdout):raise ValueError('nonportable RPATH')
        need+=re.findall(r'Shared library: \[(.*?)\]',r.stdout)
    while need:
        n=need.pop()
        if n in dependencies or n=='libsp_linear_xrt_candidate.so':continue
        p=next((d/n for d in (SDK/'usr/lib',SDK/'lib',SDK/'lib64') if (d/n).is_file()),None)
        if p is None:raise ValueError('missing SDK dependency '+n)
        r=run(['readelf','-d',p],OUT/'reports'/(n+'.dependency.json'))
        if r.returncode:raise ValueError('bad SDK dependency')
        dependencies[n]={'sdk_relative_path':p.resolve().relative_to(SDK).as_posix(),'sha256':sha(p)}
        need+=re.findall(r'Shared library: \[(.*?)\]',r.stdout)
    save(OUT/'dependency_manifest.json',{'target':'Cortex-A53','SDK':'2026.1 Common','libraries':dependencies,'BOARD':'NOT_TESTED'})
    # Run the real gate. Exit 3 proves blocked precondition, not a v++ attempt.
    gate_dir=OUT/'reports/link-preflight';gate_dir.mkdir()
    cmd=[sys.executable,OUT/'platform/qwen35/a07/b04/link_offline.py','--root',OUT,
        '--platform','/home/member-a/AMDDesignTools/2026.1/Vitis/base_platforms/kv260_base/kv260_base.xpfm',
        '--xo',ROOT/'hw/linear_B_received/B03-supplement-e227297-20261003/payload/artifact/b03_candidate/w4a8_linear_v1.xo']
    r=subprocess.run(list(map(str,cmd)),cwd=gate_dir,capture_output=True,text=True)
    save(gate_dir/'command.json',{'argv':list(map(str,cmd)),'exit_code':r.returncode,'stdout':r.stdout,'stderr':r.stderr})
    if r.returncode!=3:raise ValueError('unexpected gate result; inspect before continuing')
    roles={'public_header':'contracts/qwen35/sp_linear_v1.h','runtime_source':'modules/linear_A/xrt/backend.cpp',
        'build_entry':'platform/qwen35/a07/b04/build_portable.sh','dependency_notes':'README.md',
        'arm64_library':'artifacts/libsp_linear_xrt_candidate.so','arm64_host':'artifacts/sp-linear-host',
        'link_config':'platform/qwen35/a07/b04/link.cfg','platform_profile':'platform/qwen35/a07/b04/platform_profile.pending.json',
        'arm_build_log':'reports/build-command.json','control_test_receipt':'reports/control.json'}
    save(OUT/'a_delivery.json',{'status':'PARTIAL_NOT_A07_OR_B04_ACCEPTED','source_revision':'sha256:'+sha(OUT/'source_manifest.json'),
        'A_base_commit':'ed9df6c7152c908d512ecd1f871583182823e1eb',
        'public_contract_sha256':'83bd402b39350710d8689d50f79296e9625e9c75ccb0ecee145f08067c4ee3b6',
        'kernel_build_id':'0xB3030002','xo_sha256':'96ca2a5825c4e044e0159b7a1553a30d8546cc59ab5cfc9201d6d44d4b7ddd23',
        'artifacts':{k:{'path':v,'sha256':sha(OUT/v)} for k,v in roles.items()},
        'missing_roles':['xclbin','implementation_report','link_log'],
        'pending_tests':['full_XRT_control_fault_injection','ARM_execution','BOARD'],
        'release_gate':'A06_NOT_ACCEPTED','BOARD':'NOT_TESTED'})
    b=OUT/'hw/linear_B_received/B04-scope-9a75600-20261003'
    r=run([sys.executable,b/'tools/b04_a_preflight.py',OUT,'--readelf','/usr/bin/readelf',
        '--receipt',OUT/'reports/B-preflight-receipt.json'],OUT/'reports/B-preflight-command.json')
    if r.returncode==0 or 'A delivery role missing: xclbin' not in r.stderr:raise ValueError('expected B missing-xclbin rejection absent')
    manifest={p.relative_to(OUT).as_posix():{'bytes':p.stat().st_size,'sha256':sha(p)} for p in OUT.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    save(OUT/'files.sha256.json',manifest)
    print(json.dumps({'delivery':str(OUT),'files':len(manifest),'status':'PARTIAL','actual_tests':control,'dependencies':len(dependencies)}))
if __name__=='__main__':main()
