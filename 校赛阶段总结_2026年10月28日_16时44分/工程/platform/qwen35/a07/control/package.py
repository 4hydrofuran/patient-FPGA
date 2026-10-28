"""Assemble a self-contained A07 handoff only after actual offline review passes."""
import argparse,hashlib,json,shutil,subprocess
from pathlib import Path
R=Path(__file__).resolve().parents[4]
E=R/'evidence/A07_closeout/20261004-v1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v,replace=False):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('w' if replace else 'x') as f:json.dump(v,f,indent=2)
def copy(src,dst):
    dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--control',type=Path,required=True)
    ap.add_argument('--link',type=Path,required=True);ap.add_argument('--audit',type=Path,required=True)
    a=ap.parse_args();out=R/'release/a07_b04_v3'
    review=json.loads((a.audit/'REVIEW.json').read_text())
    assert review['status']=='PASS_OFFLINE_IMPLEMENTATION_REVIEW'
    arm=json.loads((E/'control-v2/REPORT.json').read_text())
    assert arm['status']=='PASS_PC_CONTROL_AND_ARM64_BUILD'
    source=json.loads((R/'hw/linear_A/KERNEL_SOURCE.json').read_text())
    assert source['accepted'] is True and source['frozen'] is True
    assert json.loads((a.link/'link.json').read_text())['exit_code']==0
    assert sha(a.link/'w4a8.xclbin')==review['xclbin_sha256']
    # Compiled source identity, not the current README, is required to match.
    for name in ['backend.cpp','host_contract.cpp','host_contract.hpp','release_gate.hpp','host.cpp']:
        assert sha(R/'modules/linear_A/xrt'/name)==sha(a.control/'inputs/modules/linear_A/xrt'/name),name
    assert not out.exists()
    shutil.copytree(a.control/'inputs',out,ignore=shutil.ignore_patterns('__pycache__'))
    # Preserve exact build manifests before regenerating a delivery source manifest.
    (out/'source_manifest.json').rename(out/'original_build_source_manifest.json')
    copy(R/'hw/linear_A/KERNEL_SOURCE.json',out/'hw/linear_A/KERNEL_SOURCE.json')
    copy(R/'modules/linear_A/xrt/README.md',out/'modules/linear_A/xrt/README.md')
    lock=json.loads((R/'contracts/qwen35/contracts.lock').read_text())
    for name,digest in lock['files'].items():
        assert sha(R/'contracts/qwen35'/name)==digest
        copy(R/'contracts/qwen35'/name,out/'contracts/qwen35'/name)
    copy(R/'contracts/qwen35/contracts.lock',out/'contracts/qwen35/contracts.lock')
    for p in (R/'platform/qwen35/a07/control').iterdir():
        if p.is_file():copy(p,out/'platform/qwen35/a07/control'/p.name)
    for name in ['link_offline.py','link.cfg','build_portable.sh']:
        copy(R/'platform/qwen35/a07/b04'/name,out/'platform/qwen35/a07/b04'/name)
    copy(R/'platform/qwen35/a07/control/DELIVERY_README.md',out/'README.md')
    for name,item in arm['artifacts'].items():
        assert sha(a.control/name)==item['sha256'];copy(a.control/name,out/'artifacts'/name)
    copy(a.link/'w4a8.xclbin',out/'artifacts/w4a8.xclbin')
    for kind,item in review['matching_files'].items():
        p=Path(item['path']);assert sha(p)==item['sha256']
        copy(p,out/'artifacts'/('MPSoC_ext_platform.'+kind))
    shutil.copytree(E/'control-v2',out/'reports/control')
    shutil.copytree(a.audit,out/'reports/implementation',ignore=shutil.ignore_patterns('*.jou','*.log'))
    for name in ['link.json','vpp-version.json','platforminfo.json','link-gate.json','artifact.json','xclbin-info.json','v++_w4a8.log']:
        copy(a.link/name,out/'reports/link'/name)
    for name in ['control-v2-run.json','control-v2-submit.json','pc-openssl.json','run.json','interface-resume.json','csim-run.json','link-submit.json','link-run.json','audit-run.json','audit-v2-run.json','audit-v3-run.json','implementation-review.json']:
        copy(E/name,out/'reports/commands'/name)
    for name in ['run.json','audit-run.json','audit-v2-run.json']:
        receipt=json.loads((E/name).read_text());job=json.loads(receipt['stdout'])
        assert job['status']=='FAILED'
        work=Path(job['cwd']);dest=out/'reports/preserved-failures'/job['job']
        for log in ['stdout.txt','stderr.txt']:copy(work/log,dest/log)
        if (work/'audit').is_dir():shutil.copytree(work/'audit',dest/'audit')
    copy(E/'A06_ACCEPTED.json',out/'reports/A06_ADDENDUM.json')
    for p in (R/'evidence/A06_acceptance/final-20261004-v1').iterdir():
        if p.is_file():copy(p,out/'reports/A06'/p.name)
    shutil.copytree(R/'evidence/A06_acceptance/final-20261004-v1/csim',out/'reports/A06/csim')
    # Retain prior host/meta evidence, not an obsolete binary or the entire old project.
    old=R/'release/a07_b04_v1/reports'
    for name in ['stdout.txt','stderr.txt','control.json','build-command.json','B-preflight-command.json']:
        copy(old/name,out/'reports/previous-v1'/name)
    modelroot=R/'platform/build/a07-independent-a53-v2'
    modelmanifest=json.loads((modelroot/'manifest.json').read_text())
    for name,meta in modelmanifest['files'].items():
        if name.endswith('libsp_linear_xrt_candidate.so') or name.endswith('host-test-a53'):continue
        assert sha(modelroot/name)==meta['sha256'],name
        copy(modelroot/name,out/'model_arm64'/name)
    save(out/'model_arm64/manifest.json',{'status':'REUSED_VALID_A53_CPU_MODEL_BUILD_NOT_ARM_EXECUTION',
        'original_manifest_sha256':sha(modelroot/'manifest.json'),'llama_commit':modelmanifest['llama_base_commit'],
        'source':modelmanifest['source'],'BOARD':'NOT_TESTED',
        'files':{p.relative_to(out/'model_arm64').as_posix():sha(p) for p in (out/'model_arm64').rglob('*') if p.is_file()}})
    copy(R/'evidence/A07_independent/preboard-v1/REPORT.md',out/'reports/previous-model-build.md')
    for name in ['preboard_readiness.json','kria_2026_1_image_candidate.json','offline_link_inputs.json']:
        copy(R/'platform/a1'/name,out/'platform/history'/name)
    profile=json.loads((R/'platform/qwen35/a07/b04/platform_profile.pending.json').read_text())
    profile.update(xclbin_sha256=review['xclbin_sha256'],xclbin_uuid=review['xclbin_uuid'],
        offline_implementation='PASS',logical_argument_groups=review['logical_argument_groups'])
    save(out/'platform/qwen35/a07/b04/platform_profile.pending.json',profile,replace=True)
    save(out/'dependency_manifest.json',{'target':'Cortex-A53','libraries':arm['dependencies'],'BOARD':'NOT_TESTED'})
    sources={p.relative_to(out).as_posix():sha(p) for folder in ['modules','platform/qwen35','contracts','third_party','hw/linear_A'] for p in (out/folder).rglob('*') if p.is_file()}
    save(out/'source_manifest.json',sources)
    roles={'public_header':'contracts/qwen35/sp_linear_v1.h','runtime_source':'modules/linear_A/xrt/backend.cpp',
        'build_entry':'platform/qwen35/a07/b04/build_portable.sh','dependency_notes':'README.md',
        'xclbin':'artifacts/w4a8.xclbin','arm64_library':'artifacts/libsp_linear_xrt_candidate.so',
        'arm64_host':'artifacts/sp-linear-host','link_config':'platform/qwen35/a07/b04/link.cfg',
        'platform_profile':'platform/qwen35/a07/b04/platform_profile.pending.json',
        'implementation_report':'reports/implementation/REVIEW.json','link_log':'reports/link/link.json',
        'arm_build_log':'reports/commands/control-v2-run.json','control_test_receipt':'reports/control/REPORT.json'}
    save(out/'a_delivery.json',{'status':'A07_OFFLINE_COMPLETE_PENDING_CLEAN_PACKAGE_CHECK',
        'source_revision':'sha256:'+sha(out/'source_manifest.json'),
        'public_contract_sha256':lock['contract_sha256'],'public_header_sha256':sha(out/roles['public_header']),'kernel_build_id':source['selected_build_id'],
        'xo_sha256':source['xo_sha256'],'artifacts':{k:{'path':v,'sha256':sha(out/v)} for k,v in roles.items()},
        'missing_roles':[],'B04_joint_signoff':'NOT_CLAIMED','BOARD':'NOT_TESTED'})
    b=out/'hw/linear_B_received/B04-scope-9a75600-20261003'
    argv=['python3',str(b/'tools/b04_a_preflight.py'),str(out),'--readelf','/usr/bin/readelf','--receipt',str(out/'reports/B-preflight-receipt.json')]
    q=subprocess.run(argv,capture_output=True,text=True)
    save(out/'reports/B-preflight-command.json',{'argv':argv,'exit_code':q.returncode,'stdout':q.stdout,'stderr':q.stderr})
    assert q.returncode==0
    save(out/'files.sha256.json',{p.relative_to(out).as_posix():{'bytes':p.stat().st_size,'sha256':sha(p)} for p in out.rglob('*') if p.is_file() and '__pycache__' not in p.parts})
    print(json.dumps({'package':str(out),'B_preflight_exit':q.returncode,'BOARD':'NOT_TESTED'}))
if __name__=='__main__':main()
