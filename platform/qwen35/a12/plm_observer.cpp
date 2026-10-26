// RO atomic observation only; no writer/lease/release API is linked here.
#include "plm_page.hpp"
extern "C" __attribute__((visibility("default"))) int a12_plm_observe_fd_v1(int fd,char*out,uint64_t cap){
    void*p=MAP_FAILED;
    try{
        struct stat st{};plm::need(fd>=3&&!fstat(fd,&st)&&S_ISREG(st.st_mode)&&st.st_size==4096&&(fcntl(fd,F_GETFL)&O_ACCMODE)==O_RDONLY);
        p=mmap(nullptr,4096,PROT_READ,MAP_SHARED,fd,0);plm::need(p!=MAP_FAILED);auto page=static_cast<plauth::Page*>(p);
        plm::need(page->magic==plauth::MAGIC&&plm::extra(page)->magic==plm::EXT_MAGIC);
        auto text=plm::snapshot(page).dump();plm::need(out&&cap>text.size());std::memcpy(out,text.c_str(),text.size()+1);munmap(p,4096);return 0;
    }catch(...){if(p!=MAP_FAILED)munmap(p,4096);return 1;}
}
