"""Exact, reversible edits of the frozen ordinary real-XRT backend only."""
from pl_auth_evidence import BUNDLE,sha

PARENT_SHA='bb0d6f439239606b79acbca541d28be9e63db5e7d882f7bcd8413dfa0dbd062c'
EXTRA=r'''
// Private diagnostic identity, not a device-generation approval or release proof.
extern "C" int32_t sp_a12_pl_candidate_context_v1(sp_linear_context*c,char*dst,uint64_t cap,uint64_t*required)try{
    if(!required||(!dst&&cap))return SP_BAD_ARGUMENT;
    auto lock=locked(c);auto text=c->authority_facts.dump();*required=text.size()+1;
    if(!dst)return SP_OK;
    if(cap<*required)return SP_BUFFER_TOO_SMALL;
    std::memcpy(dst,text.c_str(),*required);return SP_OK;
}catch(...){return error();}
extern "C" int32_t sp_a12_pl_candidate_attach_v1(sp_linear_context*c,int fd)try{
    auto lock=locked(c);if(auto rc=c->life.idle())return rc;
    if(c->loads||c->runs||c->pending)return SP_BAD_ARGUMENT;
#ifdef SP_LINEAR_CONTROL_TEST
    const auto text=c->authority_facts.dump();unsigned char hash[32];unsigned length=0;
    require(EVP_Digest(text.data(),text.size(),hash,&length,EVP_sha256(),nullptr)==1&&length==32);
    uint64_t words[4];std::memcpy(words,hash,32);c->authority.attach(fd,words);return SP_OK;
#else
    // Intentionally unavailable until real device generation and manager binding are reviewed.
    (void)fd;return SP_UNSUPPORTED;
#endif
}catch(...){return error();}
'''

def generate():
    parent=BUNDLE/'source/backend.cpp';assert sha(parent)==PARENT_SHA
    text=parent.read_text(encoding='utf-8');original=text;changes=[]
    def edit(old,new):
        nonlocal text
        assert text.count(old)==1,old
        text=text.replace(old,new);changes.append((old,new))
    edit('#include "supervisor_gate.hpp"','#include "supervisor_gate.hpp"\n#include "pl_auth_gate.hpp"')
    edit('    a07::Lifecycle life;','    a07::Lifecycle life;\n    plauth::Gate authority;\n    json authority_facts;')
    edit('    std::map<uint64_t,std::unique_ptr<Weight>> weights;',
        '    std::map<uint64_t,std::unique_ptr<Weight>> weights;\n    std::unique_ptr<Weight> pending; // destroyed before device and DeviceLock; retained on unknown upload')
    edit('    a12::permit("device_open",0);','''#ifndef SP_LINEAR_CONTROL_TEST
    // This candidate cannot be activated on a board by editing a JSON enable flag.
    return SP_UNSUPPORTED;
#endif
    a12::permit("device_open",0);''')
    edit('    std::shared_ptr<sp_linear_context> owner(std::move(c));auto raw=owner.get();','''    c->authority_facts={{"schema","A12_PL_CONTEXT_UNBOUND_V1"},{"production_enabled",false},
        {"worker_pid",getpid()},{"worker_start_ticks",plauth::ticks(getpid())},
        {"context_generation",plauth::nonce()},
        {"xclbin_sha256",c->bit_hash},{"xclbin_uuid",uuid.to_string()},
        {"kernel_build_id",c->build},{"device_name",c->device_name},{"device_index",index},
        {"groups",c->groups},{"windows",c->windows},
        {"io_addresses",{c->x.address(),c->sx.address(),c->y.address(),c->meta.address()}},
        {"io_sizes",{c->x.size(),c->sx.size(),c->y.size(),c->meta.size()}},
        {"boot_id",a11::text("/proc/sys/kernel/random/boot_id")},
        {"board_generation_approval","UNBOUND"}};
    std::shared_ptr<sp_linear_context> owner(std::move(c));auto raw=owner.get();''')
    edit('    auto v=std::make_unique<Weight>();v->shape=a;v->charged=amount;','''    try{
    c->authority.before_load();
    c->pending=std::make_unique<Weight>();auto&v=c->pending;v->shape=a;v->charged=amount;''')
    edit('    auto h=c->next;c->weights.emplace(h,std::move(v));++c->next;++c->loads;c->used+=amount;*out=h;return SP_OK;','''    c->authority.complete(0,true);
    auto h=c->next;c->weights.emplace(h,std::move(c->pending));++c->next;++c->loads;c->used+=amount;*out=h;return SP_OK;
    }catch(...){c->authority.fail();c->life.poison();return error();}''')
    edit('    a12::permit("submit",job);','    // Private shared authority replaces only backend submit; legacy router/open/load lanes remain.')
    edit('auto finish_error=[&](int rc){c->life.poison();','auto finish_error=[&](int rc){c->authority.fail();c->life.poison();')
    edit('    try{\n        std::memcpy(c->x.map<void*>(),x,a.x);','    try{\n        c->authority.before_transfer(job);\n        std::memcpy(c->x.map<void*>(),x,a.x);')
    edit('        c->run.start();const auto deadline=', '        c->authority.before_start(job);\n        c->run.start();const auto deadline=')
    edit('        if(auto rc=c->life.begin(job,timeout))return rc;',
        '        if(auto rc=c->life.begin(job,timeout))return finish_error(rc);')
    edit('        c->life.completed_and_validated();++c->runs;','        c->authority.complete(job);\n        c->life.completed_and_validated();++c->runs;')
    edit('    c->closed=true;{std::lock_guard<std::mutex> g(registry_mutex);registry.erase(c);}',
        '    require(!c->authority.unknown(),SP_POISONED);\n    c->closed=true;{std::lock_guard<std::mutex> g(registry_mutex);registry.erase(c);}')
    text+=EXTRA
    inverse=text[:-len(EXTRA)]
    for old,new in reversed(changes):assert inverse.count(new)==1;inverse=inverse.replace(new,old)
    assert inverse==original
    return text,changes
