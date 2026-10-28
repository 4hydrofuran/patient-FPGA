// PC-only real private Control/Writer boundaries. No model, XRT or claimed Y.
#include "plm_control.hpp"
#include <sys/wait.h>
#include <thread>
#include <chrono>
#include <iostream>

int main(){
    using plauth::need;
    int page=memfd_create("RESIDENT_PC_CONTROL_BOUNDARY",MFD_ALLOW_SEALING);
    need(page>=3&&!ftruncate(page,4096));
    need(fcntl(page,F_ADD_SEALS,F_SEAL_SEAL|F_SEAL_SHRINK|F_SEAL_GROW)==0);
    plm::Writer writer(page,1,2,plauth::now()+10000000000ULL);
    int sockets[2];need(!socketpair(AF_UNIX,SOCK_SEQPACKET,0,sockets));
    auto pid=fork();need(pid>=0);
    if(pid==0){
        int stage=0;
        try{
            close(sockets[0]);setenv("SP_A12_PLM_FD",std::to_string(sockets[1]).c_str(),1);
            setenv("SP_A12_PLM_PAGE_FD",std::to_string(page).c_str(),1);
            stage=1;plm::Control control;control.configure({{"domain","PC_CONTROL_ONLY_NOT_MODEL"}});
            char configured='C';need(write(sockets[1],&configured,1)==1);
            auto p=plm::map(page);
            for(uint64_t i=1;i<=9;++i){
                stage=int(10+i);char token;need(read(sockets[1],&token,1)==1&&token=='B');
                control.bind_request(plm::request_digest(p));
                need(!control.maintenance_allowed());control.end_request();
                token='E';need(write(sockets[1],&token,1)==1);
                need(read(sockets[1],&token,1)==1&&token=='I');
                need(control.maintenance_allowed());
                for(auto flag:{plauth::ACTIVE,plauth::REVOKED,plauth::IO,plauth::START,plauth::LOAD}){
                    p->state.fetch_or(flag);need(!control.maintenance_allowed());p->state.fetch_and(~flag);
                }
                token='O';need(write(sockets[1],&token,1)==1);
            }
            need(control.report().at("request_limit")==9);
            munmap(p,4096);_exit(0);
        }catch(...){std::cerr<<"child boundary stage "<<stage<<" refused\n";_exit(2);}
    }
    close(sockets[1]);char buffer[8192];auto n=recv(sockets[0],buffer,sizeof buffer,0);need(n>0);
    auto bind=nlohmann::json::parse(buffer,buffer+n);
    writer.healthy(plauth::now());writer.bind(pid,plauth::ticks(pid),bind.at("context_sha256"));
    auto reply=nlohmann::json{{"schema","PC_PLM_BACKEND_WIRE_V1"},{"sequence",1},{"allow",true},
                            {"context_sha256",bind.at("context_sha256")}}.dump();
    need(send(sockets[0],reply.data(),reply.size(),0)==ssize_t(reply.size()));
    char configured;need(read(sockets[0],&configured,1)==1&&configured=='C');
    writer.finish_load();
    for(uint64_t i=1;i<=9;++i){
        writer.begin(0,1,std::string(64,'a'));char token='B';need(write(sockets[0],&token,1)==1);
        need(read(sockets[0],&token,1)==1&&token=='E');writer.end(0);token='I';need(write(sockets[0],&token,1)==1);
        need(read(sockets[0],&token,1)==1&&token=='O');
    }
    bool rejected=false;try{writer.begin(0,1,std::string(64,'b'));}catch(...){rejected=true;}need(rejected);
    int status=0;need(waitpid(pid,&status,0)==pid&&WIFEXITED(status)&&WEXITSTATUS(status)==0);
    need((writer.p->state.load()&plauth::COUNT)==0&&plm::extra(writer.p)->request_serial.load()==9);
    need(writer.dispose());close(page);close(sockets[0]);
    std::cout<<"PASS_REAL_CONTROL_NINE_NOOP_REQUESTS_TENTH_REFUSED_AND_MAINTENANCE_FLAGS_45\n";
}
