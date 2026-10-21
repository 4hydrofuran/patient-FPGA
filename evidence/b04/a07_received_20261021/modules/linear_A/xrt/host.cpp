// Independent real C-ABI consumer. Built for A53; no fake XRT or CPU fallback.
#include "sp_linear_v1.h"
#include <cstring>
#include <iostream>
#include <vector>
#include <unistd.h>
static int retain_if_unsafe(int rc){
    if(rc==SP_POISONED||rc==SP_BUSY){
        std::cerr<<"UNSAFE_TO_EXIT: hardware quiescence unproved; retaining process/library/BO ownership. Operator recovery required.\n";
        for(;;)::pause();
    }
    return rc;
}
int main(int argc,char**argv){
    if(argc!=3||(std::strcmp(argv[1],"--check-unavailable")&&std::strcmp(argv[1],"--execute-hand"))){
        std::cerr<<"usage: sp-linear-host --check-unavailable|--execute-hand trusted-config.json\n";return 2;
    }
    sp_linear_context*c=nullptr;int rc=sp_linear_open_v1(argv[2],&c);
    if(!std::strcmp(argv[1],"--check-unavailable")){
        if(c){retain_if_unsafe(sp_linear_close_v1(c));return 1;}
        std::cout<<"{\"operation\":\"open_only\",\"status_code\":"<<rc<<",\"compute_executed\":false}\n";
        return rc==SP_UNSUPPORTED?0:1;
    }
    if(rc){std::cerr<<"open status="<<rc<<'\n';return rc;}
    std::vector<uint8_t>w(2048,0);w[0]=0x21;w[16]=0xef;
    std::vector<float>sw(32,1),y(32,-999);int8_t x[128]={3,1};float sx=1;uint64_t handle=0;
    rc=sp_linear_load_v1(c,2,2,w.data(),w.size(),sw.data(),128,&handle);
    if(!rc){w.clear();sw.clear();rc=sp_linear_run_v1(c,handle,1,x,128,&sx,4,y.data(),128,1,5000);}
    if(!rc){for(unsigned i=0;i<32;++i)if(y[i]!=(i==0?2.f:i==1?4.f:0.f))rc=SP_NUMERIC_ERROR;}
    uint64_t bytes=0;int report_rc=sp_linear_report_v1(c,nullptr,0,&bytes);
    if(!report_rc&&bytes&&bytes<1024*1024){
        std::vector<char>report(bytes);report_rc=sp_linear_report_v1(c,report.data(),bytes,&bytes);
        if(!report_rc)std::cout<<report.data()<<'\n';
    }
    if(handle){int u=sp_linear_unload_v1(c,handle);retain_if_unsafe(u);if(!rc)rc=u;}
    int closed=sp_linear_close_v1(c);retain_if_unsafe(closed);
    return rc?rc:report_rc?report_rc:closed;
}
