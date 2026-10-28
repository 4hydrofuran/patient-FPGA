#pragma once
// A-owned PRIVATE page extension. The frozen Page/Extra bytes are unchanged.
// This is a trusted-worker revocation protocol, not an isolation boundary.
#include "plm_control.hpp"
namespace generation {
using plm::need;
constexpr uint64_t MAGIC=0x41313247454e3031ULL,REVOKED=1ULL<<63;
constexpr uint64_t PC_FIXTURE=1,BOARD=2,LOADING=1,RESIDENT=2;
struct alignas(64) Slot {
    uint64_t magic;
    std::atomic<uint64_t> state,healthy_ns;
    uint64_t domain,deadline,epoch[4],identity[4],context[4],resident[4];
};
static_assert(sizeof(Slot)==192 && 192+sizeof(Slot)<=4096,"private generation slot geometry");
inline Slot* slot(plauth::Page*p){return reinterpret_cast<Slot*>(reinterpret_cast<char*>(p)+192);}
inline bool same(const uint64_t*a,const uint64_t*b){return std::memcmp(a,b,32)==0;}
inline void live(plauth::Page*p,uint64_t domain,uint64_t phase){
    auto s=slot(p);const auto now=plauth::now(),stamp=s->healthy_ns.load();
    need(s->magic==MAGIC&&s->domain==domain&&s->state.load()==phase&&
        !(p->state.load()&plauth::REVOKED)&&s->deadline==p->expires_ns.load()&&now<s->deadline&&
        stamp&&stamp<=now&&now-stamp<=p->max_age_ns.load());
}
class Reader {
    plauth::Page*p=nullptr;uint64_t domain=0,epoch[4]{},context[4]{};
public:
    ~Reader(){if(p)munmap(p,4096);}
    void attach(int fd,uint64_t expected,const std::string&ctx){
        need(!p);p=plm::map(fd);domain=expected;auto hash=plm::words(ctx);auto s=slot(p);
        live(p,domain,LOADING);need(same(s->context,hash.data())&&same(p->context,hash.data()));
        std::memcpy(epoch,s->epoch,32);std::memcpy(context,s->context,32);
    }
    void check(uint64_t phase)const{
        need(p);live(p,domain,phase);auto s=slot(p);
        need(same(epoch,s->epoch)&&same(context,s->context)&&same(context,p->context));
    }
    void revoke()noexcept{if(p){slot(p)->state.fetch_or(REVOKED);p->state.fetch_or(plauth::REVOKED);}}
    nlohmann::json report()const{return {{"attached",bool(p)},{"required_domain",domain},
        {"slot_state",p?slot(p)->state.load():0},{"healthy_ns",p?slot(p)->healthy_ns.load():0}};}
#ifdef SP_A12_PC_TEST
    void test_stale(){need(p&&domain==PC_FIXTURE);slot(p)->healthy_ns=0;}
#endif
};
template<uint64_t Domain> class Control {
    plm::Control original;Reader reader;
#ifdef SP_A12_PC_TEST
    bool test_original_start_committed=false;
#endif
    static std::string hash(const nlohmann::json&facts){
        auto text=facts.dump();unsigned char b[32];unsigned n=0;uint64_t w[4];
        need(EVP_Digest(text.data(),text.size(),b,&n,EVP_sha256(),nullptr)==1&&n==32);
        std::memcpy(w,b,32);return plm::hex(w);
    }
public:
    void configure(const nlohmann::json&facts){
        original.configure(facts);auto fd=std::getenv("SP_A12_PLM_PAGE_FD");need(fd);
        reader.attach(std::stoi(fd),Domain,hash(facts));
    }
    void attach(int,const uint64_t*){throw std::runtime_error("independent generation bootstrap required");}
    void bind_request(const std::string&d){reader.check(RESIDENT);original.bind_request(d);reader.check(RESIDENT);}
    void before_load(){reader.check(LOADING);original.before_load();reader.check(LOADING);}
    void before_transfer(uint64_t j,uint32_t t){reader.check(RESIDENT);original.before_transfer(j,t);reader.check(RESIDENT);}
    void before_start(uint64_t j){reader.check(RESIDENT);original.before_start(j);
#ifdef SP_A12_PC_TEST
        const auto test=std::getenv("SP_A12_GEN_TEST_STALE_SLOT");
        if(Domain==PC_FIXTURE&&j==5&&test&&std::string(test)=="1"){
            test_original_start_committed=true;reader.test_stale();
        }
#endif
        reader.check(RESIDENT);
    }
    void complete(uint64_t j,bool load=false){reader.check(load?LOADING:RESIDENT);original.complete(j,load);reader.check(load?LOADING:RESIDENT);}
    void end_request(){reader.check(RESIDENT);original.end_request();reader.check(RESIDENT);}
    void fail()noexcept{reader.revoke();original.fail();}
    bool unknown()const noexcept{return original.unknown();}
    bool maintenance_allowed()const noexcept{try{reader.check(RESIDENT);return original.maintenance_allowed();}catch(...){return false;}}
    nlohmann::json report()const{auto r=original.report();auto g=reader.report();g.update({{"schema","A12_GENERATION_CONSUMER_V1"},
        {"expected_domain",Domain},{"Board_approval",false},{"hardware_completions",nullptr}});
#ifdef SP_A12_PC_TEST
        g["PC_test_original_start_committed"]=test_original_start_committed;
#endif
        r["generation_consumer"]=g;return r;}
};
// Manager-only writer. No method can reset/rebind/resurrect a slot.
struct Writer {
    plauth::Page*p=nullptr;
    Writer(int fd,const char*id,const char*epoch){
        p=plm::map(fd);try{
            need(p->manager_pid==uint64_t(getpid())&&p->manager_ticks==plauth::ticks(getpid())&&
                !slot(p)->magic&&plm::extra(p)->phase.load()==plm::UNBOUND);
            auto i=plm::words(id),e=plm::words(epoch);new(slot(p))Slot{};auto s=slot(p);
            s->domain=PC_FIXTURE; // There is deliberately NO Board-positive issuer.
            s->deadline=p->expires_ns.load();std::memcpy(s->identity,i.data(),32);std::memcpy(s->epoch,e.data(),32);s->magic=MAGIC;
        }catch(...){munmap(p,4096);p=nullptr;throw;}
    }
    ~Writer(){if(p)munmap(p,4096);}
    void health(uint64_t stamp){auto s=slot(p);auto now=plauth::now();need(!(s->state.load()&REVOKED)&&
        !(p->state.load()&plauth::REVOKED)&&stamp&&stamp<=now&&stamp>=s->healthy_ns.load());s->healthy_ns=stamp;
        need(!(s->state.load()&REVOKED));}
    void bind(const char*ctx){auto s=slot(p);auto h=plm::words(ctx);need(plm::extra(p)->phase.load()==plm::LOADING&&
        same(p->context,h.data())&&s->state.load()==0);std::memcpy(s->context,h.data(),32);
        uint64_t zero=0;need(s->state.compare_exchange_strong(zero,LOADING));live(p,PC_FIXTURE,LOADING);}
    void resident(const char*sha){auto s=slot(p);auto h=plm::words(sha);live(p,PC_FIXTURE,LOADING);
        need(plm::extra(p)->phase.load()==plm::IDLE&&!(p->state.load()&(plauth::ACTIVE|plauth::COUNT|plauth::IO|plauth::START|plauth::LOAD)));
        std::memcpy(s->resident,h.data(),32);uint64_t expected=LOADING;need(s->state.compare_exchange_strong(expected,RESIDENT));}
    uint64_t revoke()noexcept{auto s=slot(p);s->state.fetch_or(REVOKED);p->state.fetch_or(plauth::REVOKED);return s->state.load();}
    bool disposable()const{return !(p->state.load()&(plauth::ACTIVE|plauth::IO|plauth::START|plauth::LOAD));}
};
}
