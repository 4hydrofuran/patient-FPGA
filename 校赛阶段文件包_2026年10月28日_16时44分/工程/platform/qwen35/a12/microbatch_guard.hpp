// Private x86 PC experiment. No public ABI/math/device/HLS implementation.
#pragma once
#if !defined(__x86_64__) || !defined(SP_A12_PC_TEST)
#error "microbatch_guard requires x86_64 PC-test build"
#endif
#include <array>
#include <atomic>
#include <chrono>
#include <cstring>
#include <fcntl.h>
#include <poll.h>
#include <stdexcept>
#include <string>
#include <sys/mman.h>
#include <sys/random.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <unistd.h>

namespace mb {
using json=nlohmann::json;
constexpr uint64_t MAGIC=0x4131325043423033ull;
constexpr uint64_t REVOKED=1ull<<63,ACTIVE=1ull<<62,INFLIGHT=1ull<<61,COUNT=0xffffffffull,GEN=0xffffull<<32;
inline uint64_t now(){return std::chrono::duration_cast<std::chrono::nanoseconds>(
    std::chrono::steady_clock::now().time_since_epoch()).count();}
inline void need(bool v,const char*s){if(!v)throw std::runtime_error(s);}
struct alignas(64) Page {
    uint64_t magic,manager,epoch_hi,epoch_lo,worker_pid,worker_start;
    alignas(8) uint64_t gate,limit,expires,max_age,healthy_at;
    uint64_t digest[4];
};
static_assert(sizeof(Page)<=4096 && __atomic_always_lock_free(8,nullptr),"PC shared atomics required");
inline uint64_t load(const uint64_t*p){return __atomic_load_n(p,__ATOMIC_SEQ_CST);}
inline void store(uint64_t*p,uint64_t v){__atomic_store_n(p,v,__ATOMIC_SEQ_CST);}
inline uint64_t generation(uint64_t g){return (g&GEN)>>32;}
inline uint64_t process_start(){
    std::ifstream f("/proc/self/stat");std::string s;std::getline(f,s);auto end=s.rfind(')');
    need(end!=std::string::npos,"PC process identity unreadable");std::istringstream fields(s.substr(end+2));
    std::string value;for(int i=0;i<20;++i)need(bool(fields>>value),"PC process identity incomplete");
    size_t n=0;auto ticks=std::stoull(value,&n);need(n==value.size()&&ticks,"PC process start invalid");return ticks;
}
inline std::string hex(uint64_t a,uint64_t b){
    std::ostringstream s;s<<std::hex<<std::setfill('0')<<std::setw(16)<<a<<std::setw(16)<<b;return s.str();
}
inline std::string digest(Page*p){std::string s;for(int i=0;i<4;i+=2)s+=hex(load(p->digest+i),load(p->digest+i+1));return s;}
inline void digest_to(Page*p,const char*s){
    need(s&&std::strlen(s)==64,"invalid request digest");
    for(int i=0;i<4;++i){std::string v(s+i*16,16);size_t n=0;auto x=std::stoull(v,&n,16);need(n==16,"invalid hex digest");store(p->digest+i,x);}
}
struct Writer {Page*p;~Writer(){__atomic_fetch_or(&p->gate,REVOKED,__ATOMIC_SEQ_CST);munmap(p,4096);}};
inline Page* map(int fd,bool write){
    struct stat s{};need(!fstat(fd,&s)&&S_ISREG(s.st_mode)&&s.st_size==4096,"wrong PC page extent/type");
    int seals=fcntl(fd,F_GET_SEALS);need(seals>=0&&(seals&(F_SEAL_GROW|F_SEAL_SHRINK|F_SEAL_SEAL))==
        (F_SEAL_GROW|F_SEAL_SHRINK|F_SEAL_SEAL),"unsealed PC page geometry");
    need((fcntl(fd,F_GETFL)&O_ACCMODE)==(write?O_RDWR:O_RDONLY),"wrong PC page access mode");
    auto*p=mmap(nullptr,4096,PROT_READ|(write?PROT_WRITE:0),MAP_SHARED,fd,0);
    need(p!=MAP_FAILED,"PC shared page mmap failed");return static_cast<Page*>(p);
}
struct Control {
    int fd=-1;uint64_t router=0,backend=0,first=0,last=0,next=0,grant_generation=0,batches=0,claims=0;
    uint32_t expected_t=0;Page*p=nullptr;std::string worker,context,request_sha;uint64_t start_ticks=0;
    ~Control(){if(p)munmap(p,4096);}
    void configure(const json&cfg){
        context=cfg.at("context_sha256");need(context.size()==64,"PC context binding missing");
        const char*v=std::getenv("SP_A12_BATCH_PAGE_FD");need(v,"PC batch page FD absent");
        size_t n=0;int pagefd=std::stoi(v,&n);need(n==std::strlen(v)&&pagefd>=3,"PC batch page FD invalid");
        // The local authoritative counter and revoke share one atomic word.
        // This RW mapping requires a trusted controlled worker; it is NOT
        // protection against malicious code that writes this page directly.
        p=map(pagefd,true);need(load(&p->magic)==MAGIC&&load(&p->manager)==uint64_t(getppid()),"PC page owner/version differs");
        std::array<uint64_t,2> nonce{};need(getrandom(nonce.data(),sizeof(nonce),0)==sizeof(nonce),"PC worker nonce failed");
        worker=hex(nonce[0],nonce[1]);start_ticks=process_start();
    }
    void peer(){
        if(fd<0){const char*v=std::getenv("SP_A12_CONTROL_FD");need(v,"PC parent control FD absent");
            size_t n=0;fd=std::stoi(v,&n);need(n==std::strlen(v)&&fd>=3,"PC control FD invalid");}
        struct ucred u{};socklen_t size=sizeof(u);
        need(!getsockopt(fd,SOL_SOCKET,SO_PEERCRED,&u,&size)&&u.pid==getppid()&&uint64_t(u.pid)==load(&p->manager),"PC manager peer changed");
        pollfd item{fd,POLLIN|POLLRDHUP,0};need(poll(&item,1,0)>=0&&!(item.revents&(POLLERR|POLLHUP|POLLNVAL|POLLRDHUP)),"PC manager disconnected");
    }
    json exchange(json q){
        peer();auto&seq=q.at("phase").get_ref<const std::string&>().compare(0,7,"router_")==0?router:backend;
        q["sequence"]=++seq;q["pid"]=getpid();q["batch_protocol"]=1;q["worker_epoch"]=worker;
        q["process_start_ticks"]=start_ticks;
        q["manager_epoch"]=hex(load(&p->epoch_hi),load(&p->epoch_lo));q["context_sha256"]=context;
        auto text=q.dump()+"\n";size_t sent=0;
        while(sent<text.size()){auto n=send(fd,text.data()+sent,text.size()-sent,MSG_NOSIGNAL);need(n>0,"PC batch send failed");sent+=n;}
        std::string reply;char c=0;
        while(reply.size()<4096){need(recv(fd,&c,1,0)==1,"PC batch manager disconnected");if(c=='\n')break;reply+=c;}
        need(c=='\n',"PC batch reply too long");auto r=json::parse(reply);
        need(r.at("sequence")==seq&&r.at("allow")==true&&r.at("allow").is_boolean(),"PC batch denied");
        need(r.at("worker_epoch")==worker&&r.at("context_sha256")==context&&
            r.at("manager_epoch")==hex(load(&p->epoch_hi),load(&p->epoch_lo)),"PC stale/foreign reply");return r;
    }
    void permit(const char*phase,uint64_t job){exchange({{"phase",phase},{"job",job}});}
    uint64_t live(bool active){
        peer();uint64_t g=load(&p->gate),clock=now(),observed=load(&p->healthy_at);
        need(load(&p->worker_pid)==uint64_t(getpid())&&load(&p->worker_start)==start_ticks,"PC worker restarted/foreign");
        need(!(g&REVOKED)&&(!active||(g&ACTIVE))&&clock<load(&p->expires),"PC revoked/inactive/expired");
        need(observed&&clock>=observed&&clock-observed<=load(&p->max_age),"PC health stale");return g;
    }
    void before(uint64_t job,uint32_t t){
        uint64_t g=live(true);need(!(g&INFLIGHT)&&job&&job<=5000&&job==(g&COUNT)+1&&job<=load(&p->limit),"PC shared busy/job/budget exhausted");
        if(grant_generation!=generation(g)){next=last=0;grant_generation=generation(g);}
        if(next==0||next>last){
            auto sha=digest(p);auto r=exchange({{"phase","batch"},{"job",job},{"T",t},
                {"request_generation",grant_generation},{"request_sha256",sha}});
            auto count=r.at("count").get<uint64_t>();first=r.at("first_job");last=r.at("last_job");
            need(count>=1&&count<=72&&first==job&&last==first+count-1&&last<=load(&p->limit)&&
                r.at("request_generation")==grant_generation&&r.at("request_sha256")==sha&&r.at("T")==t&&
                r.at("deadline_monotonic_ns")==load(&p->expires),
                "PC grant range/context differs");
            expected_t=t;next=job;request_sha=sha;++batches;
        }
        need(next==job&&job<=last&&t==expected_t&&request_sha==digest(p),"PC grant order/T/request differs");
        g=live(true);need(!(g&INFLIGHT)&&generation(g)==grant_generation&&job==(g&COUNT)+1,"PC grant busy/generation/job changed");
        // Atomic claim vs revoke/request transition: the single shared counter
        // prevents duplicate credit in a second mapping/DSO. No refund on doubt.
        uint64_t wanted=(g&~COUNT)|job|INFLIGHT;
        need(__atomic_compare_exchange_n(&p->gate,&g,wanted,false,__ATOMIC_SEQ_CST,__ATOMIC_SEQ_CST),"PC claim lost revoke/start race");
        ++claims;++next;
        // Recheck time/liveness after any preemption at claim. A rejected claim
        // remains charged; it must never be refunded or retried automatically.
        need(generation(live(true))==grant_generation,"PC revoked after claim");
    }
    void after(uint64_t job){
        auto g=live(true);need((g&INFLIGHT)&&(g&COUNT)==job&&generation(g)==grant_generation,"PC completion revoked/foreign");
        auto wanted=g&~INFLIGHT;
        need(__atomic_compare_exchange_n(&p->gate,&g,wanted,false,__ATOMIC_SEQ_CST,__ATOMIC_SEQ_CST),"PC completion lost revoke race");
    }
    json report(){return {{"schema","PC_MICROBATCH_LOCAL_BUDGET_V3"},{"worker_epoch",worker},
        {"manager_epoch",hex(load(&p->epoch_hi),load(&p->epoch_lo))},{"context_sha256",context},
        {"grant_requests",batches},{"local_claims",claims},{"shared_claims",load(&p->gate)&COUNT},
        {"request_generation",generation(load(&p->gate))},{"revoked",bool(load(&p->gate)&REVOKED)},
        {"inflight_or_unknown",bool(load(&p->gate)&INFLIGHT)},
        {"bound_worker_pid",load(&p->worker_pid)},{"bound_worker_start_ticks",load(&p->worker_start)},
        {"unused_local_credit",next&&next<=last?last-next+1:0},{"hardware_completions",nullptr}};}
};
}

