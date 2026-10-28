"""Exact reversible private hooks in the frozen actual Qwen frontend and Route."""
from modelpl_evidence import ROOT,BUNDLE,read,sha

class Derive:
    def __init__(self,text):self.original=text;self.text=text;self.edits=[]
    def edit(self,old,new):
        assert self.text.count(old)==1,old
        self.text=self.text.replace(old,new);self.edits.append((old,new))
    def finish(self):
        inverse=self.text
        for old,new in reversed(self.edits):assert inverse.count(new)==1;inverse=inverse.replace(new,old)
        assert inverse==self.original;return self.text,self.edits

ROUTE_EXTRA=r'''
namespace a12 {
json Route::private_status()const{return {{"schema","A12_MODEL_PLM_ROUTE_V1"},{"enabled",private_control},
    {"request_active",control_active},{"failed",private_failed},{"request_sha256",control_digest},
    {"copy_checks",copy_checks},{"checked_copy_bytes",copy_bytes},{"closed",closed},{"release_allowed",false}};}
void Route::begin_private_request(const json&request){
    if(!private_control)return;
    need(enabled&&!closed&&!unsafe&&!private_failed&&!control_active,"private request state");
    auto text=request.dump();control_digest=hash_bytes(text.data(),text.size());
    need(control_begin_fn(context,control_digest.c_str())==SP_OK,"private request bind failed");
    control_active=true;copy_checks=copy_bytes=0;
}
void Route::finish_private_request(bool ok){
    if(!private_control)return;
    if(!ok){abort_private_request();throw std::runtime_error("private request failed; no result commit");}
    need(control_active&&!unsafe&&!private_failed&&copy_checks>0,"private request completion state");
    need(control_end_fn(context)==SP_OK,"private request end failed");control_active=false;
}
void Route::abort_private_request()noexcept{
    if(!private_control)return;
    private_failed=true;control_active=false;unsafe=real;
    if(context&&control_abort_fn)control_abort_fn(context);
}
}
'''

