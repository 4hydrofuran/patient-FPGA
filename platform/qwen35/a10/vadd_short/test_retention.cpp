// POSIX control fixture only: child has NO XRT library, BO, or device access.
#include "retention.hpp"
#include <iostream>
#include <poll.h>
#include <sys/wait.h>
#include <unistd.h>
int main(){
    int p[2];if(pipe(p))return 1;
    const auto child=fork();if(child<0)return 2;
    if(child==0){
        close(p[0]);a10::block_exit_signals();
        const char ready='R';if(write(p[1],&ready,1)!=1)_exit(3);
        close(p[1]);a10::park_owner();
    }
    close(p[1]);int status=0;bool okay=true;
    pollfd fd{p[0],POLLIN,0};okay=poll(&fd,1,1000)==1;
    char ready=0;if(okay)okay=read(p[0],&ready,1)==1&&ready=='R';close(p[0]);
    for(int signal:{SIGINT,SIGTERM,SIGHUP,SIGQUIT}){
        if(okay)okay=kill(child,signal)==0;
        std::this_thread::sleep_for(std::chrono::milliseconds(30));
        if(okay)okay=waitpid(child,&status,WNOHANG)==0;
    }
    // Safe ONLY for this known, freshly forked no-device test child.
    kill(child,SIGKILL);waitpid(child,&status,0);
    if(!okay)return 4;
    std::cout<<"PASS_PC_SIGNAL_RETENTION_4_SIGNALS_NO_DEVICE; SIGKILL not protectable\n";
    return 0;
}
