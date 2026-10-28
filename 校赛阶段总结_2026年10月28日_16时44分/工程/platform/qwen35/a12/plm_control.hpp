#pragma once
// Private backend lane, separate from the UNCHANGED legacy router/open/load wire.
#include "plm_page.hpp"
#include <cstdlib>
#include <memory>
#include <sys/socket.h>
#include <openssl/evp.h>
namespace plm {
class Control {
    plauth::Page*p=nullptr;int fd=-1,pagefd=-1;uint64_t sequence=0,generation=0,last=0,batches=0,seen_generation=1;
    uint32_t grant_t=0;
    std::string context,request;std::unique_ptr<plauth::Gate> gate;
    nlohmann::json exchange(nlohmann::json q){
        need(fd>=3);struct ucred peer{};socklen_t n=sizeof peer;int kind=0;socklen_t kn=sizeof kind;
        need(!getsockopt(fd,SOL_SOCKET,SO_PEERCRED,&peer,&n)&&peer.pid==getppid()&&
            !getsockopt(fd,SOL_SOCKET,SO_TYPE,&kind,&kn)&&kind==SOCK_SEQPACKET);
        q.update({{"schema","PC_PLM_BACKEND_WIRE_V1"},{"sequence",++sequence},{"pid",getpid()},
            {"worker_start_ticks",plauth::ticks(getpid())}});
        if(!context.empty())q["context_sha256"]=context;
        auto wire=q.dump();need(wire.size()<=8192);
        need(send(fd,wire.data(),wire.size(),MSG_NOSIGNAL)==ssize_t(wire.size()));
        pollfd in{fd,POLLIN,0};need(poll(&in,1,2000)==1);char buffer[8193];
        auto got=recv(fd,buffer,sizeof buffer,MSG_TRUNC);need(got>0&&got<=8192);
        auto r=nlohmann::json::parse(buffer,buffer+got);
        need(r.at("sequence")==sequence&&r.at("allow")==true&&r.at("schema")=="PC_PLM_BACKEND_WIRE_V1");return r;
    }
    void request_live(){
        need(p&&extra(p)->magic==EXT_MAGIC&&extra(p)->phase.load()==REQUEST&&generation>=2&&
            (p->state.load()&plauth::GENERATION)==(generation<<32)&&
            (p->state.load()&plauth::ACTIVE)&&!(p->state.load()&plauth::REVOKED)&&request_digest(p)==request);
    }
public:
    ~Control(){gate.reset();if(p)munmap(p,4096);}
    void configure(const nlohmann::json&facts){
        need(!p);const char*f=std::getenv("SP_A12_PLM_FD"),*pf=std::getenv("SP_A12_PLM_PAGE_FD");need(f&&pf);
        fd=std::stoi(f);pagefd=std::stoi(pf);p=map(pagefd);
        auto text=facts.dump();unsigned char bytes[32];unsigned n=0;
        need(EVP_Digest(text.data(),text.size(),bytes,&n,EVP_sha256(),nullptr)==1&&n==32);
        uint64_t hash[4];std::memcpy(hash,bytes,32);context=hex(hash);
        auto reply=exchange({{"phase","bind"},{"facts",facts},{"context_sha256",context}});
        need(reply.at("context_sha256")==context&&extra(p)->phase.load()==LOADING&&
            p->worker_pid==uint64_t(getpid())&&p->worker_ticks==plauth::ticks(getpid()));
        gate=std::make_unique<plauth::Gate>();gate->attach(pagefd,hash);
    }
    void attach(int,const uint64_t*){throw std::runtime_error("PLM requires manager bootstrap; scalar attach disabled");}
    void bind_request(const std::string&digest){
        need(p&&request.empty()&&!unknown()&&extra(p)->phase.load()==REQUEST);
        request=digest;generation=(p->state.load()&plauth::GENERATION)>>32;
        need(generation>seen_generation&&generation<=4);seen_generation=generation;last=p->state.load()&plauth::COUNT;
        gate.reset();request_live();need(last==p->limit.load());
    }
    void before_load(){need(p&&extra(p)->phase.load()==LOADING&&request.empty()&&gate);gate->before_load();}
    void before_transfer(uint64_t job,uint32_t t){
        request_live();
        if(job>last){
            auto reply=exchange({{"phase","batch"},{"job",job},{"T",t},{"generation",generation},{"request_sha256",request}});
            const auto end=reply.at("last_job").get<uint64_t>();
            need(reply.at("first_job")==job&&end>=job&&end-job<72&&reply.at("generation")==generation&&
                reply.at("request_sha256")==request&&reply.at("context_sha256")==context&&
                reply.at("deadline_monotonic_ns")==p->expires_ns.load()&&end<=extra(p)->request_end.load()&&end==p->limit.load());
            last=end;grant_t=t;++batches;
        }
        request_live();need(job<=last&&t==grant_t);
        if(!gate){auto hash=words(context);gate=std::make_unique<plauth::Gate>();gate->attach(pagefd,hash.data());}
        gate->before_transfer(job);
    }
    void before_start(uint64_t job){request_live();need(bool(gate));gate->before_start(job);}
    void complete(uint64_t job,bool load=false){
        need(bool(gate));if(load)need(extra(p)->phase.load()==LOADING);else request_live();gate->complete(job,load);
    }
    void end_request(){request_live();need(!unknown()&&(p->state.load()&plauth::COUNT)==last);
        request.clear();generation=0;last=0;gate.reset();}
    void fail()noexcept{if(p)p->state.fetch_or(plauth::REVOKED);}
    bool unknown()const noexcept{return p&&(p->state.load()&(plauth::IO|plauth::START|plauth::LOAD));}
    bool maintenance_allowed()const noexcept{return p&&request.empty()&&extra(p)->phase.load()==IDLE&&
        extra(p)->request_serial.load()==3&&!(p->state.load()&(plauth::ACTIVE|plauth::REVOKED|plauth::IO|plauth::START|plauth::LOAD));}
    nlohmann::json report()const{return {{"schema","PC_PLM_BACKEND_CONTROL_V1"},{"batches",batches},
        {"bound_context_sha256",context},{"bound_request_sha256",request},{"local_generation",generation},
        {"page",p?snapshot(p):nlohmann::json(nullptr)},{"hardware_completions",nullptr}};}
};
}
