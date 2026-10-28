// Control-only probe of the unchanged legacy permit helper in a separate DSO.
#include "supervisor_gate.hpp"
extern "C" __attribute__((visibility("default"))) int plm_legacy_router_v1(bool close){
    try{a12::permit(close?"router_close":"router_open",0);return 0;}catch(...){return 1;}
}
