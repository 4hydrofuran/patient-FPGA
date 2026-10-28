// Private manager-only atomic writer. Not linked into the backend or router DSO.
#include "plm_page.hpp"
#define PLM_API extern "C" __attribute__((visibility("default")))
PLM_API void* a12_plm_writer_open_v1(int fd,uint64_t hi,uint64_t lo,uint64_t deadline){try{return new plm::Writer(fd,hi,lo,deadline);}catch(...){return nullptr;}}
PLM_API int a12_plm_health_v1(void*h,uint64_t stamp){try{static_cast<plm::Writer*>(h)->healthy(stamp);return 0;}catch(...){return 1;}}
PLM_API int a12_plm_bind_v1(void*h,uint64_t pid,uint64_t ticks,const char*sha){try{plm::need(sha);static_cast<plm::Writer*>(h)->bind(pid,ticks,sha);return 0;}catch(...){return 1;}}
PLM_API int a12_plm_load_end_v1(void*h){try{static_cast<plm::Writer*>(h)->finish_load();return 0;}catch(...){return 1;}}
PLM_API int a12_plm_begin_v1(void*h,uint64_t base,uint64_t budget,const char*sha){try{plm::need(sha);static_cast<plm::Writer*>(h)->begin(base,budget,sha);return 0;}catch(...){return 1;}}
PLM_API int a12_plm_grant_v1(void*h,uint64_t first,uint64_t last){try{static_cast<plm::Writer*>(h)->grant(first,last);return 0;}catch(...){return 1;}}
PLM_API int a12_plm_end_v1(void*h,uint64_t count){try{static_cast<plm::Writer*>(h)->end(count);return 0;}catch(...){return 1;}}
PLM_API uint64_t a12_plm_revoke_v1(void*h){return static_cast<plm::Writer*>(h)->revoke();}
PLM_API uint64_t a12_plm_state_v1(void*h){return static_cast<plm::Writer*>(h)->p->state.load();}
PLM_API int a12_plm_snapshot_v1(void*h,char*out,uint64_t size){try{auto s=plm::snapshot(static_cast<plm::Writer*>(h)->p).dump();plm::need(out&&size>s.size());std::memcpy(out,s.c_str(),s.size()+1);return 0;}catch(...){return 1;}}
PLM_API int a12_plm_writer_close_v1(void*h){auto p=static_cast<plm::Writer*>(h);if(!p->dispose())return 1;delete p;return 0;}
