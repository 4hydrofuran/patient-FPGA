"""Independent artifact/source/export audit of the unbound PL candidate."""
import re
import subprocess
from pathlib import Path
from pl_auth_evidence import ROOT,OUT,WORK,BUNDLE,read,save,sha,pin
from pl_auth_derive import generate,PARENT_SHA

def main():
    work=WORK.with_name(WORK.name[:-1]+'4');src=work/'source';arm=work/'arm-source'
    receipt=read(OUT/'ARTIFACTS-v4.json');snapshot=read(OUT/'SNAPSHOT-v4.json')
    for row in snapshot['source']:assert sha(src/row['name'])==row['sha256'],row['name']
    for row in snapshot['inputs']:assert sha(row['origin'])==row['sha256'],row['origin']
    text,edits=generate();assert text==(src/'backend.cpp').read_text()
    for name in ('pl_auth_gate.hpp','test_pl_auth.cpp','pl_auth_portable_probe.cpp'):
        assert sha(ROOT/'platform/qwen35/a12'/name)==sha(src/name)
    for p in arm.iterdir():
        other=src/p.name if p.name!='sp_abi.map' else BUNDLE/'source/sp_abi.map'
        assert sha(p)==sha(other)
    assert 'SP_LINEAR_CONTROL_TEST' not in (work/'cross-build.sh').read_text()
    assert '-march=native' not in (work/'cross-build.sh').read_text()
    assert '-mcpu=cortex-a53' in (work/'cross-build.sh').read_text()
    assert text.index('DeviceLock device_lock;')<text.index('std::unique_ptr<Weight> pending;')
    assert text.index('xrt::device device;')<text.index('std::unique_ptr<Weight> pending;')<text.index('xrt::bo x,sx,y,meta;')
    assert text.index('return SP_UNSUPPORTED;\n#endif\n    a12::permit("device_open",0);')<text.index('c->device=xrt::device')
    assert text.index('c->authority.before_transfer(job);')<text.index('c->x.sync(XCL_BO_SYNC_BO_TO_DEVICE')
    assert 'c->authority.before_start(job);\n        c->run.start();' in text
    assert text.index('a07::output(a,result,a.y)')<text.index('c->authority.complete(job);')<text.index('std::memcpy(y,result,a.y)')
    assert text.count('c->run.start();')==1
    # The last-check/start gap cannot be eliminated by host atomics. Test it explicitly.
    late=read(OUT/'PC_CASE-v4-start_entry_revoke.json');assert late['exit_code']==0
    normal=read(OUT/'PC_SUMMARY-v4.json');san=read(OUT/'SANITIZED_SUMMARY-v4.json')
    assert len(normal['cases'])==41 and normal['cases']==san['cases']
    assert read(OUT/'PC_BUILD-v4.json')['stderr']==''
    assert read(OUT/'SANITIZED_BUILD-v4.json')['stderr']==''
    for prefix in ('PC','SANITIZED'):
        for case in normal['cases']:
            r=read(OUT/f'{prefix}_CASE-v4-{case["case"]}.json');assert r['exit_code']==0
            assert 'AddressSanitizer' not in r['stderr'] and 'runtime error:' not in r['stderr']
    for key,hkey in [('arm_library','arm_sha256'),('arm_full_gate_object','arm_full_gate_object_sha256')]:
        assert sha(receipt[key])==receipt[hkey]
    def capture(argv):
        r=subprocess.run(argv,capture_output=True,text=True);assert r.returncode==0,r.stderr
        return dict(command=argv,exit_code=r.returncode,stdout=r.stdout,stderr=r.stderr)
    dyn=capture(['nm','-D','--defined-only',receipt['arm_library']])
    exports={line.split()[-1].split('@@')[0] for line in dyn['stdout'].splitlines() if line.strip()}
    allowed={'SP_LINEAR_V1','sp_linear_open_v1','sp_linear_load_v1','sp_linear_run_v1','sp_linear_report_v1',
        'sp_linear_unload_v1','sp_linear_close_v1','sp_a12_completion_report_v1'}
    assert exports==allowed,exports
    elf=capture(['readelf','-h','-d','-Ws',receipt['arm_library']]);assert 'AArch64' in elf['stdout']
    assert 'libatomic' not in elf['stdout'] and not re.search(r'UND\s+__atomic_',elf['stdout'])
    obj=capture(['readelf','-h','-s',receipt['arm_full_gate_object']]);assert 'AArch64' in obj['stdout']
    raw=read(OUT/'ARM_BUILD-v4.json');assert raw['exit_code']==0
    assert '__aarch64_cas8_acq_rel' in raw['stdout'] and '__aarch64_ldset8_acq_rel' in raw['stdout']
    # Preserve actual SDK/runtime header and library identities; this is not a board compatibility assertion.
    sdk=Path('/home/member-a/kv260-sdk-2026.1-common/sysroots/cortexa72-cortexa53-amd-linux')
    needs=re.findall(r'Shared library: \[([^]]+)\]',elf['stdout']);deps=[]
    for name in needs:
        matches=[p for base in ('usr/lib','lib') for p in (sdk/base).glob(name) if p.is_file()]
        assert matches,name;p=matches[0].resolve();deps.append(dict(name=name,path=str(p),sha256=sha(p),bytes=p.stat().st_size))
    save(OUT/'ARTIFACT_REVIEW.json',dict(status='PASS_OFFLINE_XRT_DERIVATIVE_PC_FAULTS_AND_A53_COMPILE',
        revision=4,PC_cases=41,PC_assertions=normal['checks'],ASAN_UBSAN_cases=41,
        derived_source_sha256=sha(src/'backend.cpp'),parent_backend_sha256=PARENT_SHA,derivation_inverse_exact=True,
        source_matches_current=True,public_exports=sorted(exports),dynamic_symbols=dyn,ARM_header_and_symbols=elf,
        ARM_full_gate_object=obj,SDK_dependencies=deps,ARM_runtime='NOT_EXECUTED',
        ARM_production_activation='HARD_DISABLED_BEFORE_DEVICE_OPEN',
        caller_Y_on_fault='UNCHANGED',unknown_DMA_or_upload='POISONED_OWNERS_RETAINED_NO_RELEASE',
        late_revoke_after_final_check='ONE_START_INTENT_POSSIBLE_OUTPUT_REJECTED_OWNERS_RETAINED',
        BOARD='NOT_TESTED',production_enabled=False,hardware_latency_s=None,
        real_manager_protocol='NOT_IMPLEMENTED',real_device_generation_approval='UNBOUND',
        PL_microbatch_grant_integration='NOT_IMPLEMENTED',B_HLS_or_public_math_ABI_changed=False))
    print('PASS_OFFLINE_XRT_DERIVATIVE_PC_FAULTS_AND_A53_COMPILE')
if __name__=='__main__':main()
