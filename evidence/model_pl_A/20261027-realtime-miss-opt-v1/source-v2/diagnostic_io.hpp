#pragma once
// Diagnostic files only. Compute permissions retain their original durable journal.
#include <cerrno>
#include <cstdint>
#include <filesystem>
#include <stdexcept>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>

namespace tt10 {
inline void write_diagnostic(const std::filesystem::path& path,const void* data,size_t bytes) {
    int fd=::open(path.c_str(),O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC,0600);
    if(fd<0)throw std::runtime_error("diagnostic exclusive open failed");
    try {
        struct stat st{};
        if(::fstat(fd,&st)||!S_ISREG(st.st_mode))throw std::runtime_error("diagnostic regular file required");
        const auto* p=static_cast<const uint8_t*>(data);size_t done=0;
        while(done<bytes){
            ssize_t n=::write(fd,p+done,bytes-done);
            if(n<0&&errno==EINTR)continue;
            if(n<=0)throw std::runtime_error("diagnostic write failed");done+=size_t(n);
        }
        if(::fsync(fd))throw std::runtime_error("diagnostic fsync failed");
        // Pages are clean before this advice; only our newly-created diagnostic file.
        if(::posix_fadvise(fd,0,0,POSIX_FADV_DONTNEED))throw std::runtime_error("diagnostic cache advice failed");
        int result=::close(fd);fd=-1;
        if(result)throw std::runtime_error("diagnostic close failed");
    }catch(...){if(fd>=0)::close(fd);throw;}
}
}
