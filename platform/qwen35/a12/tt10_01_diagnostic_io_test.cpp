#include "diagnostic_io.hpp"
#include <fstream>
#include <vector>
#include <iostream>
int main(int argc,char**argv){
    if(argc!=2)return 2;std::filesystem::path root=argv[1];std::filesystem::create_directory(root);
    std::vector<uint8_t> bytes(16*1024*1024);for(size_t i=0;i<bytes.size();++i)bytes[i]=uint8_t(i%251);
    tt10::write_diagnostic(root/"full.bin",bytes.data(),bytes.size());
    std::ifstream f(root/"full.bin",std::ios::binary);std::vector<uint8_t> read(bytes.size());f.read(reinterpret_cast<char*>(read.data()),read.size());
    if(!f||read!=bytes)return 3;int checks=1;struct stat st{};
    if(::stat((root/"full.bin").c_str(),&st)||(st.st_mode&0777)!=0600)return 4;++checks;
    try{tt10::write_diagnostic(root/"full.bin",bytes.data(),1);return 5;}catch(const std::runtime_error&){}++checks;
    if(std::filesystem::file_size(root/"full.bin")!=bytes.size())return 6;++checks;
    std::filesystem::create_symlink(root/"full.bin",root/"link.bin");
    try{tt10::write_diagnostic(root/"link.bin",bytes.data(),1);return 7;}catch(const std::runtime_error&){}++checks;
    tt10::write_diagnostic(root/"empty.bin",nullptr,0);if(std::filesystem::file_size(root/"empty.bin"))return 8;++checks;
    try{tt10::write_diagnostic(root/"missing/child.bin",bytes.data(),1);return 9;}catch(const std::runtime_error&){}++checks;
    std::cout<<"{\"status\":\"PASS_DIAGNOSTIC_IO_REAL_PC_FILES\",\"checks\":"<<checks<<"}\n";
}
