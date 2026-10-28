#include "managed_lock.hpp"
#include <iostream>
int main(int argc,char**argv) {
    if(argc!=5)return 2;
    try {
        int fd=a11::borrow_lock(std::stoi(argv[1]),std::stoi(argv[2]),std::stoull(argv[3]),argv[4]);
        close(fd);
        std::cout<<"PASS_PC_INHERITED_LOCK_CLOSED_WITHOUT_UNLOCK\n";
        return 0;
    } catch(const std::exception& e) {
        std::cerr<<e.what()<<'\n';return 3;
    }
}
