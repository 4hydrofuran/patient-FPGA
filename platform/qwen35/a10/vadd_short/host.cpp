// A10 SHORT REAL-XRT HOST. No CPU fallback, mock kernel, reset, or forced abort.
#include "control.hpp"
#include "retention.hpp"
#include "../../../a1/vadd/cases.hpp"
#include "../../../a1/vadd/bo_range.hpp"
#include "../../../a1/vadd/evidence_file.hpp"
#include "json.hpp"
#include <xrt/xrt_bo.h>
#include <xrt/xrt_device.h>
#include <xrt/xrt_kernel.h>
#include <openssl/evp.h>
#include <array>
#include <charconv>
#include <chrono>
#include <csignal>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <memory>
#include <pthread.h>
#include <sstream>
#include <sys/file.h>
#include <sys/utsname.h>
#include <thread>
using json=nlohmann::json;
using Clock=std::chrono::steady_clock;
namespace fs=std::filesystem;
static constexpr const char* BIT_SHA="9d1243508f887dfe7db76ad1f37984907fe39567bab1cb118403f7691ed98394";
static constexpr const char* UUID="87b3bf55-dfd2-2b35-0a6a-55028f87deec";
static constexpr std::size_t WORDS=MAX_LENGTH+16, BYTES=WORDS*sizeof(uint32_t);
static void require(bool ok,const char* why){if(!ok)throw std::runtime_error(why);}
static std::string read(const fs::path&p,std::size_t cap=65536){
    std::ifstream f(p,std::ios::binary);require(bool(f),"read failed");
    std::string s(cap+1,'\0');f.read(s.data(),s.size());const auto n=f.gcount();
    require(f.eof()&&n<=static_cast<std::streamsize>(cap),"read cap/I/O failure");s.resize(n);return s;
}
static std::string trim(std::string s){while(!s.empty()&&(s.back()=='\n'||s.back()=='\r'||s.back()==' '))s.pop_back();return s;}
static unsigned number(const std::string&s){unsigned n=0;const auto r=std::from_chars(s.data(),s.data()+s.size(),n);
    require(r.ec==std::errc()&&r.ptr==s.data()+s.size(),"invalid unsigned decimal");return n;}
