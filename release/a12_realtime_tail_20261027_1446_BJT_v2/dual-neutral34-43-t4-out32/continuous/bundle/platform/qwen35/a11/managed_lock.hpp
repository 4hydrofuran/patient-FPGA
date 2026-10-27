#pragma once
// No XRT, unlock, lock-file creation or takeover. The manager retains its own
// open-file-description throughout. This helper accepts only an inherited fd
// that already carries the parent's flock; opening the same inode is NOT enough.
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <string>

namespace a11 {
inline std::string text(const std::string& path) {
    std::ifstream f(path);
    if (!f) throw std::runtime_error("managed lock evidence unreadable");
    return std::string(std::istreambuf_iterator<char>(f), {});
}
inline unsigned long long start_ticks(int pid) {
    auto s=text("/proc/"+std::to_string(pid)+"/stat");
    auto end=s.rfind(')');
    if(end==std::string::npos)throw std::runtime_error("invalid proc stat");
    std::istringstream in(s.substr(end+2)); std::string value;
    for(int field=3;field<=22;++field)if(!(in>>value))throw std::runtime_error("short proc stat");
    return std::stoull(value);
}
inline bool parent_flock(const std::string& info, int parent) {
    std::istringstream rows(info); std::string row;
    while(std::getline(rows,row)) {
        std::istringstream in(row);std::string label,id,kind,advisory,mode;long owner=0;
        if(in>>label>>id>>kind>>advisory>>mode>>owner)
            if(label=="lock:"&&kind=="FLOCK"&&advisory=="ADVISORY"&&mode=="WRITE"&&owner==parent)return true;
    }
    return false;
}
inline int borrow_lock(int inherited, int parent, unsigned long long ticks, const std::string& path) {
    if(inherited<3 || parent!=getppid() || ticks!=start_ticks(parent))
        throw std::runtime_error("not a fresh direct manager child");
    struct stat named{},self{},owner{};
    const auto proc="/proc/"+std::to_string(parent)+"/";
    if(lstat(path.c_str(),&named)||fstat(inherited,&self)||
       stat((proc+"fd/"+std::to_string(inherited)).c_str(),&owner))
        throw std::runtime_error("lock stat unavailable");
    if(!S_ISREG(named.st_mode)||named.st_uid!=geteuid()||(named.st_mode&0022)||
       named.st_dev!=self.st_dev||named.st_ino!=self.st_ino||
       named.st_dev!=owner.st_dev||named.st_ino!=owner.st_ino)
        throw std::runtime_error("lock identity/permissions differ");
    if(!parent_flock(text(proc+"fdinfo/"+std::to_string(inherited)),parent)||
       !parent_flock(text("/proc/self/fdinfo/"+std::to_string(inherited)),parent))
        throw std::runtime_error("inherited open-file-description does not hold manager flock");
    int fd=fcntl(inherited,F_DUPFD_CLOEXEC,3);
    if(fd<0)throw std::runtime_error("cannot duplicate inherited lock");
    // close(fd), never LOCK_UN: an unlock would also release the parent's lock.
    return fd;
}
}
