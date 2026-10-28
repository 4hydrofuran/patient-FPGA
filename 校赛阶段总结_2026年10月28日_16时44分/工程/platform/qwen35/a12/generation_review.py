"""Independent byte/ABI/derivation checks and a review-only bounded package."""
import hashlib
from pathlib import Path
import re
import subprocess
import zipfile
from generation_evidence import ROOT,OUT,PARENT,read,save,sha,pin

def main():
    b=read(OUT/'BUILD-v3.json');w=Path(b['workspace']);old=read(PARENT/'BUILD-v5.json')
    audit=read(OUT/'model04-AUDIT.json');assert audit['status']=='PASS_SIX_ACTUAL_MODEL_PC_GENERATION_WINDOWS'
    assert read(OUT/'ISSUER_TEST-v2.json')['count']==21
    for label in ('SLOT_TEST-v3','SLOT_SAN-v3'):
        q=read(OUT/(label+'.json'));assert q['exit_code']==0 and q['stdout'].strip()=='PASS_PC_GENERATION_SLOT 22' and not q['stderr']
    for row in b['runtime_artifacts']:assert sha(row['path'])==row['sha256']
    for row in old['runtime_artifacts']:
        if row['role']!='adapter':assert sha(row['path'])==row['sha256']
    assert sha(old['imported_quant_object']['path'])==old['imported_quant_object']['sha256']
    for row in b['generation_source']:assert sha(w/'source'/row['name'])==row['sha256']
    here=ROOT/'platform/qwen35/a12'
    for name in ('generation_slot.hpp','generation_writer.cpp','test_generation_slot.cpp'):assert sha(here/name)==sha(w/'source'/name)
    d=read(OUT/'SOURCE-v3.json');text=(w/'source/generation_cpu.cpp').read_text()
    for before,after in reversed(d['CPU_adapter_reversible_edits']):assert text.count(after)==1;text=text.replace(after,before)
    assert hashlib.sha256(text.encode()).hexdigest()==d['original_CPU_adapter_sha256']
    arm=read(OUT/'ARM_RESULT-v3.json');artifact=Path(arm['artifact']['path']);assert sha(artifact)==arm['artifact']['sha256']
    source=read(OUT/'ARM_SOURCE-v3.json');text=(w/'arm-source/backend.cpp').read_text()
    assert 'return SP_UNSUPPORTED;\n#endif\n    a12::permit("device_open",0);' in text
    for before,after in reversed(source['reversible_edits']):assert text.count(after)==1;text=text.replace(after,before)
    assert hashlib.sha256(text.encode()).hexdigest()==source['original_XRT_backend_sha256']
    assert b'SP_A12_GEN_TEST_STALE_SLOT' not in artifact.read_bytes()
    assert b'SP_A12_GEN_TEST_STALE_SLOT' in Path(b['adapter']).read_bytes()
    symbols=subprocess.run(['readelf','--dyn-syms','--wide',str(artifact)],capture_output=True,text=True,check=True)
    original=Path(read(PARENT/'ARM_BUILD-v5.json')['artifacts'][1]['path'])
    previous=subprocess.run(['readelf','--dyn-syms','--wide',str(original)],capture_output=True,text=True,check=True)
    def abi(text):return sorted(set(re.findall(r'\b(sp_[A-Za-z0-9_]+@@(?:SP_LINEAR_V1|A12_PLM_PRIVATE_V1))\b',text)))
    assert abi(symbols.stdout)==abi(previous.stdout) and len(abi(symbols.stdout))==10
    save(OUT/'ABI_REVIEW.json',dict(status='PASS_PRIVATE_DERIVATION_PUBLIC_SYMBOLS_UNCHANGED',symbols=abi(symbols.stdout),
        CPU_test_seam_absent_from_ARM=True,readelf_command=symbols.args,exit_code=symbols.returncode))
    for row in read(OUT/'BASELINE.json')['files']:assert sha(ROOT/row['path'])==row['sha256']
    probe=ROOT/'evidence/model_pl_A/20261025-resource-probe-v1/bundle-v2.zip'
    assert sha(probe)=='acd578ddd66140a3d0507d71ea9a1d30245c632c7537f0a940227935cc17a7fa'
    protected_contract=ROOT/'contracts/qwen35/sp_linear_v1.h'
    assert sha(protected_contract)=='d97e544444b8566a32d0bd25e67e2e548f71678ac6e63ac63e96aa415b1a76f9'
    # Review package deliberately needs the pinned repository/runtime dependencies.
    files={}
    for p in sorted(here.iterdir()):
        if p.is_file() and p.name.startswith(('generation_','test_generation_')):files['source/'+p.name]=p.read_bytes()
    files['pc/liba12_native_cpu_control.so']=Path(b['adapter']).read_bytes()
    files['pc/liba12_generation_writer.so']=Path(b['generation_writer']).read_bytes()
    files['arm/liba12_generation_xrt_unbound.so']=artifact.read_bytes()
    files['contracts/sp_linear_v1.h']=protected_contract.read_bytes()
    for name in ('BUILD-v3.json','ARM_RESULT-v3.json','model04-AUDIT.json','ISSUER_TEST-v2.json','ABI_REVIEW.json'):
        files['review/'+name]=(OUT/name).read_bytes()
    files['README.txt']=('OFFLINE REVIEW ONLY. NOT STANDALONE OR DEPLOYABLE.\n'
        'PC generation fixture only; no live Board issuer exists. ARM device_open remains hard-disabled.\n'
        'Requires the frozen repository, original native executable, CPU/math DSOs, model and sidecars identified by BUILD-v3.json.\n'
        'Original ordinary bundle-v2.zip remains the first future Board resource probe after recovery, release and separate authorization.\n'
        'No weights, bitstream, install/recovery/Board execution scripts are included.\n').encode()
    members=[dict(name=name,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()) for name,data in sorted(files.items())]
    archive=OUT/'generation-consumer-offline-unbound-v1.zip'
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for name,data in files.items():z.writestr(name,data)
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None and set(z.namelist())==set(files)
        for row in members:assert hashlib.sha256(z.read(row['name'])).hexdigest()==row['sha256']
    save(OUT/'PACKAGE_REVIEW.json',dict(status='PASS_REVIEW_ONLY_ZIP_ROUNDTRIP',archive=pin(archive),members=members,standalone=False,deployable=False))
    save(OUT/'ARTIFACT_REVIEW.json',dict(status='PASS_PC_NATIVE_GENERATION_CONSUMER_AND_A53_COMPILE_ONLY',
        runtime_artifacts=b['runtime_artifacts'],generation_writer=dict(path=b['generation_writer'],sha256=sha(b['generation_writer'])),ARM_artifact=arm['artifact'],
        math_recompiled=False,quantization_recompiled=False,original_front_unchanged=True,public_ABI_unchanged=True,
        existing_4096_page_bytes_used=384,extra_CMA_BO_allocated=False,BOARD='NOT_TESTED',actual_Board_CMA=None,
        live_Board_generation_issuer='NOT_IMPLEMENTED',PL_mode_coordinator='NOT_IMPLEMENTED',real_PL_results_consumed=False))
    print('PASS_PC_NATIVE_GENERATION_CONSUMER_AND_A53_COMPILE_ONLY')
if __name__=='__main__':main()
