#pragma once
// Private A12 control channel. No unlock, takeover, device calls or auto-recovery.
#include "json.hpp"
#include <cstdlib>
#include <cstring>
#include <stdexcept>
#include <string>
#include <sys/socket.h>
#include <unistd.h>
namespace a12 {
inline void permit(const char*phase,uint64_t job) {
#ifdef SP_LINEAR_CONTROL_TEST
    (void)phase;(void)job; // Compile-time PC-only XRT doubles; never in ARM library.
#else
    const char*value=std::getenv("SP_A12_CONTROL_FD");
    if(!value)throw std::runtime_error("A12 parent permission channel absent");
    int fd=std::stoi(value);struct ucred peer{};socklen_t len=sizeof(peer);
    if(fd<3||getsockopt(fd,SOL_SOCKET,SO_PEERCRED,&peer,&len)||peer.pid!=getppid())
        throw std::runtime_error("A12 permission peer is not direct manager");
    static uint64_t sequence=0;
    auto request=nlohmann::json{{"sequence",++sequence},{"phase",phase},{"job",job},{"pid",getpid()}}.dump()+"\n";
    size_t sent=0;
    while(sent<request.size()){auto n=send(fd,request.data()+sent,request.size()-sent,MSG_NOSIGNAL);if(n<=0)throw std::runtime_error("A12 permit send");sent+=n;}
    std::string reply;char ch;
    while(reply.size()<4096){if(recv(fd,&ch,1,0)!=1)throw std::runtime_error("A12 manager lost");if(ch=='\n')break;reply+=ch;}
    auto response=nlohmann::json::parse(reply);
    if(response.value("allow",false)!=true||response.at("sequence")!=sequence)
        throw std::runtime_error("A12 manager denied operation");
#endif
}
}
