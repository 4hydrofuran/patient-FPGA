// CONTROL TEST DOUBLE ONLY. Does not generate mathematical or FPGA evidence.
#include "control.hpp"
#include <iostream>
#include <memory>
#include <string>
static int checks = 0;
static void check(bool v, const char* why) { ++checks; if (!v) throw std::runtime_error(why); }
struct Owner { int& destroyed; ~Owner() { ++destroyed; } };
struct Double {
    int prepares=0, starts=0, reads=0, polls=0, stop_after=-1;
    int fail_at=0; // prepare/start/state/readback/sleep/stop
    std::uint64_t clock=0;
    bool matches=true, done=true, failed=false, late=false;
    bool stop_requested() { if(fail_at==6)throw 6; return stop_after>=0 && starts>=stop_after; }
    void prepare(){++prepares;if(fail_at==1)throw 1;}
    void start(){++starts;if(fail_at==2)throw 2;}
    a10::RunState state(){++polls;if(fail_at==3)throw 3;return failed?a10::RunState::failed:done?a10::RunState::completed:a10::RunState::running;}
    void sleep_poll(){if(fail_at==5)throw 5;clock+=2;}
    std::uint64_t now_ms(){return clock;}
    bool readback_validate(){++reads;if(fail_at==4)throw 4;if(late)clock+=1000;return matches;}
};
int main() try {
    for(int failure:{0,1,2,3}){
        int calls=0,checks_seen=0;bool stopped=false;
        auto gate=[&]{++checks_seen;if(checks_seen==failure)throw std::runtime_error("cancel/health/deadline");};
        try{a10::checked_init(gate,[&]{++calls;if(failure==3)throw std::runtime_error("init operation");});}
        catch(const std::exception&){stopped=true;}
        check(calls==(failure==1?0:1),"initialization gate prevents pre-cancel device call");
        check(stopped==(failure!=0),"initialization errors propagate; no next operation");
        check(checks_seen==(failure==1||failure==3?1:2),"before/after gate call counts");
    }
    // Minimal reproduction of the old local-BO + throw pattern, preserved test.
    int old_destroyed=0;
    try { Owner old{old_destroyed}; throw std::runtime_error("simulated wait timeout"); } catch (...) {}
    check(old_destroyed==1,"old timeout unwinds resource owner");
    for (int scenario=0;scenario<10;++scenario) {
        a10::Control c;Double d;int released=0;
        auto owner=std::make_unique<Owner>(Owner{released}); released=0;
        if(scenario==1)d.done=false;
        if(scenario==2)d.fail_at=2;
        if(scenario==3)d.fail_at=3;
        if(scenario==4)d.failed=true;
        if(scenario==5)d.stop_after=1;
        if(scenario==6)d.fail_at=1;
        if(scenario==7)d.fail_at=4;
        if(scenario==8)d.matches=false;
        if(scenario==9)d.late=true;
        const auto r=a10::one(c,d);
        check((r==a10::Result::pass)==(scenario==0),"pass only on successful validated path");
        check(c.output_consumable==(scenario==0),"error output never consumable");
        check(released==0,"outer resource owner not unwound");
        const bool poison=scenario>=1 && scenario<=5;
        check(c.must_retain()==poison,"unknown quiescence retained");
        check(d.reads==(scenario==0||scenario>=7?1:0),"no readback before positive completion");
        if(poison){
            bool refused=false;try{a10::one(c,d);}catch(const std::invalid_argument&){refused=true;}
            check(refused&&d.starts==1,"poison blocks resubmission");
        }
        // Test-only cleanup of a fake owner, NEVER an instruction for real DMA.
    }
    for(auto timeout:{0u,1001u}){a10::Control c;Double d;bool rejected=false;
        try{a10::one(c,d,timeout);}catch(const std::invalid_argument&){rejected=true;}
        check(rejected&&d.starts==0,"timeout bounds before submit");}
    a10::Control c;Double d;d.stop_after=0;
    check(a10::one(c,d)==a10::Result::stopped_before_submit&&d.starts==0&&!c.must_retain(),"pre-submit cancel safe");
    a10::Control c2;Double d2;d2.done=false;d2.fail_at=5;
    check(a10::one(c2,d2)==a10::Result::device_error&&c2.must_retain(),"poll exception retained");
    std::cout<<"PASS_PC_CONTROL_ONLY checks="<<checks<<" FPGA=NOT_TESTED\n";
    return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}