def runtime():
    manifest=read(BUNDLE/'manifest.json');pins={r['path']:r for r in manifest['files']};out={};changes={}
    for name in ('main.cpp','route.cpp','route.hpp','bridge.cpp'):
        p=BUNDLE/'source'/name;assert sha(p)==pins['source/'+name]['sha256'];d=Derive(p.read_text(encoding='utf-8'))
        if name=='route.hpp':
            d.edit('    json policy,ledger=json::array();','''    json policy,ledger=json::array();
    int32_t(*control_begin_fn)(sp_linear_context*,const char*)=nullptr;
    int32_t(*control_end_fn)(sp_linear_context*)=nullptr;
    int32_t(*control_abort_fn)(sp_linear_context*)=nullptr;
    bool control_active=false,private_failed=false;uint64_t copy_checks=0,copy_bytes=0;
    std::string control_digest;''')
            d.edit('    bool enabled=false,real=false;std::string scope="none";','''    bool enabled=false,real=false,private_control=false;std::string scope="none";
    void begin_private_request(const json&request);
    void finish_private_request(bool ok);
    void abort_private_request()noexcept;
    json private_status()const;''')
        elif name=='route.cpp':
            d.edit('    if(real)permit("router_open",0);','''    private_control=policy.value("a12_private_protocol",std::string())=="A12_PLM_PRIVATE_V1";
    need(!policy.contains("a12_private_protocol")||private_control,"unknown private protocol");
    if(real||private_control)permit("router_open",0);''')
            d.edit('#undef A12_LOAD','''#undef A12_LOAD
    if(private_control){
        control_begin_fn=reinterpret_cast<decltype(control_begin_fn)>(dlsym(library,"sp_a12_plm_request_v1"));
        control_end_fn=reinterpret_cast<decltype(control_end_fn)>(dlsym(library,"sp_a12_plm_request_end_v1"));
        control_abort_fn=reinterpret_cast<decltype(control_abort_fn)>(dlsym(library,"sp_a12_plm_request_abort_v1"));
        need(control_begin_fn&&control_end_fn&&control_abort_fn,"private protocol ABI missing");
    }''')
            d.edit('    r["a12_hardware_global_count"]=nullptr;r["a12_trace"]=ledger;return r;','''    r["a12_hardware_global_count"]=nullptr;r["a12_trace"]=ledger;
    r["a12_private_control"]=private_status();return r;''')
            d.edit('    if(real)permit("router_close",0);','''    need(!private_failed&&!control_active,"private failed/active route cannot close");
    if(real||private_control)permit("router_close",0);''')
            d.edit('    unsafe=false;return rc;', '''    if(private_control&&!real)need(r.at("pc_adapter")=="A12_REAL_MODEL_PLM_CPU_V1"&&
        r.at("execution_kind")=="CPU_REFERENCE"&&r.at("pc_output_consumable")==true&&r.at("pc_poisoned")==false&&
        r.at("pc_last_job")==job&&r.at("job_id")==job,"CPU private completion identity differs");
    unsafe=false;return rc;''')
            d.edit('    if(!diagnostic)return;need(ledger.size()<trace_limit,"A12 trace capacity exceeded");','''    if(private_control){
        need(control_active&&!private_failed&&!unsafe&&!closed&&dst&&y&&t>0&&t<=8&&n>0&&n<=4864,"private graph copy state");
        for(int row=0;row<t;++row)need(std::memcmp(static_cast<const char*>(dst->data)+(start+row)*dst->nb[1],y+size_t(row)*n,size_t(n)*4)==0,"private graph copy differs");
        ++copy_checks;copy_bytes+=uint64_t(t)*n*4;
    }
    if(!diagnostic)return;need(ledger.size()<trace_limit,"A12 trace capacity exceeded");''')
        elif name=='bridge.cpp':
            old='''            if(e.pl)b.route.returned(dst,start,count,n,job,b.y.data(),e.layer,e.op,b.epoch,b.execution);
#ifdef SP_A12_PC_TEST
            if(e.pl&&std::getenv("SP_A12_TEST_DROP_OUTPUT"))for(int row=0;row<count;++row)std::memset(static_cast<char*>(dst->data)+(start+row)*dst->nb[1],0,n*4);
#endif'''
            new='''#ifdef SP_A12_PC_TEST
            if(e.pl&&std::getenv("SP_A12_TEST_DROP_OUTPUT"))for(int row=0;row<count;++row)std::memset(static_cast<char*>(dst->data)+(start+row)*dst->nb[1],0,n*4);
#endif
            if(e.pl)b.route.returned(dst,start,count,n,job,b.y.data(),e.layer,e.op,b.epoch,b.execution);'''
            d.edit(old,new)
        else:
            d.edit('auto op=req.value("op","generate");if(op=="shutdown")break;',
                'auto op=req.value("op","generate");if(op=="shutdown")break;\n        if(bridge.route.private_control&&op!="generate"&&op!="cache_create")throw std::runtime_error("private control forbids auxiliary compute/cache operations");')
            d.edit('        auto cpu_before=bridge.report(false);','        bridge.route.begin_private_request(req);\n        auto cpu_before=bridge.report(false);')
            d.edit('''            bridge.request_stats.active=false;
            emit({{"type","cache_created"}''','''            bridge.request_stats.active=false;
            bridge.route.finish_private_request(true);route["a12_route"]=bridge.route.report();
            emit({{"type","cache_created"}''')
            d.edit('        emit({{"prefix_cache_request",cache_result}',
                '        bridge.route.finish_private_request(status=="OK");bridge_report["a12_route"]=bridge.route.report();\n        emit({{"prefix_cache_request",cache_result}')
            d.edit('      }catch(const std::exception&e){cache.clear_private();',
                '''      }catch(const std::exception&e){bridge.route.abort_private_request();
        json private_CPU_report=nullptr;
#ifdef SP_A12_PC_TEST
        if(bridge.route.private_control)private_CPU_report=bridge.report(false);
#endif
        cache.clear_private();''')
            d.edit('''{"request_profile",prof}});}
    }''','''{"request_profile",prof},{"private_control",bridge.route.private_status()},
          {"private_CPU_report",private_CPU_report},{"model_bridge_error",bridge.error}});
        if(bridge.route.private_control){
#ifdef SP_A12_PC_TEST
            return 2; // CPU-only cooperative exit; ARM keeps original quarantine.
#else
            bridge.route.park_if_unsafe();
#endif
        }
      }
    }''')
            d.edit('    bridge.route.close_checked();','''    bridge.route.close_checked();
    if(bridge.route.private_control){
        emit({{"type","private_closed"},{"domain",bridge.route.real?"BOARD":"PC"},
            {"status","NATIVE_CONTEXT_CLOSED_NOT_PLATFORM_RELEASE"},{"private_control",bridge.route.private_status()}});
        std::string acknowledgement;if(!std::getline(std::cin,acknowledgement)||acknowledgement.size()>1024||
            json::parse(acknowledgement).at("op")!="private_exit_ack")throw std::runtime_error("private close acknowledgement absent");
    }''')
        body,edits=d.finish()
        if name=='route.cpp':body+=ROUTE_EXTRA
        out[name]=body;changes[name]=dict(parent_sha256=sha(p),edits=edits,appended_private_methods=name=='route.cpp',inverse_exact=True)
    return out,changes

