#include "host_contract.hpp"
#include "release_gate.hpp"
#include <array>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <limits>
#include <vector>
static int count=0;
static void check(bool ok,const char*name){++count;if(!ok){std::cerr<<"FAIL "<<name<<'\n';std::exit(1);}}
int main(int argc,char**argv){
    if(argc!=2){std::cerr<<"usage: host-test PROJECT_ROOT\n";return 2;}
    const std::string root=argv[1];
    using namespace a07;
    for(auto nk: {std::array<uint32_t,2>{1,1},{33,129},{3584,1024},{1024,3584},{4864,4864}}){
        for(uint32_t t=1;t<=8;++t){Layout a;check(layout(nk[0],nk[1],t,a)==SP_OK,"valid layout");
            std::vector<uint8_t>w(a.w,0);std::vector<float>sw(a.sw/4,1),sx(t,1),y(a.y/4,0);std::vector<int8_t>x(a.x,0);
            check(weights(a,w.data(),w.size(),sw.data(),a.sw)==0,"valid weights");
            check(inputs(a,x.data(),a.x,sx.data(),a.sx,y.data(),a.y)==0,"valid inputs");
            check(output(a,y.data(),a.y)==0,"valid output");
            check(weights(a,w.data(),a.w-1,sw.data(),a.sw)==SP_BUFFER_TOO_SMALL,"short W");
            check(weights(a,w.data(),a.w,sw.data(),a.sw-1)==SP_BUFFER_TOO_SMALL,"short Sw");
            check(inputs(a,x.data(),a.x-1,sx.data(),a.sx,y.data(),a.y)==SP_BUFFER_TOO_SMALL,"short X");
            check(inputs(a,x.data(),a.x,sx.data(),a.sx-1,y.data(),a.y)==SP_BUFFER_TOO_SMALL,"short Sx");
            check(inputs(a,x.data(),a.x,sx.data(),a.sx,y.data(),a.y-1)==SP_BUFFER_TOO_SMALL,"short Y");
            w[0]=8;check(weights(a,w.data(),a.w,sw.data(),a.sw)==SP_NUMERIC_ERROR,"reserved low W");w[0]=0x80;
            check(weights(a,w.data(),a.w,sw.data(),a.sw)==SP_NUMERIC_ERROR,"reserved high W");w[0]=0;
            x[0]=-128;check(inputs(a,x.data(),a.x,sx.data(),a.sx,y.data(),a.y)==SP_NUMERIC_ERROR,"reserved X");x[0]=0;
            for(float bad:{0.f,-1.f,std::numeric_limits<float>::infinity(),std::numeric_limits<float>::quiet_NaN()}){
                sw[0]=bad;check(weights(a,w.data(),a.w,sw.data(),a.sw)==SP_NUMERIC_ERROR,"bad Sw");sw[0]=1;
                sx[0]=bad;check(inputs(a,x.data(),a.x,sx.data(),a.sx,y.data(),a.y)==SP_NUMERIC_ERROR,"bad Sx");sx[0]=1;
            }
            y[0]=std::numeric_limits<float>::infinity();check(output(a,y.data(),a.y)==SP_NUMERIC_ERROR,"nonfinite Y");y[0]=0;
            if(a.np>a.n){y[a.n]=1;check(output(a,y.data(),a.y)==SP_NUMERIC_ERROR,"N tail");y[a.n]=0;
                auto si=(uint64_t(a.n/32)*a.g)*32+a.n%32;sw[si]=2;
                check(weights(a,w.data(),a.w,sw.data(),a.sw)==SP_NUMERIC_ERROR,"N scale tail");sw[si]=1;
                auto wi=(uint64_t(a.n/32)*a.g)*128*16+(a.n%32)/2;w[wi]=uint8_t(1<<((a.n%2)*4));
                check(weights(a,w.data(),a.w,sw.data(),a.sw)==SP_NUMERIC_ERROR,"N W tail");w[wi]=0;
            }
            if(a.kp>a.k){x[a.k]=1;check(inputs(a,x.data(),a.x,sx.data(),a.sx,y.data(),a.y)==SP_NUMERIC_ERROR,"K X tail");x[a.k]=0;
                w[(a.k/128*128+a.k%128)*16]=1;
                check(weights(a,w.data(),a.w,sw.data(),a.sw)==SP_NUMERIC_ERROR,"K W tail");
            }
        }
    }
    Layout a;
    for(uint32_t v:{0u,4865u,UINT32_MAX}){check(layout(v,128,1,a)==SP_BAD_ARGUMENT,"bad N");check(layout(32,v,1,a)==SP_BAD_ARGUMENT,"bad K");}
    check(layout(32,128,0,a)==SP_BAD_ARGUMENT,"zero T");check(layout(32,128,9,a)==SP_BAD_ARGUMENT,"large T");
    check(fits_budget(10,5,5)&&!fits_budget(10,5,6)&&!fits_budget(0,0,0)&&!fits_budget(10,UINT64_MAX,1),"budget overflow/null");
    check(in_window(4096,4096,4096,4096),"BO exact window");
    check(!in_window(4096,4096,4095,1)&&!in_window(4096,4096,8192,1),"BO out of bounds");
    check(!in_window(4096,4096,8191,2)&&!in_window(UINT64_MAX,2,UINT64_MAX,1),"BO overflow");
    check(!in_window(0,0,0,1)&&!in_window(0,4096,0,0),"BO null/zero window");
    std::array<uint8_t,40> m{};write_le(m.data(),magic,4);write_le(m.data()+4,0xB3030002,4);write_le(m.data()+8,42,8);
    write_le(m.data()+20,1,4);write_le(m.data()+24,1,8);write_le(m.data()+32,2048,8);
    check(validate_meta(m.data(),40,0xB3030002,42,0,2048)==0,"meta valid bytes fixture, NOT device result");
    for(auto off:{0,4,8,20,24,32}){auto copy=m;copy[off]^=1;check(validate_meta(copy.data(),40,0xB3030002,42,0,2048)!=0,"meta mismatch");}
    check(validate_meta(m.data(),39,0xB3030002,42,0,2048)==SP_BUFFER_TOO_SMALL,"short meta");
    auto wrap=m;write_le(wrap.data()+24,0,8);
    check(validate_meta(wrap.data(),40,0xB3030002,42,UINT64_MAX,2048)==SP_OK,"private counter modulo wrap");
    check(validate_meta(m.data(),40,0xB3030002,42,UINT64_MAX,2048)==SP_DEVICE_ERROR,"incorrect wrap rejected");
    int expected[]={0,2,1,3,1,9,8};for(uint32_t i=0;i<7;++i)check(private_status(i)==expected[i],"private/public mapping");
    Lifecycle life;check(life.begin(0,1)==SP_BAD_ARGUMENT,"zero job");check(life.begin(1,0)==SP_BAD_ARGUMENT,"infinite wait refused");
    check(life.begin(1,5)==0&&life.idle()==SP_BUSY,"running holds ownership");
    check(life.begin(2,5)==SP_BUSY,"one inflight");check(life.completed_and_validated()==0,"validated completion");
    check(life.begin(1,5)==SP_BAD_ARGUMENT,"replayed job");check(life.begin(2,5)==0,"next job");life.poison();
    check(life.idle()==SP_POISONED&&life.begin(3,5)==SP_POISONED&&life.completed_and_validated()==SP_POISONED,"poison retains ownership forever without recovery");
    auto cfg=nlohmann::json::parse(std::ifstream(root+"/modules/linear_A/xrt/config.pending.json"));
    auto source=nlohmann::json::parse(std::ifstream(root+"/hw/linear_A/KERNEL_SOURCE.json"));
    check(release_gate(cfg,source)==SP_UNSUPPORTED,"actual repository remains fail closed");
    // Synthetic *policy documents*, not a fake kernel or hardware computation.
    auto policy=source;policy["accepted"]=true;policy["frozen"]=true;policy["production_or_A07_link_allowed"]=true;
    check(release_gate(cfg,policy)==SP_UNSUPPORTED,"device access still disabled");
    auto enabled=cfg;enabled["allow_device_access"]=true;
    check(release_gate(enabled,policy)==SP_OK,"pure first gate; subsequent real profile/hash/device checks remain mandatory");
    for(auto key:{"accepted","frozen","production_or_A07_link_allowed"}){auto p=policy;p[key]=false;
        check(release_gate(enabled,p)==SP_UNSUPPORTED,"each release latch");p[key]="true";
        check(release_gate(enabled,p)==SP_UNSUPPORTED,"string cannot enable release");}
    auto bad=enabled;bad["fallback"]="cpu";check(release_gate(bad,policy)==SP_CONTRACT_MISMATCH,"no fallback");
    bad=enabled;bad["contract_sha256"]="bad";check(release_gate(bad,policy)==SP_CONTRACT_MISMATCH,"contract mismatch");
    bad=enabled;bad["allow_device_access"]="true";check(release_gate(bad,policy)==SP_UNSUPPORTED,"string cannot enable device");
    std::cout<<"{\"domain\":\"PC_HOST_LOGIC_ONLY\",\"assertions\":"<<count<<",\"device_calls\":0,\"BOARD\":\"NOT_TESTED\"}\n";
}
