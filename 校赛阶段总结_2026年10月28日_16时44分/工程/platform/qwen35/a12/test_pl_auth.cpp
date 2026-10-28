// Control-flow / ownership tests of the derived actual XRT backend. No FPGA math.
#include "sp_linear_v1.h"
#include "pl_auth_gate.hpp"
#include "control_xrt.hpp"
#include "json.hpp"
#include <algorithm>
#include <fstream>
#include <iostream>
#include <openssl/evp.h>
#include <sys/wait.h>
#include <sys/prctl.h>
using json=nlohmann::json;
extern "C" int32_t sp_a12_pl_candidate_context_v1(sp_linear_context*,char*,uint64_t,uint64_t*);
extern "C" int32_t sp_a12_pl_candidate_attach_v1(sp_linear_context*,int);
static unsigned checks=0;
static void check(bool ok,const char*why){++checks;if(!ok)throw std::runtime_error(why);}
template<class F>static void denied(F f,const char*why){bool yes=false;try{f();}catch(...){yes=true;}check(yes,why);}
static plauth::Page* page=nullptr;
static std::string inject,when;
static void observer(const std::string&e){
    if(e!=when)return;
    when.clear();
    if(inject=="revoke")page->state.fetch_or(plauth::REVOKED);
    else if(inject=="epoch")++page->epoch_hi;
    else if(inject=="generation")page->state.fetch_add(1ULL<<32);
    else if(inject=="context")++page->context[0];
    else if(inject=="health")page->healthy_ns=1;
    else if(inject=="deadline")page->expires_ns=1;
    else if(inject=="budget")page->limit=0;
}
static int make_page(const uint64_t hash[4]){
    int fd=int(syscall(SYS_memfd_create,"a12-pl-test-authority",MFD_CLOEXEC|MFD_ALLOW_SEALING));check(fd>=3,"memfd");
    check(!ftruncate(fd,4096),"page size");void*m=mmap(nullptr,4096,PROT_READ|PROT_WRITE,MAP_SHARED,fd,0);
    check(m!=MAP_FAILED,"map page");page=new(m)plauth::Page{};
    page->magic=plauth::MAGIC;page->manager_pid=getppid();page->manager_ticks=plauth::ticks(getppid());
    page->worker_pid=getpid();page->worker_ticks=plauth::ticks(getpid());page->epoch_hi=123;page->epoch_lo=456;
    std::memcpy(page->context,hash,32);page->state=plauth::ACTIVE|(1ULL<<32);
    page->limit=3;page->expires_ns=plauth::now()+30000000000ULL;page->healthy_ns=plauth::now();page->max_age_ns=1000000000;
    check(!fcntl(fd,F_ADD_SEALS,F_SEAL_SEAL|F_SEAL_GROW|F_SEAL_SHRINK),"geometry seals");return fd;
}
static std::string context(sp_linear_context*c){
    uint64_t n=0;check(!sp_a12_pl_candidate_context_v1(c,nullptr,0,&n),"context size");std::vector<char>b(n);
    check(!sp_a12_pl_candidate_context_v1(c,b.data(),n,&n),"context data");return b.data();
}
static json report(sp_linear_context*c){uint64_t n=0;check(!sp_linear_report_v1(c,nullptr,0,&n),"report size");
    std::vector<char>b(n);check(!sp_linear_report_v1(c,b.data(),n,&n),"report data");return json::parse(b.data());}