CPU_EXTRA=r'''
EXPORT int32_t sp_a12_completion_report_v1(sp_linear_context*c,char*dst,uint64_t capacity,uint64_t*needed)try{
    if(!c||!needed||(!dst&&capacity))return SP_BAD_ARGUMENT;
    std::unique_lock<std::mutex> lock(c->mutex,std::try_to_lock);if(!lock)return SP_BUSY;
    json j={{"schema","PC_MODEL_PLM_COMPACT_COMPLETION_V1"},{"execution_kind","CPU_REFERENCE"},
        {"pc_adapter","A12_REAL_MODEL_PLM_CPU_V1"},{"pc_output_consumable",c->last_consumable},
        {"pc_poisoned",c->poisoned},{"pc_last_job",c->last_job},{"job_id",c->last_job},
        {"hardware_done_count",nullptr},{"kernel_build_id",nullptr}};
    auto text=j.dump();*needed=text.size()+1;if(!dst)return SP_OK;
    if(capacity<*needed)return SP_BUFFER_TOO_SMALL;
    std::memcpy(dst,text.c_str(),*needed);return SP_OK;
}catch(...){return SP_DEVICE_ERROR;}
EXPORT int32_t sp_a12_plm_request_v1(sp_linear_context*c,const char*digest)try{
    if(!c||!digest)return SP_BAD_ARGUMENT;
    std::unique_lock<std::mutex> lock(c->mutex,std::try_to_lock);if(!lock)return SP_BUSY;
    need(!c->poisoned&&!c->closing,"CPU private bind poisoned");c->authority.bind_request(digest);return SP_OK;
}catch(...){if(c){c->authority.fail();c->poisoned=true;c->last_consumable=false;}return SP_DEVICE_ERROR;}
EXPORT int32_t sp_a12_plm_request_end_v1(sp_linear_context*c)try{
    if(!c)return SP_BAD_ARGUMENT;
    std::unique_lock<std::mutex> lock(c->mutex,std::try_to_lock);if(!lock)return SP_BUSY;
    need(!c->poisoned&&!c->closing,"CPU private END poisoned");c->authority.end_request();return SP_OK;
}catch(...){if(c){c->authority.fail();c->poisoned=true;c->last_consumable=false;}return SP_DEVICE_ERROR;}
EXPORT int32_t sp_a12_plm_request_abort_v1(sp_linear_context*c){
    if(!c)return SP_BAD_ARGUMENT;
    c->authority.fail();std::unique_lock<std::mutex> lock(c->mutex,std::try_to_lock);if(!lock)return SP_BUSY;
    c->poisoned=true;c->last_consumable=false;return SP_POISONED;
}
'''

