#pragma once
#include <chrono>
#include <csignal>
#include <pthread.h>
#include <stdexcept>
#include <thread>
namespace a10 {
inline void block_exit_signals(){
    sigset_t s;sigemptyset(&s);
    for(int n:{SIGINT,SIGTERM,SIGHUP,SIGQUIT})sigaddset(&s,n);
    if(pthread_sigmask(SIG_BLOCK,&s,nullptr)!=0)throw std::runtime_error("cannot block exit signals");
}
inline bool cancelled(){
    sigset_t s;if(sigpending(&s)!=0)throw std::runtime_error("sigpending");
    for(int n:{SIGINT,SIGTERM,SIGHUP,SIGQUIT})if(sigismember(&s,n))return true;
    return false;
}
// Requires block_exit_signals before ANY XRT-created threads. No signals are
// unblocked here. SIGKILL/power loss remain outside userspace's safety guarantee.
[[noreturn]] inline void park_owner(){
    for(;;)std::this_thread::sleep_for(std::chrono::seconds(1));
}
}
