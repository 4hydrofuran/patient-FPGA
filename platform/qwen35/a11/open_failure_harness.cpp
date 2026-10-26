// PC CONTROL DOUBLES ONLY. No device, PL or real DMA is accessible here.
#include "sp_linear_v1.h"
#include "control_xrt.hpp"
#include "json.hpp"
#include <iostream>
#include <stdexcept>
#include <string>

int main(int argc,char** argv) try {
    if(argc!=4)return 2;
    const std::string fault=argv[1];
    control::fault=fault=="normal"||fault.rfind("policy_",0)==0?"":fault;
    const int expected=std::stoi(argv[3]);
    sp_linear_context* ctx=nullptr;
    const auto status=sp_linear_open_v1(argv[2],&ctx);
    if(status!=expected)throw std::runtime_error("unexpected status");
    if(control::starts!=0)throw std::runtime_error("open submitted a computation");
    if(status==SP_OK){
        if(!ctx||sp_linear_close_v1(ctx)!=SP_OK)throw std::runtime_error("normal close failed");
    }else if(ctx)throw std::runtime_error("failed open exposed a context");
    if(control::starts!=0||control::live!=0)throw std::runtime_error("stub resources/submissions differ");
    std::cout<<nlohmann::json{{"domain","PC_CONTROL_DOUBLE_NOT_FPGA"},
        {"status_code",status},{"mock_submissions",control::starts},
        {"live_stub_allocations",control::live},{"BOARD","NOT_TESTED"}}.dump()<<'\n';
    return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
