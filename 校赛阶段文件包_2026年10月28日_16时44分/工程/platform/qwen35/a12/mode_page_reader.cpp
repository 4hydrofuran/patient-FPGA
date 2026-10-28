// PC observer only: no write mapping, reinitialization, device or math API.
#if !defined(__x86_64__) || !defined(SP_A12_PC_TEST)
#error "mode reader is x86_64 PC test only"
#endif
#include "prefix_cache.hpp"
#include "microbatch_guard_read_layout.hpp"
#include <cstdio>
#include <cstring>

extern "C" __attribute__((visibility("default")))
int a12_pc_mode_read_page_v1(int fd,char*out,uint64_t capacity){
    mb::Page*p=nullptr;
    try{
        mb::need(out&&capacity>=512,"PC page reader output too small");p=mb::map(fd,false);
        auto magic=mb::load(&p->magic);mb::need(magic==mb::MAGIC,"PC page reader version differs");
        auto g=mb::load(&p->gate);
        auto s=nlohmann::json{{"schema","PC_MODE_PAGE_OBSERVATION_V1"},{"gate",g},
            {"manager_pid",mb::load(&p->manager)},{"worker_pid",mb::load(&p->worker_pid)},
            {"worker_start_ticks",mb::load(&p->worker_start)},
            {"manager_epoch",mb::hex(mb::load(&p->epoch_hi),mb::load(&p->epoch_lo))},
            {"shared_claims",g&mb::COUNT},{"active",bool(g&mb::ACTIVE)},
            {"revoked",bool(g&mb::REVOKED)},{"inflight_or_unknown",bool(g&mb::INFLIGHT)},
            {"request_generation",mb::generation(g)}}.dump();
        mb::need(s.size()+1<=capacity,"PC page reader bound");std::memcpy(out,s.c_str(),s.size()+1);
        munmap(p,4096);return 0;
    }catch(...){if(p)munmap(p,4096);return -1;}
}
