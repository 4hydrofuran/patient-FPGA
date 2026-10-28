#include "generation_slot.hpp"
#include <iostream>
int main(){
    int checks=0;
    auto require=[&](bool ok){if(!ok)throw std::runtime_error("generation assertion");++checks;};
    auto rejects=[&](auto fn){bool rejected=false;try{fn();}catch(...){rejected=true;}require(rejected);};
    const std::string ctx(64,'1'),id(64,'2'),epoch(64,'3'),inventory(64,'4');
    int fd=memfd_create("PC_GENERATION_TEST",MFD_CLOEXEC|MFD_ALLOW_SEALING);require(fd>=3);
    require(!ftruncate(fd,4096));require(!fcntl(fd,F_ADD_SEALS,F_SEAL_SEAL|F_SEAL_SHRINK|F_SEAL_GROW));
    plm::Writer page(fd,1,2,plauth::now()+10000000000ULL);generation::Writer writer(fd,id.c_str(),epoch.c_str());
    writer.health(plauth::now());page.bind(getpid(),plauth::ticks(getpid()),ctx);writer.bind(ctx.c_str());
    generation::Reader reader;reader.attach(fd,generation::PC_FIXTURE,ctx);reader.check(generation::LOADING);require(true);
    rejects([&]{reader.check(generation::RESIDENT);});
    rejects([&]{generation::Reader board;board.attach(fd,generation::BOARD,ctx);});
    rejects([&]{generation::Reader wrong;wrong.attach(fd,generation::PC_FIXTURE,id);});
    rejects([&]{writer.bind(ctx.c_str());});
    rejects([&]{writer.resident(inventory.c_str());}); // loading/ACTIVE cannot seal
    page.finish_load();writer.resident(inventory.c_str());reader.check(generation::RESIDENT);require(true);
    rejects([&]{writer.resident(inventory.c_str());});
    auto s=generation::slot(writer.p);const auto old=s->healthy_ns.load();s->healthy_ns=plauth::now()-300000001ULL;
    rejects([&]{reader.check(generation::RESIDENT);});s->healthy_ns=old;
    s->epoch[0]^=1;rejects([&]{reader.check(generation::RESIDENT);});s->epoch[0]^=1;
    s->context[0]^=1;rejects([&]{reader.check(generation::RESIDENT);});s->context[0]^=1;
    s->domain=generation::BOARD;rejects([&]{reader.check(generation::RESIDENT);});s->domain=generation::PC_FIXTURE;
    page.p->state.fetch_or(plauth::IO);writer.revoke();require(!writer.disposable());
    require((page.p->state.load()&(plauth::IO|plauth::REVOKED))==(plauth::IO|plauth::REVOKED));
    rejects([&]{reader.check(generation::RESIDENT);});rejects([&]{writer.health(plauth::now());});
    rejects([&]{writer.bind(ctx.c_str());});rejects([&]{writer.resident(inventory.c_str());});
    require((s->state.load()&generation::REVOKED)!=0);
    close(fd);std::cout<<"PASS_PC_GENERATION_SLOT "<<checks<<"\n";
}
