#include "supervisor_gate.hpp"
#include "managed_lock.hpp"
#include <cstdio>
#include <cstdlib>
#include <iostream>
int main(){
    try {
        int held=a11::borrow_lock(std::stoi(std::getenv("TEST_LOCK_FD")),getppid(),
                    std::stoull(std::getenv("TEST_PARENT_TICKS")),std::getenv("TEST_LOCK_PATH"));
        puts("{\"type\":\"ready\"}");fflush(stdout);
        std::string line;uint64_t job=0;
        while(std::getline(std::cin,line)){
            auto r=nlohmann::json::parse(line);if(r.value("op",std::string())=="shutdown")break;
            try{a12::permit("submit",++job);puts("{\"type\":\"allowed\"}");}
            catch(const std::exception&){puts("{\"type\":\"denied\"}");}
            fflush(stdout);
        }
        close(held);return 0;
    }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 2;}
}
