#pragma once
#ifndef SP_LINEAR_CONTROL_TEST
#error "Control doubles must never enter production builds"
#endif
// CONTROL FLOW ONLY. No HLS/FPGA, numerical reference, emulation or performance.
#include <array>
#include <atomic>
#include <cstdint>
#include <cstring>
#include <memory>
#include <mutex>
#include <stdexcept>
#include <string>
#include <type_traits>
#include <vector>
enum {XCL_BO_SYNC_BO_TO_DEVICE=0,XCL_BO_SYNC_BO_FROM_DEVICE=1};
enum {ERT_CMD_STATE_RUNNING=1,ERT_CMD_STATE_COMPLETED=4,ERT_CMD_STATE_ERROR=5,ERT_CMD_STATE_ABORT=6,ERT_CMD_STATE_NORESPONSE=7};
namespace control {
inline std::string fault;
inline std::atomic<bool> started{false},release_run{false};
inline unsigned allocations=0,live=0,device_opens=0,starts=0;
inline uint8_t observed_weight=0;
inline uint64_t next_address=4096;
inline std::vector<std::string> events;
inline std::array<unsigned,17> widths{};
inline std::array<int,6> argument_groups{{5,3,7,7,9,11}};
inline void fail(const std::string&key){if(fault==key)throw std::runtime_error("CONTROL_INJECTED_"+key);}
inline void event(const std::string&name){events.push_back(name);fail(name);}
inline void put(uint8_t*p,uint64_t value,unsigned n){for(unsigned i=0;i<n;++i)p[i]=uint8_t(value>>(8*i));}
inline unsigned count(const std::string&text){unsigned n=0;for(auto&e:events)if(e==text)++n;return n;}
struct allocation {
    size_t bytes;int group;uint64_t address;
    std::vector<uint64_t> host,device;
    allocation(size_t n,int g):bytes(n),group(g),address(next_address),host((n+7)/8),device((n+7)/8){
        fail("allocate");next_address+=n+4096;++allocations;++live;
    }
    ~allocation(){--live;events.push_back("free");}
};
}
namespace xrt {
namespace info {enum class device{name};}
struct uuid {std::string to_string()const{return "CONTROL_ONLY_UUID";}};
class device {
public:
    device()=default;
    explicit device(unsigned){++control::device_opens;control::event("device_open");}
    template<info::device>std::string get_info()const{return "CONTROL_ONLY_DEVICE";}
    uuid load_xclbin(const std::string&){control::event("load_xclbin");return {};}
};
class kernel {
public:
    enum class cu_access_mode{exclusive};
    kernel()=default;
    kernel(const device&,const uuid&,const std::string&,cu_access_mode){control::event("kernel_open");}
    int group_id(unsigned arg)const{control::fail("group_id");return control::argument_groups.at(arg);}
};
class bo {
    std::shared_ptr<control::allocation> p;
public:
    bo()=default;
    bo(const device&,size_t n,int g):p(std::make_shared<control::allocation>(n,g)){}
    size_t size()const{return p->bytes;}
    uint64_t address()const{return control::fault=="bad_address"?UINT64_MAX:p->address;}
    template<class T>T map()const{control::fail("map");return reinterpret_cast<T>(p->host.data());}
    void sync(int direction,size_t bytes,size_t off)const{
        if(bytes>p->bytes||off>p->bytes-bytes)throw std::runtime_error("CONTROL range");
        const std::string dir=direction==XCL_BO_SYNC_BO_TO_DEVICE?"to_":"from_";
        control::event(dir+std::to_string(p->group));
        auto h=reinterpret_cast<uint8_t*>(p->host.data());auto d=reinterpret_cast<uint8_t*>(p->device.data());
        if(direction==XCL_BO_SYNC_BO_TO_DEVICE)std::memcpy(d+off,h+off,bytes);else std::memcpy(h+off,d+off,bytes);
    }
    uint8_t* device_bytes()const{return reinterpret_cast<uint8_t*>(p->device.data());}
    int group()const{return p->group;}
};
class run {
    std::array<bo,6> buffers;
    std::array<uint64_t,17> values{};
public:
    run()=default;
    explicit run(const kernel&){control::event("run_create");}
    void set_arg(unsigned index,const bo&b){control::event("set_arg");buffers.at(index)=b;control::widths.at(index)=8;}
    template<class T,std::enable_if_t<std::is_integral<T>::value,int> =0>
    void set_arg(unsigned index,T value){control::event("set_arg");values.at(index)=value;control::widths.at(index)=sizeof(T);}
    void start(){
        ++control::starts;control::started=true;control::event("start");
        for(unsigned i=0;i<6;++i)if(buffers[i].group()!=control::argument_groups[i])throw std::runtime_error("wrong group binding");
        control::observed_weight=buffers[0].device_bytes()[0];
        if(control::fault=="stale")return;
        auto meta=buffers[5].device_bytes();
        control::put(meta,0x57344138,4);control::put(meta+4,0xB3030002,4);control::put(meta+8,values[15],8);
        control::put(meta+16,0,4);control::put(meta+20,1,4);control::put(meta+24,1,8);control::put(meta+32,values[9],8);
        // Fixed transport payload sentinel, NOT matrix multiplication or a golden.
        std::memset(buffers[4].device_bytes(),0,size_t(values[13]));
        if(control::fault=="nan_y")control::put(buffers[4].device_bytes(),0x7fc00000,4);
        if(control::fault=="tail_y")control::put(buffers[4].device_bytes()+values[7]*4,0x3f800000,4);
        if(control::fault=="bad_job")meta[8]^=1;
        if(control::fault=="bad_build")meta[4]^=1;
        if(control::fault=="bad_count")meta[24]^=1;
        if(control::fault=="bad_done")meta[20]=0;
        if(control::fault=="bad_bytes")meta[32]^=1;
        if(control::fault=="private_error"){control::put(meta+16,5,4);control::put(meta+24,0,8);}
    }
    int state(){
        control::fail("state");
        if(control::fault=="timeout"||(control::fault=="blocked"&&!control::release_run))return ERT_CMD_STATE_RUNNING;
        if(control::fault=="device_error")return ERT_CMD_STATE_ERROR;
        if(control::fault=="device_abort")return ERT_CMD_STATE_ABORT;
        if(control::fault=="device_noresponse")return ERT_CMD_STATE_NORESPONSE;
        return ERT_CMD_STATE_COMPLETED;
    }
};
}
