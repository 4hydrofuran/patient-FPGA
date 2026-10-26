// COMPILE ONLY: force complete private control protocol paths into the ARM object.
#include "plm_control.hpp"
extern "C" void a12_plm_unbound_compile_probe(const nlohmann::json&facts,const char*request){
    plm::Control c;c.configure(facts);c.before_load();c.complete(0,true);c.bind_request(request);
    c.before_transfer(1,8);c.before_start(1);c.complete(1);c.end_request();
    (void)c.report();(void)c.maintenance_allowed();c.fail();
}