int main(int argc,char**argv)try{
    if(argc!=3)return 2;
    std::string mode=argv[1];
    if(mode=="parent_loss"||mode=="parent_loss_io"){
        check(!prctl(PR_SET_CHILD_SUBREAPER,1),"test-only reaping of owned descendants");
        int ready[2],result[2];check(!pipe(ready)&&!pipe(result),"parent-death test pipes");
        auto owner=fork();check(owner>=0,"fork real owner");
        if(!owner){
            auto worker=fork();if(worker<0)_exit(3);
            if(worker){close(ready[1]);close(result[0]);close(result[1]);
                char v=0;if(read(ready[0],&v,1)!=1)_exit(4);_exit(0);}
            try{
                close(ready[0]);close(result[0]);
                uint64_t hash[4]{1,2,3,4};int fd=make_page(hash);
                const auto parent=getppid();int identity=int(syscall(SYS_pidfd_open,parent,0));plauth::need(identity>=0);
                plauth::Gate gate;gate.attach(fd,hash);
                if(mode=="parent_loss_io")gate.before_transfer(1);
                char v='R';plauth::need(write(ready[1],&v,1)==1);pollfd p{identity,POLLIN,0};
                plauth::need(poll(&p,1,3000)==1);
                denied([&]{if(mode=="parent_loss_io")gate.before_start(1);else gate.before_transfer(1);},"actual manager death refused");
                check(bool(page->state.load()&plauth::IO)==(mode=="parent_loss_io"),"death does not erase IO ownership");
                v='P';plauth::need(write(result[1],&v,1)==1);_exit(0);
            }catch(...){_exit(5);}
        }
        close(ready[0]);close(ready[1]);close(result[1]);int status=0;
        check(waitpid(owner,&status,0)==owner&&WIFEXITED(status)&&WEXITSTATUS(status)==0,"owner actually exited");
        char v=0;check(read(result[0],&v,1)==1&&v=='P',"worker saw terminal pidfd and refused operation");
        check(waitpid(-1,&status,0)>0&&WIFEXITED(status)&&WEXITSTATUS(status)==0,"worker confirmed exited without forced signal");
        close(result[0]);
    }else if(mode=="core"){
        uint64_t hash[4]{1,2,3,4};int fd=make_page(hash);page->limit=72;
        plauth::Gate a,b;a.attach(fd,hash);b.attach(fd,hash);
        a.before_transfer(1);denied([&]{b.before_transfer(1);},"shared mapping cannot double debit");
        denied([&]{a.complete(1);},"IO without start cannot complete");
        denied([&]{b.before_start(2);},"wrong job cannot start");
        a.before_start(1);denied([&]{b.before_start(1);},"one start intent only");b.complete(1);
        for(uint64_t i=2;i<=72;++i){auto&g=i%2?a:b;g.before_transfer(i);g.before_start(i);g.complete(i);}
        check((page->state.load()&plauth::COUNT)==72,"shared seventy-two debit count");
        denied([&]{a.before_transfer(73);},"budget exhausted");
        page->state.fetch_or(plauth::REVOKED);denied([&]{b.before_load();},"revoked load refused");
        ::close(fd);
    }else{
        sp_linear_context*c=nullptr;check(!sp_linear_open_v1(argv[2],&c)&&c,"open real backend with PC XRT double");
        const auto facts=context(c);auto j=json::parse(facts);check(j["board_generation_approval"]=="UNBOUND","unbound remains explicit");
        check(j["io_addresses"].size()==4&&j["xclbin_uuid"]=="CONTROL_ONLY_UUID","facts from actual opened transport");
        unsigned char bytes[32];unsigned len=0;check(EVP_Digest(facts.data(),facts.size(),bytes,&len,EVP_sha256(),nullptr)&&len==32,"context SHA");
        uint64_t hash[4];std::memcpy(hash,bytes,32);int fd=make_page(hash);
        if(mode=="reopen_generation"){
            check(!sp_linear_close_v1(c),"close original generation");
            check(!sp_linear_open_v1(argv[2],&c),"reopen transport");
            check(json::parse(context(c))["context_generation"]!=j["context_generation"],"new random context generation");
            check(sp_a12_pl_candidate_attach_v1(c,fd)!=0,"old context page cannot authorize new open");
            check(!sp_linear_close_v1(c)&&control::live==0,"rejected reopen owns no transfers");
        }else if(mode=="wrong_worker"){
            page->worker_pid=getppid();check(sp_a12_pl_candidate_attach_v1(c,fd)!=0,"foreign worker identity refused");
            check(!sp_linear_close_v1(c)&&control::live==0,"worker mismatch no transfers");
        }else if(mode=="wrong_binding"){
            ++page->context[0];check(sp_a12_pl_candidate_attach_v1(c,fd)!=0,"foreign context refused");
            check(!sp_linear_close_v1(c)&&control::live==0,"no transfers, clean rejected attachment");
        }else if(mode=="readonly"){
            int ro=open(("/proc/self/fd/"+std::to_string(fd)).c_str(),O_RDONLY|O_CLOEXEC);
            check(ro>=0&&sp_a12_pl_candidate_attach_v1(c,ro)!=0,"read-only authority cannot debit");close(ro);
            check(!sp_linear_close_v1(c)&&control::live==0,"readonly rejection owns no transfers");
        }else{
            if(mode!="unbound")check(!sp_a12_pl_candidate_attach_v1(c,fd),"attach synthetic test authority");
            std::vector<uint8_t>w(2048,0);w[0]=0x21;std::vector<float>sw(32,1),y(32,-999);
            std::vector<int8_t>x(128,0);float sx=1;uint64_t h=0;
            if(mode=="load_fault")control::fault="to_3";
            const int loaded=sp_linear_load_v1(c,2,2,w.data(),w.size(),sw.data(),128,&h);
            if(mode=="load_fault"||mode=="unbound"){
                check(loaded!=0&&!h,"load denied without returned handle");
                check(control::live==(mode=="load_fault"?6u:4u),"uncertain upload retains both BOs; unbound creates none");
                check(mode!="load_fault"||(page->state.load()&(plauth::REVOKED|plauth::IO|plauth::LOAD))==
                    (plauth::REVOKED|plauth::IO|plauth::LOAD),"unknown upload remains latched");
                check(sp_linear_close_v1(c)==SP_POISONED,"cannot close failed owner");
            }else{
                check(!loaded&&h,"resident load");const auto allocations=control::allocations,live=control::live;
                auto run=[&](uint64_t id,uint32_t timeout=1000){return sp_linear_run_v1(c,h,1,x.data(),128,&sx,4,y.data(),128,id,timeout);};
                if(mode=="normal"){
                    for(uint64_t i=1;i<=3;++i)check(!run(i),"normal completion");
                    check((page->state.load()&(plauth::IO|plauth::START|plauth::REVOKED))==0,"quiescent after completion");
                    check((page->state.load()&plauth::COUNT)==3&&control::starts==3,"debit is start intent, not hardware count");
                    check(std::all_of(y.begin(),y.end(),[](float v){return v==0;}),"transport sentinel delivered");
                    check(run(3)==SP_BAD_ARGUMENT&&(page->state.load()&plauth::COUNT)==3,"duplicate not charged");
                    auto r=report(c);check(r["execution_kind"].is_null()&&r["hardware_done_count"].is_null(),"no fabricated FPGA metrics");
                    check(!sp_linear_unload_v1(c,h)&&!sp_linear_close_v1(c)&&control::live==0,"normal close");
                }else{
                    if(mode.rfind("prestart_",0)==0){inject=mode.substr(9);when="set_arg";control::observer=observer;}
                    else if(mode=="postmeta_revoke"){inject="revoke";when="from_11";control::observer=observer;}
                    else if(mode=="posty_revoke"){inject="revoke";when="from_9";control::observer=observer;}
                    else if(mode=="start_entry_revoke"){inject="revoke";when="start";control::observer=observer;}
                    else if(mode=="preio_revoke")page->state.fetch_or(plauth::REVOKED);
                    else if(mode=="over_budget")page->limit=0;
                    else control::fault=mode;
                    const int rc=run(1,mode=="timeout"?8:1000);check(rc!=0,"injected fault refused");
                    const bool no_io=mode=="preio_revoke"||mode=="over_budget";
                    const bool no_start=no_io||mode.rfind("prestart_",0)==0||mode=="to_7"||mode=="set_arg";
                    check(control::starts==(no_start?0u:1u),"no start across prestart denial");
                    check(no_io?control::count("to_7")==0:control::count("to_7")>=1,"pre-IO denial transfers none");
                    check((page->state.load()&plauth::REVOKED)!=0,"fault latches authority");
                    if(!no_io)check((page->state.load()&plauth::IO)!=0,"unknown IO cannot become idle");
                    check(control::allocations==allocations&&control::live==live,"all BO owners retained; no steady-state allocation");
                    check(std::all_of(y.begin(),y.end(),[](float v){return v==-999;}),"Y unchanged on fault");
                    check(sp_linear_close_v1(c)==SP_POISONED&&sp_linear_unload_v1(c,h)==SP_POISONED&&run(2)==SP_POISONED,"no close/unload/retry after fault");
                    auto r=report(c);check(r["status"]=="POISONED"&&r["output_consumable"]==false&&r["host_verified_completions"]==0,"no failed completion consumed");
                }
            }
        }
        ::close(fd);
    }
    std::cout<<json{{"domain","PC_XRT_CONTROL_DOUBLE_ONLY"},{"case",mode},{"checks",checks},
        {"actual_FPGA_calls",nullptr},{"BOARD","NOT_TESTED"},{"production_enabled",false}}.dump()<<'\n';return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}
