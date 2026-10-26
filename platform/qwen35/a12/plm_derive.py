"""Derived from the already reviewed real backend candidate; parent is untouched."""
from plm_evidence import ROOT,sha
from pl_auth_derive import generate as parent_generate
PARENT_DERIVE_SHA='4deeb77081200f1f900a1ef1b1a07375a1fdc8392e9c7f7a6792b8a200d949af'
EXTRA=r'''
extern "C" int32_t sp_a12_plm_request_v1(sp_linear_context*c,const char*digest)try{
    auto lock=locked(c);if(auto rc=c->life.idle())return rc;
#ifdef SP_LINEAR_CONTROL_TEST
    require(digest);c->authority.bind_request(digest);return SP_OK;
#else
    (void)digest;return SP_UNSUPPORTED;
#endif
}catch(...){const int rc=error();try{auto lock=locked(c);c->authority.fail();c->life.poison();c->last={{"last_status_code",rc},{"output_consumable",false}};}catch(...){}return rc;}
extern "C" int32_t sp_a12_plm_request_end_v1(sp_linear_context*c)try{
    auto lock=locked(c);if(auto rc=c->life.idle())return rc;
#ifdef SP_LINEAR_CONTROL_TEST
    c->authority.end_request();return SP_OK;
#else
    return SP_UNSUPPORTED;
#endif
}catch(...){const int rc=error();try{auto lock=locked(c);c->authority.fail();c->life.poison();c->last={{"last_status_code",rc},{"output_consumable",false}};}catch(...){}return rc;}
#ifdef SP_LINEAR_CONTROL_TEST
extern "C" int32_t sp_a12_plm_test_fault_v1(sp_linear_context*c,const char*mode,uint64_t job)try{
    auto lock=locked(c);require(mode&&job&&job<=5000);c->plm_test_mode=mode;c->plm_test_job=job;return SP_OK;
}catch(...){return error();}
extern "C" int32_t sp_a12_plm_test_inventory_v1(char*out,uint64_t capacity){
    auto s=json({{"domain","PC_XRT_CONTROL_ONLY"},{"stub_starts",control::starts},
        {"stub_allocations",control::allocations},{"stub_live",control::live},{"hardware_done_count",nullptr}}).dump();
    if(!out||capacity<=s.size())return SP_BUFFER_TOO_SMALL;
    std::memcpy(out,s.c_str(),s.size()+1);return SP_OK;
}
#endif
'''
def generate():
    assert sha(ROOT/'platform/qwen35/a12/pl_auth_derive.py')==PARENT_DERIVE_SHA
    text,_=parent_generate();original=text;edits=[]
    def edit(old,new):
        nonlocal text
        assert text.count(old)==1,old;text=text.replace(old,new);edits.append((old,new))
    edit('#include "pl_auth_gate.hpp"','#include "plm_control.hpp"\n#ifdef SP_LINEAR_CONTROL_TEST\n#include "control_xrt.hpp"\n#endif')
    edit('    plauth::Gate authority;','    plm::Control authority;\n#ifdef SP_LINEAR_CONTROL_TEST\n    std::string plm_test_mode;uint64_t plm_test_job=0;\n#endif')
    edit('    std::shared_ptr<sp_linear_context> owner(std::move(c));auto raw=owner.get();',
        '    c->authority.configure(c->authority_facts);\n    std::shared_ptr<sp_linear_context> owner(std::move(c));auto raw=owner.get();')
    edit('        c->authority.before_transfer(job);','''        c->authority.before_transfer(job,t);
#ifdef SP_LINEAR_CONTROL_TEST
        if(c->plm_test_job==job){
            if(c->plm_test_mode=="revoke_claim")c->authority.fail();
            else if(c->plm_test_mode=="nan_y")control::fault="nan_y";
            else if(c->plm_test_mode=="start")control::fault="start";
            else if(c->plm_test_mode=="timeout")control::fault="timeout";
            else if(c->plm_test_mode=="pause_claim")std::this_thread::sleep_for(std::chrono::milliseconds(100));
        }
#endif''')
    edit('    j["a12_hardware_global_completion_counter"]=nullptr;',
        '    j["a12_hardware_global_completion_counter"]=nullptr;\n    j["plm_control"]=c->authority.report();')
    edit('    j["host_verified_completions"]=c->runs;',
        '    j["host_verified_completions"]=c->runs;\n    j["plm_control"]=c->authority.report();')
    edit('    // Remove run\'s previous BO bindings while quiescent before releasing the selected weight.',
        '    if(!c->authority.maintenance_allowed()){c->authority.fail();c->life.poison();c->last={{"last_status_code",SP_POISONED},{"output_consumable",false}};return SP_POISONED;}\n    // Remove run\'s previous BO bindings while quiescent before releasing the selected weight.')
    edit('    require(!c->authority.unknown(),SP_POISONED);',
        '    if(c->authority.unknown()||!c->authority.maintenance_allowed()){c->authority.fail();c->life.poison();c->last={{"last_status_code",SP_POISONED},{"output_consumable",false}};return SP_POISONED;}')
    text+=EXTRA;inverse=text[:-len(EXTRA)]
    for old,new in reversed(edits):assert inverse.count(new)==1;inverse=inverse.replace(new,old)
    assert inverse==original;return text,edits
