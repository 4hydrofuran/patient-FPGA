// Read-only compatibility observer: no writer or platform-release API exported.
#include "generation_slot.hpp"
#include <cstdio>
extern "C" __attribute__((visibility("default"))) int a12_plm_observe_fd_v1(int fd,char*out,uint64_t cap){
    void*m=MAP_FAILED;
    try{
        struct stat st{};plm::need(fd>=3&&!fstat(fd,&st)&&S_ISREG(st.st_mode)&&st.st_size==4096&&
            (fcntl(fd,F_GETFL)&O_ACCMODE)==O_RDONLY);
        const auto seals=fcntl(fd,F_GET_SEALS);plm::need(seals>=0&&(seals&(F_SEAL_SEAL|F_SEAL_SHRINK|F_SEAL_GROW))==(F_SEAL_SEAL|F_SEAL_SHRINK|F_SEAL_GROW));
        m=mmap(nullptr,4096,PROT_READ,MAP_SHARED,fd,0);plm::need(m!=MAP_FAILED);auto p=static_cast<plauth::Page*>(m);
        plm::need(p->magic==plauth::MAGIC&&plm::extra(p)->magic==plm::EXT_MAGIC);auto q=plm::snapshot(p);
        char epoch[33];std::snprintf(epoch,sizeof epoch,"%016llx%016llx",static_cast<unsigned long long>(p->epoch_hi),static_cast<unsigned long long>(p->epoch_lo));
        q["manager_pid"]=p->manager_pid;q["manager_start_ticks"]=p->manager_ticks;q["manager_epoch"]=epoch;
        auto slot=generation::slot(p);q["source_slot"]=nullptr;
        if(slot->magic==generation::MAGIC)q["source_slot"]={{"domain",slot->domain},{"state",slot->state.load()},
            {"epoch_sha256",plm::hex(slot->epoch)},{"identity_sha256",plm::hex(slot->identity)},{"context_sha256",plm::hex(slot->context)}};
        auto text=q.dump();plm::need(out&&cap>text.size());std::memcpy(out,text.c_str(),text.size()+1);munmap(m,4096);return 0;
    }catch(...){if(m!=MAP_FAILED)munmap(m,4096);return 1;}
}
