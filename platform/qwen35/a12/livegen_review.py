"""Review current native bytes, frozen-gate derivations and review-only package."""
import hashlib
from pathlib import Path
import re
import subprocess
import zipfile
from livegen_evidence import ROOT,OUT,PARENT,read,save,sha,pin

def main():
    b=read(OUT/'BUILD-v2.json');w=Path(b['workspace']);source=read(OUT/'SOURCE-v2.json')
    assert read(OUT/'SOURCE_TEST-v6.json')['count']==33
    assert read(OUT/'IMPORT_REVIEW-v6.json')['status']=='PASS_PRIVATE_FROZEN_GATE_IMPORT_NO_BOARD_OBJECTS_OR_IO'
    assert read(OUT/'PYTHON_OPTIMIZE_REFUSAL-v6.json')['exit_code']==0
    assert read(OUT/'model03-AUDIT.json')['status']=='PASS_FIVE_ACTUAL_MODEL_LIVE_SOURCE_WINDOWS'
    counterexample=read(OUT/'OPATH_RELEASE_COUNTEREXAMPLE.json')
    assert counterexample['status']=='PASS_ORIGINAL_RELEASE_GATE_WITHOUT_OBSERVER_EXEMPTION'
    assert counterexample['records'][0]['original_release_refusal']=='ACCELERATOR_DESCRIPTOR_STILL_OPEN'
    assert counterexample['records'][1]['original_release_refusal'] is None and counterexample['records'][2]['worker_exit_code']==7
    assert read(OUT/'PIN_CONCURRENCY_TEST.json')['status']=='PASS_REVOCATION_BEFORE_CLEANUP_LOCK_AND_NO_FD_REUSE_DAMAGE'
    for name in ('NATIVE_TEST-v2','NATIVE_SAN-v2'):
        r=read(OUT/(name+'.json'));assert r['exit_code']==0 and r['stdout'].strip()=='PASS_PC_GENERATION_SLOT 22' and not r['stderr']
    for row in b['runtime_artifacts']+b['manager_artifacts']:assert sha(row['path'])==row['sha256']
    assert sha(b['imported_quant_object']['path'])==b['imported_quant_object']['sha256']
    for row in source['source']:assert sha(w/'source'/row['name'])==row['sha256']
    header=(w/'source/generation_slot.hpp').read_text()
    for old,new in reversed(source['header_reversible_edits']):assert header.count(new)==1;header=header.replace(new,old)
    assert hashlib.sha256(header.encode()).hexdigest()==source['original_header_sha256']
    writer=(w/'source/generation_writer.cpp').read_text();assert writer.endswith(source['writer_append'])
    assert hashlib.sha256(writer[:-len(source['writer_append'])].encode()).hexdigest()==source['original_writer_sha256']
    # Native consumers and all mathematics are the already validated binaries.
    old=read(PARENT/'BUILD-v3.json')
    assert b['runtime_artifacts']==old['runtime_artifacts']
    arm_consumer=read(PARENT/'ARM_RESULT-v3.json')['artifact'];assert sha(arm_consumer['path'])==arm_consumer['sha256']
    original_backend=Path(old['workspace'])/'arm-source/backend.cpp'
    assert 'return SP_UNSUPPORTED;\n#endif\n    a12::permit("device_open",0);' in original_backend.read_text()
    assert sha(original_backend)==read(PARENT/'ARM_SOURCE-v3.json')['derived_sha256']
    exports=[];dependencies=[]
    for row in b['manager_artifacts']:
        nm=subprocess.run(['nm','-D','--defined-only',row['path']],capture_output=True,text=True,check=True)
        names={line.split()[-1] for line in nm.stdout.splitlines()}
        assert names=={'a12_gen_open_v1','a12_gen_health_v1','a12_gen_bind_v1','a12_gen_resident_v1','a12_gen_revoke_v1','a12_gen_close_v1','a12_livegen_board_open_v1'}
        dynamic=subprocess.run(['readelf','-d',row['path']],capture_output=True,text=True,check=True)
        needed=re.findall(r'Shared library: \[([^]]+)\]',dynamic.stdout);assert not any('xrt' in x.lower() for x in needed)
        exports.append(dict(artifact=row,symbols=sorted(names)));dependencies.append(dict(path=row['path'],needed=needed))
    for row in read(OUT/'BASELINE.json')['files']+read(OUT/'BASELINE.json')['original_gate_sources']:assert sha(ROOT/row['path'])==row['sha256']
    probe=ROOT/'evidence/model_pl_A/20261025-resource-probe-v1/bundle-v2.zip'
    assert sha(probe)=='acd578ddd66140a3d0507d71ea9a1d30245c632c7537f0a940227935cc17a7fa'
    contract=ROOT/'contracts/qwen35/sp_linear_v1.h';assert sha(contract)=='d97e544444b8566a32d0bd25e67e2e548f71678ac6e63ac63e96aa415b1a76f9'
    review=dict(status='PASS_LIVE_SOURCE_PREPARATION_PC_BINDING_A53_ISSUER_COMPILE_ONLY',runtime_artifacts=b['runtime_artifacts'],manager_artifacts=b['manager_artifacts'],
        ARM_consumer=arm_consumer,manager_exports=exports,manager_dependencies=dependencies,manager_maps_XRT=False,
        original_native_CPU_XRT_consumers_unchanged=True,math_recompiled=False,quantization_recompiled=False,public_contract_unchanged=True,
        original_gate_AST_inverse_checked=True,extra_CMA_BOs=0,private_page_used_bytes=384,
        actual_Board_owner_ports_execution='NOT_TESTED',current_Board_source_bound=False,current_Board_lease_acquired=False,
        ARM_execution='NOT_EXECUTED',current_XRT_device_open='HARD_DISABLED',PL_mode='NOT_IMPLEMENTED',BOARD='NOT_TESTED',
        observer_release_counterexample_and_fix=True,observer_cleanup_follows_native_revoke=True,
        rejected_old_archive_sha256=counterexample['rejected_old_review_archive_sha256'],old_archive_status='NOT_ACCEPTED_FOR_RELEASE_INTERLOCK')
    save(OUT/'ARTIFACT_REVIEW-v2.json',review)
    files={};here=ROOT/'platform/qwen35/a12'
    for p in sorted(here.iterdir()):
        if p.is_file() and p.name.startswith(('livegen_','test_livegen_')):files['source/'+p.name]=p.read_bytes()
    for name in ('BUILD-v2.json','SOURCE_TEST-v6.json','IMPORT_REVIEW-v6.json','model03-AUDIT.json','ARTIFACT_REVIEW-v2.json',
        'OPATH_RELEASE_COUNTEREXAMPLE.json','PIN_CONCURRENCY_TEST.json'):
        files['review/'+name]=(OUT/name).read_bytes()
    files['pc/liba12_livegen_writer.so']=Path(b['manager_artifacts'][0]['path']).read_bytes()
    files['arm/liba12_livegen_writer_a53.so']=Path(b['manager_artifacts'][1]['path']).read_bytes()
    files['README.txt']=('OFFLINE REVIEW ONLY, NOT STANDALONE OR DEPLOYABLE.\n'
        'Prepared Board source requires the verified original Owner, exact ARM64 machine/kernel, actual lease/dual locks and interlocked original Platform.\n'
        'No Board source was instantiated, no Board approval/lease acquired, no ARM binary executed.\n'
        'The unchanged XRT consumer still refuses device_open; first future Board test remains unchanged ordinary bundle-v2.zip after separate recovery/release/authorization.\n'
        'PC model results use CPU mathematics and explicitly synthetic device/CMA policy fixtures. Never hardware evidence.\n'
        'No weights, model, sidecars, bitstream, install/recovery/Board execution scripts are included.\n').encode()
    members=[dict(name=n,bytes=len(v),sha256=hashlib.sha256(v).hexdigest()) for n,v in sorted(files.items())]
    archive=OUT/'live-owner-source-offline-unbound-v2.zip'
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for name,data in files.items():z.writestr(name,data)
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None and set(z.namelist())==set(files)
        for row in members:assert hashlib.sha256(z.read(row['name'])).hexdigest()==row['sha256']
    save(OUT/'PACKAGE_REVIEW-v2.json',dict(status='PASS_REVIEW_ONLY_ZIP_ALL_MEMBERS',archive=pin(archive),members=members,standalone=False,deployable=False))
    print(review['status'])
if __name__=='__main__':main()
