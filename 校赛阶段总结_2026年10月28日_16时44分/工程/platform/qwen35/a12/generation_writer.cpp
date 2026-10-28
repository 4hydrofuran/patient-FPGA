#include "generation_slot.hpp"
#define GEN_API extern "C" __attribute__((visibility("default")))
GEN_API void* a12_gen_open_v1(int fd,const char*id,const char*epoch){try{generation::need(id&&epoch);return new generation::Writer(fd,id,epoch);}catch(...){return nullptr;}}
GEN_API int a12_gen_health_v1(void*h,uint64_t stamp){try{static_cast<generation::Writer*>(h)->health(stamp);return 0;}catch(...){return 1;}}
GEN_API int a12_gen_bind_v1(void*h,const char*ctx){try{generation::need(ctx);static_cast<generation::Writer*>(h)->bind(ctx);return 0;}catch(...){return 1;}}
GEN_API int a12_gen_resident_v1(void*h,const char*sha){try{generation::need(sha);static_cast<generation::Writer*>(h)->resident(sha);return 0;}catch(...){return 1;}}
GEN_API uint64_t a12_gen_revoke_v1(void*h){return static_cast<generation::Writer*>(h)->revoke();}
GEN_API int a12_gen_close_v1(void*h){auto w=static_cast<generation::Writer*>(h);w->revoke();if(!w->disposable())return 1;delete w;return 0;}