def cpu():
    p=ROOT/'platform/qwen35/a12/native_cpu_control.cpp';assert sha(p)=='c4f4421a3f923793633e192dcdb6d7b516bdbe925a2ff83bf2008931253a9c1b'
    d=Derive(p.read_text(encoding='utf-8'))
    d.edit('using json=nlohmann::json;','using json=nlohmann::json;\n#include "plm_control.hpp"')
    d.edit('API api{};Control control;','API api{};Control control;plm::Control authority;')
    d.edit('r["pc_adapter"]="A12_NATIVE_CPU_CONTROL_V1";',
        'r["pc_adapter"]="A12_REAL_MODEL_PLM_CPU_V1";r["pc_plm"]=authority.report();')
    d.edit('void begin_close(){if(!closing){control.permit("router_close",0);closing=true;}}',
        'void begin_close(){if(!closing){need(authority.maintenance_allowed(),"CPU private maintenance refused");closing=true;}}')
    d.edit('cfg.at("schema")=="A12_NATIVE_CPU_CONTROL_V1"','cfg.at("schema")=="A12_REAL_MODEL_PLM_CPU_V1"')
    d.edit('    c->control.permit("router_open",0);c->control.permit("device_open",0);','    c->control.permit("device_open",0);')
    d.edit('    *out=c.release();return SP_OK;','''    json facts={{"schema","A12_MODEL_PLM_CPU_CONTEXT_V1"},{"execution_kind","CPU_REFERENCE"},
        {"worker_pid",getpid()},{"worker_start_ticks",plauth::ticks(getpid())},{"context_generation",plauth::nonce()},
        {"cpu_library_sha256",cfg.at("cpu_library_sha256")},{"cpu_config_sha256",cfg.at("cpu_config_sha256")},
        {"contract_sha256",CONTRACT},{"actual_CPU_fresh_report",r},
        {"boot_id",a12_modelpl_boot_id()},{"real_device_generation_approval","UNBOUND_PC_CPU_ONLY"}};
    c->authority.configure(facts);
    *out=c.release();return SP_OK;''')
    # The CPU fixture carries no device, BO addresses or kernel-build identity.
    d.edit('namespace {\nconstexpr',
        'static std::string a12_modelpl_boot_id(){std::ifstream f("/proc/sys/kernel/random/boot_id");return std::string(std::istreambuf_iterator<char>(f),{});}\nnamespace {\nconstexpr')
    d.edit('    int32_t rc=c->api.load(', '    c->authority.before_load();\n    int32_t rc=c->api.load(')
    d.edit('    ++c->loads;c->padded_n.emplace(*out,(n+31)/32*32);return SP_OK;',
        '    c->authority.complete(0,true);\n    ++c->loads;c->padded_n.emplace(*out,(n+31)/32*32);return SP_OK;')
    d.edit('if(rc!=SP_OK){c->poisoned=true;return rc;}',
        'if(rc!=SP_OK){c->authority.fail();c->poisoned=true;*out=0;return rc;}')
    d.edit('''    ++c->loads;c->padded_n.emplace(*out,(n+31)/32*32);return SP_OK;
}catch(...){if(c)c->poisoned=true;return SP_DEVICE_ERROR;}''','''    ++c->loads;c->padded_n.emplace(*out,(n+31)/32*32);return SP_OK;
}catch(...){if(c){c->authority.fail();c->poisoned=true;}if(out)*out=0;return SP_DEVICE_ERROR;}''')
    d.edit('    c->control.permit("submit",job);++c->started;',
        '''    const size_t values=size_t(t)*c->padded_n.at(h);need(yb>=values*4,"PC output length differs");
    std::vector<float> staged(values);c->authority.before_transfer(job,t);
    if(const char*pause=std::getenv("SP_A12_MODELPL_TEST_PAUSE_JOB")){
        need(std::string(pause)=="5","PC pause fixture job differs");
        if(job==5)std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
    c->authority.before_start(job);++c->started;''')
    d.edit('#include <cmath>','#include <cmath>\n#include <thread>\n#include <chrono>')
    d.edit('h,t,x,xb,sx,sb,y,yb,job,timeout);','h,t,x,xb,sx,sb,staged.data(),staged.size()*4,job,timeout);')
    d.edit('    const size_t values=size_t(t)*c->padded_n.at(h);need(yb>=values*4,"PC output length differs");\n    for(size_t i=0;i<values;++i)need(std::isfinite(y[i]),"PC nonfinite output");',
        '    for(size_t i=0;i<values;++i)need(std::isfinite(staged[i]),"PC nonfinite output");\n    c->authority.complete(job);std::memcpy(y,staged.data(),values*4);')
    d.edit('if(rc!=SP_OK){++c->failed;c->poisoned=true;return rc;}',
        'if(rc!=SP_OK){c->authority.fail();++c->failed;c->poisoned=true;return rc;}')
    # Exact prior error paths additionally revoke; do not hide CPU failure or permit errors.
    d.edit('if(c){c->poisoned=true;c->last_consumable=false;++c->failed;}',
        'if(c){c->authority.fail();c->poisoned=true;c->last_consumable=false;++c->failed;}')
    text,edits=d.finish();text+=CPU_EXTRA
    return text,dict(parent_sha256=sha(p),edits=edits,appended_private_ABI=True,inverse_exact=True)