#define MB_EXPORT extern "C" __attribute__((visibility("default")))
MB_EXPORT void* a12_pc_batch_writer_open_v1(int fd,uint64_t hi,uint64_t lo,uint64_t expires,uint64_t age)try{
    mb::need(age&&age<=1000000000&&expires>mb::now(),"invalid PC page bounds");
    auto*p=mb::map(fd,true);
    if(mb::load(&p->magic)!=0){munmap(p,4096);return nullptr;}
    std::memset(p,0,4096);mb::store(&p->manager,getpid());
    mb::store(&p->epoch_hi,hi);mb::store(&p->epoch_lo,lo);mb::store(&p->expires,expires);
    mb::store(&p->max_age,age);mb::store(&p->magic,mb::MAGIC);return new mb::Writer{p};
}catch(...){return nullptr;}
MB_EXPORT int a12_pc_batch_health_v1(void*handle,uint64_t stamp)try{
    auto*p=static_cast<mb::Writer*>(handle)->p;mb::need(stamp&&stamp<=mb::now()&&stamp>=mb::load(&p->healthy_at),"bad PC health stamp");
    mb::store(&p->healthy_at,stamp);return 0;
}catch(...){return -1;}
MB_EXPORT int a12_pc_batch_bind_worker_v1(void*handle,uint64_t pid,uint64_t ticks)try{
    auto*p=static_cast<mb::Writer*>(handle)->p;auto old=mb::load(&p->worker_pid);
    mb::need(pid&&ticks&&!(mb::load(&p->gate)&mb::REVOKED),"invalid PC worker binding");
    if(old){mb::need(old==pid&&mb::load(&p->worker_start)==ticks,"PC worker binding cannot be replaced");return 0;}
    // Only the serialized manager permission thread binds the first worker.
    mb::store(&p->worker_start,ticks);mb::store(&p->worker_pid,pid);return 0;
}catch(...){return -1;}
MB_EXPORT int a12_pc_batch_begin_v1(void*handle,uint64_t completed,uint64_t budget,const char*sha)try{
    auto*p=static_cast<mb::Writer*>(handle)->p;auto g=mb::load(&p->gate);auto gen=mb::generation(g);
    mb::need(!(g&(mb::REVOKED|mb::ACTIVE|mb::INFLIGHT))&&(g&mb::COUNT)==completed&&completed<=5000&&budget&&budget<=5000-completed&&gen<3,"PC request transition refused");
    mb::digest_to(p,sha);mb::store(&p->limit,completed+budget);
    auto wanted=mb::ACTIVE|((gen+1)<<32)|completed;
    mb::need(__atomic_compare_exchange_n(&p->gate,&g,wanted,false,__ATOMIC_SEQ_CST,__ATOMIC_SEQ_CST),"PC request lost revoke race");return 0;
}catch(...){return -1;}
MB_EXPORT int a12_pc_batch_end_v1(void*handle,uint64_t completed)try{
    auto*p=static_cast<mb::Writer*>(handle)->p;auto g=mb::load(&p->gate);
    mb::need(!(g&(mb::REVOKED|mb::INFLIGHT))&&(g&mb::ACTIVE)&&(g&mb::COUNT)==completed,"PC end state unknown");
    auto wanted=g&~mb::ACTIVE;
    mb::need(__atomic_compare_exchange_n(&p->gate,&g,wanted,false,__ATOMIC_SEQ_CST,__ATOMIC_SEQ_CST),"PC end lost start/revoke race");return 0;
}catch(...){return -1;}
MB_EXPORT uint64_t a12_pc_batch_revoke_v1(void*handle){return __atomic_fetch_or(&static_cast<mb::Writer*>(handle)->p->gate,mb::REVOKED,__ATOMIC_SEQ_CST);}
MB_EXPORT uint64_t a12_pc_batch_gate_v1(void*handle){return mb::load(&static_cast<mb::Writer*>(handle)->p->gate);}
MB_EXPORT void a12_pc_batch_writer_close_v1(void*handle){delete static_cast<mb::Writer*>(handle);}
