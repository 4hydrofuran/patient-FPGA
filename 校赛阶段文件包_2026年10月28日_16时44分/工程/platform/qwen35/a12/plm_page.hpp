#pragma once
// Extends the frozen private ownership page. No production/device approval API.
#include "pl_auth_gate.hpp"
#include "json.hpp"
#include <array>
#include <mutex>
namespace plm {
using plauth::need;using plauth::now;
constexpr uint64_t EXT_MAGIC=0x4131324d47523131ULL;
constexpr uint64_t UNBOUND=0,LOADING=1,IDLE=2,REQUEST=3,CLOSED=4;
struct alignas(64) Extra {
    uint64_t magic;
    std::atomic<uint64_t> phase,request_end,request_serial,digest[4];
};
static_assert(sizeof(plauth::Page)==128&&sizeof(Extra)==64,"private shared ABI");
inline Extra* extra(plauth::Page*p){return reinterpret_cast<Extra*>(reinterpret_cast<char*>(p)+128);}
inline std::array<uint64_t,4> words(const std::string&s){
    need(s.size()==64);std::array<uint64_t,4> out{};
    for(size_t i=0;i<32;++i){const auto pair=s.substr(i*2,2);need(pair.find_first_not_of("0123456789abcdef")==std::string::npos);
        reinterpret_cast<unsigned char*>(out.data())[i]=static_cast<unsigned char>(std::stoul(pair,nullptr,16));}
    return out;
}
inline std::string hex(const uint64_t*data){
    static const char*h="0123456789abcdef";std::string s;auto p=reinterpret_cast<const unsigned char*>(data);
    for(size_t i=0;i<32;++i){s+=h[p[i]>>4];s+=h[p[i]&15];}return s;
}
inline std::string request_digest(plauth::Page*p){uint64_t data[4];for(int i=0;i<4;++i)data[i]=extra(p)->digest[i].load();return hex(data);}
inline plauth::Page* map(int fd){
    struct stat st{};need(fd>=3&&!fstat(fd,&st)&&S_ISREG(st.st_mode)&&st.st_size==4096);
    auto seals=fcntl(fd,F_GET_SEALS);need(seals>=0&&(seals&(F_SEAL_SEAL|F_SEAL_SHRINK|F_SEAL_GROW))==(F_SEAL_SEAL|F_SEAL_SHRINK|F_SEAL_GROW));
    need((fcntl(fd,F_GETFL)&O_ACCMODE)==O_RDWR);
    void*p=mmap(nullptr,4096,PROT_READ|PROT_WRITE,MAP_SHARED,fd,0);need(p!=MAP_FAILED);return static_cast<plauth::Page*>(p);
}
inline nlohmann::json snapshot(plauth::Page*p){
    auto s=p->state.load();auto e=extra(p);
    return {{"schema","PC_PLM_SHARED_AUTHORITY_V1"},{"state",s},{"claims",s&plauth::COUNT},
        {"generation",(s&plauth::GENERATION)>>32},{"active",bool(s&plauth::ACTIVE)},
        {"revoked",bool(s&plauth::REVOKED)},{"unknown_io",bool(s&(plauth::IO|plauth::START|plauth::LOAD))},
        {"start_intent",bool(s&plauth::START)},{"phase",e->phase.load()},
        {"grant_limit",p->limit.load()},{"request_end",e->request_end.load()},
        {"request_serial",e->request_serial.load()},{"request_sha256",request_digest(p)},
        {"context_sha256",hex(p->context)},{"worker_pid",p->worker_pid},{"worker_start_ticks",p->worker_ticks},
        {"hardware_completions",nullptr},{"BOARD","NOT_TESTED"},{"release_allowed",false}};
}
struct Writer {
    plauth::Page*p=nullptr;std::mutex mutex;
    Writer(int fd,uint64_t hi,uint64_t lo,uint64_t deadline){
        p=map(fd);try{need(!p->magic&&hi&&lo&&deadline>now());
            new(p)plauth::Page{};new(extra(p))Extra{};p->magic=plauth::MAGIC;
            p->manager_pid=getpid();p->manager_ticks=plauth::ticks(getpid());p->epoch_hi=hi;p->epoch_lo=lo;
            p->expires_ns=deadline;p->max_age_ns=250000000;extra(p)->magic=EXT_MAGIC;
        }catch(...){munmap(p,4096);p=nullptr;throw;}}
    void healthy(uint64_t stamp){need(stamp&&stamp<=now()&&!(p->state.load()&plauth::REVOKED));
        auto old=p->healthy_ns.load();need(stamp>=old);p->healthy_ns=stamp;}
    void live(){need(p&&p->magic==plauth::MAGIC&&extra(p)->magic==EXT_MAGIC&&
        !(p->state.load()&plauth::REVOKED)&&now()<p->expires_ns.load());}
    void bind(uint64_t pid,uint64_t ticks,const std::string&digest){
        std::lock_guard<std::mutex> lock(mutex);live();need(!p->worker_pid&&extra(p)->phase.load()==UNBOUND&&
            ticks==plauth::ticks(pid));auto data=words(digest);p->worker_pid=pid;p->worker_ticks=ticks;
        std::memcpy(p->context,data.data(),32);p->limit=1;extra(p)->phase=LOADING;
        uint64_t zero=0;need(p->state.compare_exchange_strong(zero,plauth::ACTIVE|(1ULL<<32)));
    }
    void finish_load(){
        std::lock_guard<std::mutex> lock(mutex);live();auto s=p->state.load();
        need(extra(p)->phase.load()==LOADING&&(s&plauth::COUNT)==0&&(s&plauth::ACTIVE)&&
            !(s&(plauth::IO|plauth::START|plauth::LOAD|plauth::REVOKED)));
        need(p->state.compare_exchange_strong(s,s&~plauth::ACTIVE));p->limit=0;extra(p)->phase=IDLE;
    }
    void begin(uint64_t base,uint64_t budget,const std::string&digest){
        std::lock_guard<std::mutex> lock(mutex);live();auto s=p->state.load();auto e=extra(p);
        need(e->phase.load()==IDLE&&!(s&(plauth::ACTIVE|plauth::IO|plauth::START|plauth::LOAD|plauth::REVOKED))&&
            (s&plauth::COUNT)==base&&base<=5000&&budget&&budget<=5000-base&&e->request_serial.load()<3);
        auto data=words(digest);for(int i=0;i<4;++i)e->digest[i]=data[i];e->request_end=base+budget;
        p->limit=base;e->request_serial.fetch_add(1);e->phase=REQUEST;
        auto gen=((s&plauth::GENERATION)>>32)+1;need(gen>=2&&gen<=4);
        need(p->state.compare_exchange_strong(s,(s&~plauth::GENERATION)|(gen<<32)|plauth::ACTIVE));
    }
    void grant(uint64_t first,uint64_t last){
        std::lock_guard<std::mutex> lock(mutex);live();auto s=p->state.load();
        need(extra(p)->phase.load()==REQUEST&&(s&plauth::ACTIVE)&&
            !(s&(plauth::IO|plauth::START|plauth::LOAD|plauth::REVOKED))&&
            first==(s&plauth::COUNT)+1&&first==p->limit.load()+1&&last>=first&&last-first<72&&
            last<=extra(p)->request_end.load()&&last<=5000);
        p->limit=last;live();
    }
    void end(uint64_t count){
        std::lock_guard<std::mutex> lock(mutex);live();auto s=p->state.load();
        need(extra(p)->phase.load()==REQUEST&&(s&plauth::ACTIVE)&&
            !(s&(plauth::IO|plauth::START|plauth::LOAD|plauth::REVOKED))&&
            (s&plauth::COUNT)==count&&p->limit.load()==count);
        need(p->state.compare_exchange_strong(s,s&~plauth::ACTIVE));extra(p)->phase=IDLE;
    }
    uint64_t revoke()noexcept{return p->state.fetch_or(plauth::REVOKED)|plauth::REVOKED;}
    bool dispose(){if(!p)return true;revoke();if(p->state.load()&(plauth::IO|plauth::START|plauth::LOAD))return false;
        extra(p)->phase=CLOSED;munmap(p,4096);p=nullptr;return true;}
};
}
