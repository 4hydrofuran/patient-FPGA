// Candidate XRT implementation. Not selected by the application and never opened on PC.
#include "host_contract.hpp"
#include "release_gate.hpp"
#include "json.hpp"
#include "managed_lock.hpp"
#include "supervisor_gate.hpp"
#include <xrt/xrt_device.h>
#include <xrt/xrt_kernel.h>
#include <xrt/xrt_bo.h>
#include <openssl/evp.h>
#include <array>
#include <chrono>
#include <cstring>
#include <cstdio>
#include <fcntl.h>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <map>
#include <memory>
#include <mutex>
#include <sstream>
#include <stdexcept>
#include <thread>
#include <sys/file.h>
#include <unistd.h>
using json=nlohmann::json;
using Clock=std::chrono::steady_clock;
struct Rejected {int rc;};
static void require(bool ok,int rc=SP_CONTRACT_MISMATCH){if(!ok)throw Rejected{rc};}
static std::string digest(const std::string&p){
    std::ifstream f(p,std::ios::binary);require(bool(f),SP_BAD_ARGUMENT);
    std::unique_ptr<EVP_MD_CTX,decltype(&EVP_MD_CTX_free)> ctx(EVP_MD_CTX_new(),EVP_MD_CTX_free);
    require(ctx&&EVP_DigestInit_ex(ctx.get(),EVP_sha256(),nullptr)==1,SP_DEVICE_ERROR);
    std::array<char,65536>b{};while(f){f.read(b.data(),b.size());if(auto n=f.gcount())require(EVP_DigestUpdate(ctx.get(),b.data(),n)==1,SP_DEVICE_ERROR);}
    require(f.eof(),SP_DEVICE_ERROR);unsigned char sum[32];unsigned len=0;
    require(EVP_DigestFinal_ex(ctx.get(),sum,&len)==1&&len==32,SP_DEVICE_ERROR);
    std::ostringstream s;for(auto v:sum)s<<std::hex<<std::setw(2)<<std::setfill('0')<<unsigned(v);return s.str();
}
static json readj(const std::string&p){
    require(std::filesystem::is_regular_file(p)&&std::filesystem::file_size(p)<=1024*1024,SP_BAD_ARGUMENT);
    std::ifstream f(p);json j;f>>j;return j;
}
static uint64_t number(const json&j,const char*k,uint64_t max=UINT64_MAX){
    require(j.contains(k)&&j[k].is_number_unsigned(),SP_BAD_ARGUMENT);
    auto v=j[k].get<uint64_t>();require(v<=max,SP_BAD_ARGUMENT);return v;
}
static int error() noexcept {try{throw;}catch(const Rejected&e){return e.rc;}catch(...){return SP_DEVICE_ERROR;}}
struct DeviceLock {
    int fd=-1;
    ~DeviceLock(){if(fd>=0)::close(fd);}
    void acquire(const json& profile){
#ifndef SP_LINEAR_CONTROL_TEST
        require(geteuid()==0,SP_UNSUPPORTED);
        require(profile.value("boot_id",std::string())+"\n"==a11::text("/proc/sys/kernel/random/boot_id"));
        const auto expiry=number(profile,"expires_monotonic_ns");
        require(expiry>uint64_t(std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now().time_since_epoch()).count()));
        fd=a11::borrow_lock(number(profile,"inherited_device_lock_fd",INT32_MAX),
            number(profile,"manager_pid",INT32_MAX),number(profile,"manager_start_ticks"),
            "/run/lock/patient-qwen-linear.lock");
        return;
#else
        (void)profile;
#endif
        // Shared by all physical A backends; not an alias-specific lock. Never truncate/delete.
#ifdef SP_LINEAR_CONTROL_TEST
        // Compile-only test seam. Never enabled in the ARM64 production build.
        fd=::open("CONTROL_TEST_ONLY.lock",O_RDWR|O_CREAT|O_CLOEXEC|O_NOFOLLOW,0600);
#else
        fd=::open("/run/lock/patient-qwen-linear.lock",O_RDWR|O_CREAT|O_CLOEXEC|O_NOFOLLOW,0600);
#endif
        require(fd>=0,SP_DEVICE_ERROR);require(flock(fd,LOCK_EX|LOCK_NB)==0,SP_BUSY);
    }
};
struct Weight {
    a07::Layout shape;
    xrt::bo w,sw;
    uint64_t charged=0;
};
struct sp_linear_context {
    std::mutex mutex;
    a07::Lifecycle life;
    DeviceLock device_lock; // destroyed last, after all XRT objects.
    xrt::device device;
    xrt::kernel kernel;
    std::map<uint64_t,std::unique_ptr<Weight>> weights;
    xrt::bo x,sx,y,meta;
    xrt::run run; // destroyed before BOs on normal quiescent close.
    uint64_t next=1,budget=0,used=0,align=0,loads=0,runs=0,max_runs=0,max_loads=0;
    double load_copy_ms=0,load_sync_ms=0;
    uint32_t build=0;
    std::array<int,6>groups{};
    std::array<std::array<uint64_t,2>,6>windows{};
    std::string bit_hash,device_name;
    json last;
    bool closed=false; // Protected by mutex; registry guards the raw C handle lifetime.
};
static std::mutex registry_mutex;
// Intentionally never destroy the registry automatically: POISONED owners must
// not release DMA buffers on a library static destructor. Normal close erases.
static auto& registry=*new std::map<sp_linear_context*,std::shared_ptr<sp_linear_context>>;
struct Locked {
    std::shared_ptr<sp_linear_context> owner;
    std::unique_lock<std::mutex> lock; // Destroyed before owner.
};
static uint64_t charge(uint64_t n,uint64_t align){require(align&&n<=UINT64_MAX-(align-1),SP_BAD_ARGUMENT);return (n+align-1)/align*align;}
static void check_bo(sp_linear_context*c,const xrt::bo&bo,int arg,uint64_t allocated){
    const auto actual_size=bo.size();const auto actual_address=bo.address();
    const bool size_ok=actual_size==allocated;
    const bool range_ok=a07::in_window(c->windows[arg][0],c->windows[arg][1],actual_address,actual_size);
    const auto row=json({{"event","A11_BO_VALIDATION"},{"argument",arg},
        {"requested_bytes",allocated},{"actual_size",actual_size},{"actual_address",actual_address},
        {"window_base",c->windows[arg][0]},{"window_span",c->windows[arg][1]},
        {"size_ok",size_ok},{"range_ok",range_ok},{"compute_submissions",0}}).dump();
    std::fprintf(stderr,"%s\n",row.c_str());std::fflush(stderr);
    require(size_ok&&range_ok,SP_DEVICE_ERROR);
}
static Locked locked(sp_linear_context*c){
    require(c,SP_BAD_ARGUMENT);std::shared_ptr<sp_linear_context> owner;
    {std::lock_guard<std::mutex> g(registry_mutex);auto it=registry.find(c);
     require(it!=registry.end(),SP_BAD_ARGUMENT);owner=it->second;}
    std::unique_lock<std::mutex> l(owner->mutex,std::try_to_lock);require(l.owns_lock(),SP_BUSY);
    require(!owner->closed,SP_BAD_ARGUMENT);return {std::move(owner),std::move(l)};
}
static thread_local const char* a11_open_phase="not_entered";
static void a11_open_failure(int rc) noexcept {
    try {
        std::string detail="unknown nonstandard exception";
        try {throw;} catch(const Rejected&) {detail="policy or explicit device validation rejected";}
        catch(const std::exception& e) {detail=e.what();} catch(...) {}
        if(detail.size()>512)detail.resize(512);
        const auto row=json({{"event","A11_OPEN_FAILURE"},{"phase",a11_open_phase},
            {"status_code",rc},{"detail",detail},{"compute_submissions",0},
            {"does_not_prove_resource_release",true}}).dump();
        std::fprintf(stderr,"%s\n",row.c_str());std::fflush(stderr);
    } catch(...) {std::fputs("A11_OPEN_FAILURE_DIAGNOSTIC_UNAVAILABLE\n",stderr);}
}
extern "C" int32_t sp_linear_open_v1(const char*path,sp_linear_context**out)try{
    a11_open_phase="arguments"; if(!out)return SP_BAD_ARGUMENT;
    *out=nullptr;
    if(!path)return SP_BAD_ARGUMENT;
    a11_open_phase="config"; auto cfg=readj(path);
    const auto config_dir=std::filesystem::absolute(path).parent_path();
    auto resolve=[&](const char*key){
        const std::filesystem::path value=cfg.at(key).get<std::string>();
        return (value.is_absolute()?value:config_dir/value).lexically_normal().string();
    };
    // All release/deployment checks precede any device discovery, loading, or BO creation.
    a11_open_phase="source_gate"; auto source=readj(resolve("kernel_source"));
    if(auto rc=a07::release_gate(cfg,source))return rc;
    a11_open_phase="profile"; auto profile=readj(resolve("deployment_profile"));
#ifdef SP_LINEAR_CONTROL_TEST
    require(profile.value("status",std::string())=="CONTROL_TEST_ONLY_NOT_BOARD",SP_UNSUPPORTED);
#else
    require(profile.value("status",std::string())=="A12_BOUNDED_MODEL_TRIAL_NOT_ACCEPTED",SP_UNSUPPORTED);
#endif
    require(profile.at("source_xo_sha256")==source.at("xo_sha256"));
    a11_open_phase="xclbin_hash"; std::string bit=resolve("xclbin_path"), expected=cfg.at("xclbin_sha256");
    require(expected.size()==64&&profile.at("xclbin_sha256")==expected&&digest(bit)==expected);
    a11_open_phase="profile_layout"; auto c=std::make_unique<sp_linear_context>();c->bit_hash=expected;
    c->budget=number(profile,"trial_bo_limit_bytes",256ULL*1024*1024);c->align=number(profile,"bo_charge_alignment",1ULL<<20);

    require(c->budget&&c->align==8192,SP_UNSUPPORTED);
    c->max_runs=number(profile,"a12_max_runs",65536);
    c->max_loads=number(profile,"a12_max_loads",72);
    require(c->max_runs&&c->max_loads,SP_UNSUPPORTED);
    a12::permit("device_open",0);
    c->build=number(profile,"kernel_build_id",UINT32_MAX);require(c->build==a07::selected_build(source));
    auto index=number(profile,"device_index",UINT32_MAX);c->device_name=profile.at("device_name");
    auto windows=profile.at("argument_address_windows");require(windows.is_array()&&windows.size()==6);
    for(int i=0;i<6;++i){
        c->windows[i]={number(windows[i],"base"),number(windows[i],"span")};
        require(a07::in_window(c->windows[i][0],c->windows[i][1],c->windows[i][0],1));
    }
    require(!c->device_name.empty());a11_open_phase="borrowed_lock"; c->device_lock.acquire(profile);
    a11_open_phase="device_open_and_name"; c->device=xrt::device(unsigned(index));require(c->device.get_info<xrt::info::device::name>()==c->device_name);
    // Bitstream loading is only reachable after a future verified deployment profile and explicit enable.
    a11_open_phase="load_xclbin_and_uuid"; auto uuid=c->device.load_xclbin(bit);require(uuid.to_string()==profile.at("xclbin_uuid").get<std::string>());
    a11_open_phase="kernel_open"; c->kernel=xrt::kernel(c->device,uuid,"w4a8_linear_v1",xrt::kernel::cu_access_mode::exclusive);
    a11_open_phase="argument_groups"; auto groups=profile.at("argument_groups");require(groups.is_array()&&groups.size()==6);
    for(int i=0;i<6;++i){c->groups[i]=c->kernel.group_id(i);require(c->groups[i]>=0&&groups[i]==c->groups[i]);}
    const uint64_t sizes[]={8*4864,8*4,8*4864*4,64};
    for(auto n:sizes)c->used+=charge(n,c->align);
    require(c->used<=c->budget,SP_BUFFER_TOO_SMALL);
    a11_open_phase="allocate_x"; c->x=xrt::bo(c->device,charge(sizes[0],c->align),c->groups[2]);
    a11_open_phase="allocate_sx"; c->sx=xrt::bo(c->device,charge(sizes[1],c->align),c->groups[3]);
    a11_open_phase="allocate_y"; c->y=xrt::bo(c->device,charge(sizes[2],c->align),c->groups[4]);
    a11_open_phase="allocate_meta"; c->meta=xrt::bo(c->device,charge(sizes[3],c->align),c->groups[5]);
    a11_open_phase="verify_bo_ranges"; check_bo(c.get(),c->x,2,charge(sizes[0],c->align));check_bo(c.get(),c->sx,3,charge(sizes[1],c->align));
    check_bo(c.get(),c->y,4,charge(sizes[2],c->align));check_bo(c.get(),c->meta,5,charge(sizes[3],c->align));
    a11_open_phase="run_object_no_submission"; c->run=xrt::run(c->kernel);
    std::shared_ptr<sp_linear_context> owner(std::move(c));auto raw=owner.get();
    {std::lock_guard<std::mutex> g(registry_mutex);registry.emplace(raw,owner);}
    *out=raw;return SP_OK;
}catch(...){const int rc=error();a11_open_failure(rc);return rc;}
extern "C" int32_t sp_linear_load_v1(sp_linear_context*c,uint32_t n,uint32_t k,const uint8_t*w,uint64_t wb,const float*sw,uint64_t sb,uint64_t*out)try{
    if(!out)return SP_BAD_ARGUMENT;
    *out=0;
    auto lock=locked(c);if(auto rc=c->life.idle())return rc;
    a07::Layout a;if(auto rc=a07::layout(n,k,1,a))return rc;if(auto rc=a07::weights(a,w,wb,sw,sb))return rc;

    if(c->loads>=c->max_loads)return SP_UNSUPPORTED;
    a12::permit("weight_load",c->loads+1);
    uint64_t amount=charge(a.w,c->align)+charge(a.sw,c->align);
    if(!a07::fits_budget(c->budget,c->used,amount))return SP_BUFFER_TOO_SMALL;
    if(c->next==UINT64_MAX)return SP_BAD_ARGUMENT;
    auto v=std::make_unique<Weight>();v->shape=a;v->charged=amount;
    v->w=xrt::bo(c->device,charge(a.w,c->align),c->groups[0]);v->sw=xrt::bo(c->device,charge(a.sw,c->align),c->groups[1]);
    check_bo(c,v->w,0,charge(a.w,c->align));check_bo(c,v->sw,1,charge(a.sw,c->align));
    auto load_start=Clock::now();
    std::memcpy(v->w.map<void*>(),w,a.w);std::memcpy(v->sw.map<void*>(),sw,a.sw);
    auto load_copied=Clock::now();
    v->w.sync(XCL_BO_SYNC_BO_TO_DEVICE,a.w,0);v->sw.sync(XCL_BO_SYNC_BO_TO_DEVICE,a.sw,0);
    auto load_synced=Clock::now();
    c->load_copy_ms=std::chrono::duration<double,std::milli>(load_copied-load_start).count();
    c->load_sync_ms=std::chrono::duration<double,std::milli>(load_synced-load_copied).count();
    auto h=c->next;c->weights.emplace(h,std::move(v));++c->next;++c->loads;c->used+=amount;*out=h;return SP_OK;
}catch(...){return error();}
extern "C" int32_t sp_linear_run_v1(sp_linear_context*c,uint64_t h,uint32_t t,const int8_t*x,uint64_t xb,const float*sx,uint64_t sb,float*y,uint64_t yb,uint64_t job,uint32_t timeout)try{
    auto lock=locked(c);if(auto rc=c->life.idle())return rc;
    // An invalid new request must not leave the previous success report consumable.
    c->last={{"last_status_code",SP_BAD_ARGUMENT},{"output_consumable",false},{"attempted_job_id",job}};
    auto it=c->weights.find(h);if(it==c->weights.end()||!job||job<=c->life.job()||!timeout)return SP_BAD_ARGUMENT;
    auto&v=*it->second;a07::Layout a;if(auto rc=a07::layout(v.shape.n,v.shape.k,t,a)){c->last["last_status_code"]=rc;return rc;}
    if(auto rc=a07::inputs(a,x,xb,sx,sb,y,yb)){c->last["last_status_code"]=rc;return rc;}

    if(c->runs>=c->max_runs)return SP_UNSUPPORTED;
    a12::permit("submit",job);
    auto start=Clock::now();
    auto finish_error=[&](int rc){c->life.poison();c->last={{"last_status_code",rc},{"output_consumable",false}};return rc;};
    try{
        std::memcpy(c->x.map<void*>(),x,a.x);std::memcpy(c->sx.map<void*>(),sx,a.sx);
        std::memset(c->meta.map<void*>(),0,64); // seed=0 per invocation; not a cumulative hardware counter.
        auto copied=Clock::now();
        c->x.sync(XCL_BO_SYNC_BO_TO_DEVICE,a.x,0);c->sx.sync(XCL_BO_SYNC_BO_TO_DEVICE,a.sx,0);c->meta.sync(XCL_BO_SYNC_BO_TO_DEVICE,64,0);
        auto synced=Clock::now();
        c->run.set_arg(0,v.w);c->run.set_arg(1,v.sw);c->run.set_arg(2,c->x);c->run.set_arg(3,c->sx);c->run.set_arg(4,c->y);c->run.set_arg(5,c->meta);
        c->run.set_arg(6,t);c->run.set_arg(7,a.n);c->run.set_arg(8,a.k);
        c->run.set_arg(9,a.w);c->run.set_arg(10,a.sw);c->run.set_arg(11,a.x);c->run.set_arg(12,a.sx);c->run.set_arg(13,a.y);c->run.set_arg(14,uint64_t(64));
        c->run.set_arg(15,job);c->run.set_arg(16,uint32_t(1));
        if(auto rc=c->life.begin(job,timeout))return rc;
        // Mark RUNNING before start: even a start exception cannot prove no DMA submission occurred.
        auto submitted=Clock::now();
        c->run.start();const auto deadline=start+std::chrono::milliseconds(timeout);
        uint32_t observed_ert=0;
        for(;;){auto state=c->run.state();observed_ert=uint32_t(state);if(state==ERT_CMD_STATE_COMPLETED)break;
            if(state==ERT_CMD_STATE_ERROR||state==ERT_CMD_STATE_ABORT||state==ERT_CMD_STATE_NORESPONSE)return finish_error(SP_DEVICE_ERROR);
            if(Clock::now()>=deadline)return finish_error(SP_TIMEOUT);
            std::this_thread::sleep_for(std::chrono::milliseconds(1));
        }
        auto completed=Clock::now();if(completed>=deadline)return finish_error(SP_TIMEOUT);
        c->meta.sync(XCL_BO_SYNC_BO_FROM_DEVICE,64,0);
        auto meta_synced=Clock::now();
        if(auto rc=a07::validate_meta(c->meta.map<const uint8_t*>(),64,c->build,job,0,a.w))return finish_error(rc);
        auto meta_checked=Clock::now();
        std::ostringstream raw_meta;for(size_t i=0;i<64;++i)raw_meta<<std::hex<<std::setw(2)<<std::setfill('0')<<unsigned(c->meta.map<const uint8_t*>()[i]);
        c->y.sync(XCL_BO_SYNC_BO_FROM_DEVICE,a.y,0);auto result=c->y.map<const float*>();
        auto y_synced=Clock::now();
        if(auto rc=a07::output(a,result,a.y))return finish_error(rc);
        auto ended=Clock::now();if(ended>=deadline)return finish_error(SP_TIMEOUT);
        auto ms=[](auto a,auto b){return std::chrono::duration<double,std::milli>(b-a).count();};
        // Prepare report before committing any caller output: exceptions never leak stale/partial Y.
        c->last={{"a12_observed_ert_state",observed_ert},{"a12_raw_meta_hex",raw_meta.str()},{"last_status_code",SP_OK},{"output_consumable",true},{"input_sync_ms",ms(start,synced)},
                 {"kernel_ms",ms(synced,completed)},{"kernel_ms_scope","host_set_args_submit_and_poll_not_device_cycles"},
                 {"output_sync_ms",ms(completed,ended)},{"service_ms",ms(start,ended)},
                 {"a11_input_copy_and_meta_seed_ms",ms(start,copied)},
                 {"a11_input_bo_sync_ms",ms(copied,synced)},
                 {"a11_set_args_ms",ms(synced,submitted)},
                 {"a11_submit_to_confirmed_completion_ms",ms(submitted,completed)},
                 {"a11_meta_sync_ms",ms(completed,meta_synced)},
                 {"a11_meta_validate_ms",ms(meta_synced,meta_checked)},
                 {"a11_output_bo_sync_and_map_ms",ms(meta_checked,y_synced)},
                 {"a11_output_validate_ms",ms(y_synced,ended)},
                 {"a11_weight_copy_ms",c->load_copy_ms},{"a11_weight_upload_sync_ms",c->load_sync_ms},
                 {"a11_full_service_scope","MUST_USE_EXTERNAL_CALL_TIMER_INCLUDING_QUANT_AND_RETURN_COPY"},
                 {"algorithm_weight_bytes",a.w},{"logical_weight_and_scale_bytes",a.w+a.sw},
                 {"private_meta_host_seeded_count",a07::read_le(c->meta.map<const uint8_t*>()+24,8)},
                 {"private_counter_scope","per_call_seed_zero_not_global_counter"}};
        c->life.completed_and_validated();++c->runs;std::memcpy(y,result,a.y);return SP_OK;
    }catch(...){return finish_error(error());}
}catch(...){return error();}
extern "C" int32_t sp_linear_report_v1(sp_linear_context*c,char*dst,uint64_t capacity,uint64_t*required)try{
    if(!required||(!dst&&capacity))return SP_BAD_ARGUMENT;
    auto lock=locked(c);
    json j={{"api_version",1},{"contract_sha256",a07::contract_sha},{"backend_id","A_XRT_B_KERNEL_V1"},
        {"device_id",c->device_name},{"xclbin_sha256",c->bit_hash},{"kernel_build_id",c->build},{"job_id",c->life.job()},
        {"execution_kind","FPGA_REAL"},{"status",c->life.phase()==a07::Phase::POISONED?"POISONED":"READY"},
        {"hardware_done_count",nullptr},{"weight_resident",!c->weights.empty()},{"quant_ms",nullptr},
        {"input_sync_ms",nullptr},{"kernel_ms",nullptr},{"output_sync_ms",nullptr},{"service_ms",nullptr},
        {"algorithm_weight_bytes",nullptr},{"measured_bus_bytes",nullptr},{"cycles",nullptr},
        {"host_verified_completions",c->runs},{"weight_load_count",c->loads},{"owned_bo_charged_bytes",c->used},
        {"no_silent_fallback",true},{"retains_resources_on_poison",true}};
    j["a11_io_bo_addresses"]={c->x.address(),c->sx.address(),c->y.address(),c->meta.address()};
    j["a11_io_bo_charged_sizes"]={charge(8*4864,c->align),charge(8*4,c->align),charge(8*4864*4,c->align),charge(64,c->align)};
    j["a11_argument_groups"]=c->groups;
    j["a11_explicit_bo_allocations_host_counter"]=4+2*c->loads;
    j["a11_bo_counter_scope"]="host allocations for these six explicit buffers; excludes implicit XRT BOs";
    j["a11_live_weights"]=json::array();
    for(auto& item:c->weights)j["a11_live_weights"].push_back({{"handle",item.first},
        {"addresses",{item.second->w.address(),item.second->sw.address()}},
        {"charged_sizes",{charge(item.second->shape.w,c->align),charge(item.second->shape.sw,c->align)}}});
    if(!c->last.is_null())j.update(c->last);
#ifdef SP_LINEAR_CONTROL_TEST
    // A control double is not a CPU mathematical backend or an FPGA execution.
    // This deliberately non-production report MUST NOT enter public metrics.
    j["execution_kind"]=nullptr;j["test_domain"]="CONTROL_TEST_DOUBLE_NOT_FPGA";
    j["public_metrics_eligible"]=false;
    for(auto key:{"input_sync_ms","kernel_ms","output_sync_ms","service_ms","algorithm_weight_bytes","private_meta_host_seeded_count"})j[key]=nullptr;
#endif
#ifdef SP_LINEAR_CONTROL_TEST
    for(auto it=j.begin();it!=j.end();++it)if(it.key().find("a11_")==0 && it.key().find("_ms")!=std::string::npos)it.value()=nullptr;
#endif
    
    j["candidate_scope"]="A12_BOUNDED_MODEL_TRIAL_NOT_DEFAULT";
    j["a12_max_runs"]=c->max_runs;j["a12_max_loads"]=c->max_loads;
    j["a12_hardware_global_completion_counter"]=nullptr;
    auto s=j.dump();*required=s.size()+1;
    if(!dst)return SP_OK;
    if(capacity<*required)return SP_BUFFER_TOO_SMALL;
    std::memcpy(dst,s.c_str(),*required);return SP_OK;
}catch(...){return error();}
extern "C" int32_t sp_linear_unload_v1(sp_linear_context*c,uint64_t h)try{
    auto lock=locked(c);if(auto rc=c->life.idle())return rc;auto it=c->weights.find(h);if(it==c->weights.end())return SP_BAD_ARGUMENT;
    // Remove run's previous BO bindings while quiescent before releasing the selected weight.
    c->run=xrt::run(c->kernel);c->used-=it->second->charged;c->weights.erase(it);return SP_OK;
}catch(...){return error();}
extern "C" int32_t sp_linear_close_v1(sp_linear_context*c)try{
    auto lock=locked(c);if(auto rc=c->life.idle())return rc;
    c->closed=true;{std::lock_guard<std::mutex> g(registry_mutex);registry.erase(c);}
    // In-progress callers hold shared ownership and see closed before touching device state.
    return SP_OK;
}catch(...){return error();}
