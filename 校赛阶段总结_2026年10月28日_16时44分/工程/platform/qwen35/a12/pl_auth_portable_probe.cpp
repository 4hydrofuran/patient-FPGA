// COMPILE ONLY. Forces every private shared-gate path into an A53 object.
#include "pl_auth_gate.hpp"
extern "C" void a12_unbound_gate_compile_probe(int fd,const uint64_t expected[4],uint64_t job){
    plauth::Gate gate;gate.attach(fd,expected);gate.before_load();gate.complete(0,true);
    gate.before_transfer(job);gate.before_start(job);gate.complete(job);gate.fail();
    plauth::need(!gate.unknown());(void)plauth::nonce();
}