static std::string digest(const fs::path&p){
    std::ifstream f(p,std::ios::binary);require(bool(f),"hash input absent");
    std::unique_ptr<EVP_MD_CTX,decltype(&EVP_MD_CTX_free)> c(EVP_MD_CTX_new(),EVP_MD_CTX_free);
    require(c&&EVP_DigestInit_ex(c.get(),EVP_sha256(),nullptr)==1,"sha init");
    std::array<char,65536>b{};while(f){f.read(b.data(),b.size());const auto n=f.gcount();
        if(n)require(EVP_DigestUpdate(c.get(),b.data(),n)==1,"sha update");}
    require(f.eof(),"sha read");unsigned char sum[32];unsigned n=0;
    require(EVP_DigestFinal_ex(c.get(),sum,&n)==1&&n==32,"sha final");
    std::ostringstream out;for(auto v:sum)out<<std::hex<<std::setw(2)<<std::setfill('0')<<unsigned(v);return out.str();
}
static std::vector<unsigned> temperatures(){
    std::vector<unsigned> out;
    for(const auto&m:fs::directory_iterator("/sys/class/hwmon")){
        if(m.path().filename().string().rfind("hwmon",0)!=0)continue;
        for(const auto&s:fs::directory_iterator(m.path())){
            const auto name=s.path().filename().string();
            if(name.rfind("temp",0)!=0||name.size()<11||name.substr(name.size()-6)!="_input")continue;
            const auto t=number(trim(read(s.path(),128)));
            require(t>0&&t<60000,"invalid/hot temperature: stop");out.push_back(t);
            require(out.size()<=16,"sensor cap");
        }
    }
    require(!out.empty(),"temperature unavailable: stop");return out;
}
static void health(){
    (void)temperatures();
    std::istringstream in(read("/proc/meminfo"));std::string line;bool okay=false;
    while(std::getline(in,line)){if(line.rfind("MemAvailable:",0)!=0)continue;
        std::istringstream v(line.substr(13));unsigned long long kb=0;std::string unit;
        v>>kb>>unit;okay=bool(v)&&unit=="kB"&&kb>=262144;}
    require(okay,"MemAvailable unknown/low; no memory stress");
}
static json memory_observation(const char* phase){
    // Observations, not disjoint physical allocations or a pressure-test peak.
    return {{"event","MEMORY_OBSERVATION"},{"phase",phase},
            {"proc_status",read("/proc/self/status")},
            {"smaps_rollup",read("/proc/self/smaps_rollup")},
            {"meminfo",read("/proc/meminfo")},
            {"explicit_bo_live_max_bytes",3*BYTES},
            {"includes_hidden_xrt_allocations",false}};
}
struct Lock{
    int fd=-1;
    void acquire(){fd=::open("/run/lock/patient-qwen-linear.lock",O_RDWR|O_CREAT|O_NOFOLLOW|O_CLOEXEC,0600);
        require(fd>=0&&flock(fd,LOCK_EX|LOCK_NB)==0,"device ownership lock unavailable");}
    ~Lock(){if(fd>=0)::close(fd);}
};
struct Context{
    xrt::device device;
    xrt::kernel kernel;
    xrt::bo a,b,c;
    xrt::run run; // Normal destruction: run first, then all BOs, kernel, device.
    uint32_t *pa=nullptr,*pb=nullptr,*pc=nullptr;
    std::array<int,3> groups{};
};
struct Adapter{
    Context& c;ExclusiveEvidenceFile& log;unsigned job,n;Clock::time_point batch_begin,last_health;
    Clock::time_point sync_begin,submitted,completed;
    double sync_in_us=0,run_us=0,sync_out_us=0;
    std::uint64_t now_ms(){return std::chrono::duration_cast<std::chrono::milliseconds>(Clock::now().time_since_epoch()).count();}
    bool stop_requested(){
        if(a10::cancelled()||Clock::now()-batch_begin>=std::chrono::seconds(10))return true;
        if(Clock::now()-last_health>=std::chrono::milliseconds(100)){health();last_health=Clock::now();}
        return false;
    }
    void prepare(){
        health();validate_length(n,MAX_LENGTH);
        for(std::size_t i=0;i<WORDS;++i){
            c.pa[i]=i<n?input_a(job,i):0;c.pb[i]=i<n?input_b(job,i):0;
            c.pc[i]=i<n?~(c.pa[i]+c.pb[i]):0xdeadbeefu;
        }
        sync_begin=Clock::now();
        c.a.sync(XCL_BO_SYNC_BO_TO_DEVICE);c.b.sync(XCL_BO_SYNC_BO_TO_DEVICE);c.c.sync(XCL_BO_SYNC_BO_TO_DEVICE);
        sync_in_us=std::chrono::duration<double,std::micro>(Clock::now()-sync_begin).count();
        c.run.set_arg(0,c.a);c.run.set_arg(1,c.b);c.run.set_arg(2,c.c);c.run.set_arg(3,n);
        log.append(json({{"event","PREPARED_NOT_SUBMITTED"},{"job",job},{"n",n}}).dump()+"\n");
    }
    void start(){submitted=Clock::now();c.run.start();}
    a10::RunState state(){
        const auto s=c.run.state();
        if(s==ERT_CMD_STATE_COMPLETED){completed=Clock::now();run_us=std::chrono::duration<double,std::micro>(completed-submitted).count();return a10::RunState::completed;}
        if(s==ERT_CMD_STATE_NEW||s==ERT_CMD_STATE_QUEUED||s==ERT_CMD_STATE_RUNNING||s==ERT_CMD_STATE_SUBMITTED)return a10::RunState::running;
        return a10::RunState::failed;
    }
    void sleep_poll(){std::this_thread::sleep_for(std::chrono::milliseconds(2));}
    bool readback_validate(){
        const auto t=Clock::now();c.c.sync(XCL_BO_SYNC_BO_FROM_DEVICE);
        sync_out_us=std::chrono::duration<double,std::micro>(Clock::now()-t).count();
        for(std::size_t i=0;i<WORDS;++i){
            const auto expected=i<n?input_a(job,i)+input_b(job,i):0xdeadbeefu;
            if(c.pc[i]!=expected)return false;
        }
        return true;
    }
};
[[noreturn]] static void retain_forever(ExclusiveEvidenceFile* log){
    // No destructors, abort, further sync/readback, repeated run, or reset.
    // SIGKILL/power loss cannot be made safe by userspace: operator recovery only.
    try{if(log)log->append("{\"event\":\"POISONED_RETAIN_PROCESS_AND_BOS\",\"output_consumable\":false,\"hardware_quiescence\":null}\n");}catch(...){}
    std::cerr<<"POISONED: retaining process/BOs. No automatic retry/abort/reset. Do not kill; reviewed platform recovery required.\n"<<std::flush;
    a10::park_owner();
}
int main(int argc,char**argv){
    // Owners deliberately OUTSIDE try: exceptions cannot unwind live BOs.
    Lock lock;std::unique_ptr<Context> owner;std::unique_ptr<ExclusiveEvidenceFile> log;a10::Control control;
    try{
        if(argc==2&&std::string(argv[1])=="--check-linkage"){
            std::cout<<"LINKAGE_ONLY_NO_DEVICE_OPEN\n";return 0;
        }
        require(argc==7&&std::string(argv[1])=="--execute-authorized-short",
                "usage: a10-vadd-short --execute-authorized-short approval.json pinned.xclbin NEW.jsonl start_job jobs(1..20); never use timeout/kill wrapper");
        const unsigned start=number(argv[5]),count=number(argv[6]);
        require(start==7&&count==1,"minimal acceptance only: job 7, one 32-element call; regression cancelled");
        require(!std::getenv("XCL_EMULATION_MODE"),"emulation forbidden");
        require(!std::getenv("LD_PRELOAD")&&!std::getenv("LD_LIBRARY_PATH"),"unreviewed dynamic loader overrides forbidden");
        struct utsname u{};require(uname(&u)==0&&std::string(u.machine)=="aarch64","requires real aarch64");
        const auto approval=json::parse(read(argv[2]));
        require(approval.value("schema","")=="A10_VADD_SHORT_APPROVAL_V1"&&approval.value("authorized",false)
            &&approval.value("platform_review_complete",false)&&approval.value("recovery_review_complete",false),"PL review/authorization incomplete");
        require(approval.at("kernel_release")==u.release,"kernel changed");
        const auto machine=digest("/etc/machine-id"),boot=trim(read("/proc/sys/kernel/random/boot_id"));
        require(approval.at("board_machine_id_sha256")==machine&&approval.at("approved_boot_id")==boot,"wrong board/boot");
        require(read("/proc/device-tree/model").find("KV260")!=std::string::npos,"not KV260 model");
        const char* token=std::getenv("A1_BOARD_LEASE");require(token&&*token,"central board lease required");
        const auto lease=json::parse(read("/var/lock/kv260-a1/active/lease.json"));
        require(lease.at("token")==token&&lease.at("owner")=="A"&&lease.at("scope")=="A10_VADD_SHORT"
             &&lease.at("identity")==machine+":"+boot,"central lease identity/scope mismatch");
        const auto epoch=std::chrono::duration<double>(std::chrono::system_clock::now().time_since_epoch()).count();
        require(lease.at("expires_unix").get<double>()>epoch+15,"lease too near expiry");
        require(approval.at("xclbin_sha256")==BIT_SHA&&approval.at("xclbin_uuid")==UUID&&digest(argv[3])==BIT_SHA,"xclbin hash/UUID differs");
        for(const auto* kind:{"xrt_coreutil","xrt_core"}){
            const auto key=std::string(kind);const auto path=approval.at(key+"_path").get<std::string>();
            require(approval.at(key+"_sha256").is_string()&&digest(path)==approval.at(key+"_sha256"),"XRT library hash differs");
        }
        a10::block_exit_signals();health();
        log=std::make_unique<ExclusiveEvidenceFile>(argv[4]);
        log->append(json({{"event","BEGIN"},{"domain","BOARD_REAL_XRT"},{"approval_sha256",digest(argv[2])},
                          {"xclbin_sha256",BIT_SHA},{"boot_id",boot},{"start_job",start},{"requested_jobs",count},
                          {"temperature_mC",temperatures()},{"whole_A10_pass",false}}).dump()+"\n");
        const auto init_begin=Clock::now();
        auto init_check=[&]{
            require(!a10::cancelled(),"cancelled during initialization; no further device calls");
            require(Clock::now()-init_begin<std::chrono::seconds(10),"initialization soft deadline; no further device calls");
            health();
        };
        auto init_step=[&](const char* name,auto operation){
            init_check();
            log->append(json({{"event","INIT_STEP_BEGIN"},{"step",name}}).dump()+"\n");
            const auto begin=Clock::now();
            a10::checked_init(init_check,operation);
            log->append(json({{"event","INIT_STEP_COMPLETE"},{"step",name},
                             {"elapsed_ms",std::chrono::duration<double,std::milli>(Clock::now()-begin).count()}}).dump()+"\n");
        };
        lock.acquire();init_check();owner=std::make_unique<Context>();auto& c=*owner;
        log->append(memory_observation("before_device_open").dump()+"\n");
        init_step("device_open",[&]{c.device=xrt::device(0);});
        xrt::uuid uuid;
        init_step("load_xclbin",[&]{uuid=c.device.load_xclbin(argv[3]);require(uuid.to_string()==UUID,"loaded UUID differs");});
        init_step("kernel_open",[&]{c.kernel=xrt::kernel(c.device,uuid,"krnl_vadd:{krnl_vadd_1}",xrt::kernel::cu_access_mode::exclusive);});
        for(unsigned i=0;i<3;++i){c.groups[i]=c.kernel.group_id(i);require(c.groups[i]==3,"group_id differs from pinned metadata");}
        init_step("bo_a",[&]{c.a=xrt::bo(c.device,BYTES,c.groups[0]);});
        init_step("bo_b",[&]{c.b=xrt::bo(c.device,BYTES,c.groups[1]);});
        init_step("bo_c",[&]{c.c=xrt::bo(c.device,BYTES,c.groups[2]);});
        for(const auto*b:{&c.a,&c.b,&c.c}){require(b->size()==BYTES,"BO size mismatch");a1_require_bo_window(b->address(),b->size());}
        init_step("map_and_run_create",[&]{c.pa=c.a.map<uint32_t*>();c.pb=c.b.map<uint32_t*>();c.pc=c.c.map<uint32_t*>();c.run=xrt::run(c.kernel);});
        log->append(json({{"event","BO_CREATED"},{"groups",c.groups},{"addresses",{c.a.address(),c.b.address(),c.c.address()}},
                          {"bytes_each",BYTES},{"is_maximum_budget_probe",false}}).dump()+"\n");
        log->append(memory_observation("explicit_bos_live").dump()+"\n");
        const auto batch_begin=Clock::now();unsigned passed=0;
        for(unsigned job=start;job<start+count;++job){
            Adapter a{c,*log,job,unsigned(LENGTHS[job%LENGTHS.size()]),batch_begin,Clock::now(),{},{},{}};
            const auto r=a10::one(control,a);
            if(control.must_retain())retain_forever(log.get());
            if(r!=a10::Result::pass){log->append(json({{"event","STOP_NO_RETRY"},{"job",job},{"reason_code",int(r)},{"output_consumable",false}}).dump()+"\n");return 2;}
            ++passed;
            log->append(json({{"event","VERIFIED"},{"job",job},{"n",a.n},{"pass",true},{"sync_in_us",a.sync_in_us},
                              {"submit_poll_us",a.run_us},{"sync_out_us",a.sync_out_us},{"temperature_mC",temperatures()}}).dump()+"\n");
            if(job+1<start+count)std::this_thread::sleep_for(std::chrono::milliseconds(100));
        }
        owner.reset(); // Only positively completed runs reach normal destruction.
        log->append(memory_observation("after_normal_release").dump()+"\n");
        log->append(json({{"event","BATCH_COMPLETE"},{"verified",passed},{"A10","NOT_PASSED_BY_A_BATCH"}}).dump()+"\n");log->finish();
        std::cout<<"REAL_DEVICE_MINIMAL verified="<<passed<<"; separate recovery/BO evidence required; regression cancelled\n";return 0;
    }catch(const std::exception&e){
        if(control.must_retain())retain_forever(log.get());
        try{if(log)log->append(json({{"event","STOP_EXCEPTION"},{"message",e.what()},{"output_consumable",false}}).dump()+"\n");}catch(...){}
        std::cerr<<e.what()<<'\n';return 1;
    }catch(...){if(control.must_retain())retain_forever(log.get());return 1;}
}
