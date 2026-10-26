#pragma once
// A-owned PRIVATE candidate. Shared atomics require a trusted controlled worker.
// No board activation, lock release, unpoison, retry or hardware completion claim.
#include <atomic>
#include <chrono>
#include <cstdint>
#include <cstring>
#include <fcntl.h>
#include <fstream>
#include <poll.h>
#include <sstream>
#include <stdexcept>
#include <string>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/random.h>
#include <unistd.h>
namespace plauth {
static_assert(std::atomic<uint64_t>::is_always_lock_free,"64-bit shared atomic required");
constexpr uint64_t MAGIC=0x413132504c303031ULL,REVOKED=1ULL<<63,ACTIVE=1ULL<<62;
constexpr uint64_t IO=1ULL<<61,START=1ULL<<60,LOAD=1ULL<<59,COUNT=0xffffffffULL;
constexpr uint64_t GENERATION=0xffffULL<<32;
struct alignas(64) Page {
    uint64_t magic,manager_pid,manager_ticks,worker_pid,worker_ticks,epoch_hi,epoch_lo;
    uint64_t context[4];
    std::atomic<uint64_t> state,limit,expires_ns,healthy_ns,max_age_ns;
};
static_assert(sizeof(Page)<=4096 && alignof(Page)==64,"private page layout");
inline uint64_t now(){return std::chrono::duration_cast<std::chrono::nanoseconds>(
    std::chrono::steady_clock::now().time_since_epoch()).count();}
inline uint64_t ticks(pid_t pid){
    std::ifstream f("/proc/"+std::to_string(pid)+"/stat");std::string line;std::getline(f,line);
    auto at=line.rfind(')');if(!f||at==std::string::npos)throw std::runtime_error("PL process identity absent");
    std::istringstream s(line.substr(at+2));std::string v;
    for(int i=0;i<=19;++i)if(!(s>>v))throw std::runtime_error("PL process identity malformed");
    return std::stoull(v);
}
inline void need(bool ok){if(!ok)throw std::runtime_error("PL private authority refused");}
inline std::string nonce(){
    uint64_t words[2]{};size_t done=0;
    while(done<sizeof words){auto n=getrandom(reinterpret_cast<char*>(words)+done,sizeof words-done,0);
        if(n<0&&errno==EINTR)continue;
        need(n>0);done+=size_t(n);}
    need(words[0]&&words[1]);return std::to_string(words[0])+":"+std::to_string(words[1]);
}
class Gate {
    Page* p=nullptr;int manager=-1;uint64_t generation=0,hi=0,lo=0;
    uint64_t manager_pid=0,manager_ticks=0,worker_pid=0,worker_ticks=0;
    uint64_t identity[4]{};
    void live()const{
        need(p&&manager>=0);pollfd fd{manager,POLLIN,0};need(poll(&fd,1,0)==0);
        need(p->magic==MAGIC&&p->epoch_hi==hi&&p->epoch_lo==lo&&
            p->manager_pid==manager_pid&&p->manager_ticks==manager_ticks&&
            p->worker_pid==worker_pid&&p->worker_ticks==worker_ticks&&
            std::memcmp(p->context,identity,sizeof identity)==0);
        const auto s=p->state.load();const auto n=now(),h=p->healthy_ns.load(),age=p->max_age_ns.load();
        const auto limit=p->limit.load();need(limit&&limit<=5000&&(s&COUNT)<=limit);
        need(!(s&REVOKED)&&(s&ACTIVE)&&(s&GENERATION)==generation&&
            n<p->expires_ns.load()&&h&&h<=n&&age&&age<=1000000000ULL&&n-h<=age);
    }
    void reserve(uint64_t job,bool load){
        live();auto s=p->state.load();need(!(s&(IO|START|LOAD|REVOKED))&&
            (s&ACTIVE)&&(s&GENERATION)==generation);
        const auto n=s&COUNT,lim=p->limit.load();need(lim&&lim<=5000);
        if(!load)need(job==n+1&&n<lim);
        const auto desired=(s&~COUNT)|(load?n:n+1)|IO|(load?LOAD:0);
        need(p->state.compare_exchange_strong(s,desired));live();
    }
public:
    Gate()=default;Gate(const Gate&)=delete;Gate&operator=(const Gate&)=delete;
    ~Gate(){if(p)munmap(p,4096);if(manager>=0)::close(manager);}
    void attach(int fd,const uint64_t expected[4]){
        need(!p&&manager<0&&fd>=3);struct stat st{};
        need(!fstat(fd,&st)&&S_ISREG(st.st_mode)&&st.st_size==4096&&
            (fcntl(fd,F_GETFL)&O_ACCMODE)==O_RDWR);
        const int seals=fcntl(fd,F_GET_SEALS);
        need(seals>=0&&(seals&(F_SEAL_SEAL|F_SEAL_GROW|F_SEAL_SHRINK))==(F_SEAL_SEAL|F_SEAL_GROW|F_SEAL_SHRINK));
        auto q=static_cast<Page*>(mmap(nullptr,4096,PROT_READ|PROT_WRITE,MAP_SHARED,fd,0));
        need(q!=MAP_FAILED);
        int pidfd=-1;
        try{
            const auto parent=getppid();
            need(q->magic==MAGIC&&q->manager_pid==uint64_t(parent)&&q->worker_pid==uint64_t(getpid())&&
                q->manager_ticks==ticks(parent)&&q->worker_ticks==ticks(getpid())&&
                q->epoch_hi&&q->epoch_lo&&std::memcmp(q->context,expected,32)==0);
            pidfd=int(syscall(SYS_pidfd_open,parent,0));need(pidfd>=0);
            need(getppid()==parent&&ticks(parent)==q->manager_ticks);
            generation=q->state.load()&GENERATION;need(generation);
            manager_pid=q->manager_pid;manager_ticks=q->manager_ticks;
            worker_pid=q->worker_pid;worker_ticks=q->worker_ticks;hi=q->epoch_hi;lo=q->epoch_lo;
            std::memcpy(identity,expected,32);p=q;manager=pidfd;live();
        }catch(...){p=nullptr;manager=-1;munmap(q,4096);if(pidfd>=0)::close(pidfd);throw;}
    }
    void before_transfer(uint64_t job){reserve(job,false);}
    void before_load(){reserve(0,true);}
    void before_start(uint64_t job){
        live();auto s=p->state.load();need((s&IO)&&!(s&(START|LOAD|REVOKED))&&(s&COUNT)==job&&
            (s&ACTIVE)&&(s&GENERATION)==generation);
        need(p->state.compare_exchange_strong(s,s|START));live();
        // Last local check precedes XRT start directly. It cannot atomically cancel DMA.
    }
    void complete(uint64_t job,bool load=false){
        live();auto s=p->state.load();
        need((s&IO)&&!(s&REVOKED)&&(s&ACTIVE)&&(s&GENERATION)==generation&&((load&&(s&LOAD)&&!(s&START))||
            (!load&&(s&START)&&!(s&LOAD)&&(s&COUNT)==job)));
        need(p->state.compare_exchange_strong(s,s&~(IO|START|LOAD)));live();
    }
    void fail()noexcept{if(p)p->state.fetch_or(REVOKED);}
    bool unknown()const noexcept{return p&&(p->state.load()&(IO|START|LOAD));}
};
}
