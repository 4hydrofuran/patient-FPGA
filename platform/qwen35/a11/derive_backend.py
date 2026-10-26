"""Hash-pinned A11 maintenance derivative; leaves the frozen A07 library intact.

No public mathematical/ABI/bitstream changes. Trial profile is expressly NOT a
BOARD_VERIFIED deployment. It is useful only behind a separately audited A11
manager and requires that manager's inherited lock and fresh boot identity.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PIN = 'c9e2032ec4853feed0e37112e9305afe9dd2e59b5eece15ae3797464447c8170'


def derive(out):
    src = ROOT/'release/a07_b04_v3/modules/linear_A/xrt/backend.cpp'
    data = src.read_bytes()
    if hashlib.sha256(data).hexdigest() != PIN:
        raise ValueError('frozen A07 backend differs')
    s = data.decode().replace('\r\n','\n')

    def replace(old, new):
        nonlocal s
        if s.count(old) != 1:
            raise ValueError('patch context must occur exactly once: '+old[:60])
        s = s.replace(old, new)

    replace('#include "json.hpp"', '#include "json.hpp"\n#include "managed_lock.hpp"')
    replace('    void acquire(){', '''    void acquire(const json& profile){
#ifndef SP_LINEAR_CONTROL_TEST
        require(geteuid()==0,SP_UNSUPPORTED);
        require(profile.value("boot_id",std::string())+"\\n"==a11::text("/proc/sys/kernel/random/boot_id"));
        const auto expiry=number(profile,"expires_monotonic_ns");
        require(expiry>uint64_t(std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now().time_since_epoch()).count()));
        fd=a11::borrow_lock(number(profile,"inherited_device_lock_fd",INT32_MAX),
            number(profile,"manager_pid",INT32_MAX),number(profile,"manager_start_ticks"),
            "/run/lock/patient-qwen-linear.lock");
        return;
#else
        (void)profile;
#endif''')
    replace('=="BOARD_VERIFIED",SP_UNSUPPORTED)', '=="A11_BOUNDED_TRIAL_AUTHORIZED_NOT_ACCEPTED",SP_UNSUPPORTED)')
    replace('number(profile,"verified_bo_budget_bytes")', 'number(profile,"trial_bo_limit_bytes",4ULL*1024*1024)')
    replace('c->device_lock.acquire();','c->device_lock.acquire(profile);')
    replace('    auto start=Clock::now();', '''    if(c->runs>=23)return SP_UNSUPPORTED;
    auto start=Clock::now();''')
    replace('    std::memcpy(v->w.map<void*>(),w,a.w);', '    auto load_start=Clock::now();\n    std::memcpy(v->w.map<void*>(),w,a.w);')
    replace('    v->w.sync(XCL_BO_SYNC_BO_TO_DEVICE,a.w,0);', '    auto load_copied=Clock::now();\n    v->w.sync(XCL_BO_SYNC_BO_TO_DEVICE,a.w,0);')
    replace('    auto h=c->next;', '''    auto load_synced=Clock::now();
    c->load_copy_ms=std::chrono::duration<double,std::milli>(load_copied-load_start).count();
    c->load_sync_ms=std::chrono::duration<double,std::milli>(load_synced-load_copied).count();
    auto h=c->next;''')
    replace('    uint32_t build=0;', '    double load_copy_ms=0,load_sync_ms=0;\n    uint32_t build=0;')
    replace('        c->x.sync(XCL_BO_SYNC_BO_TO_DEVICE,a.x,0);', '        auto copied=Clock::now();\n        c->x.sync(XCL_BO_SYNC_BO_TO_DEVICE,a.x,0);')
    replace('        c->run.start();const auto deadline=', '        auto submitted=Clock::now();\n        c->run.start();const auto deadline=')
    replace('        if(auto rc=a07::validate_meta(', '        auto meta_synced=Clock::now();\n        if(auto rc=a07::validate_meta(')
    replace('        c->y.sync(XCL_BO_SYNC_BO_FROM_DEVICE,a.y,0);', '        auto meta_checked=Clock::now();\n        c->y.sync(XCL_BO_SYNC_BO_FROM_DEVICE,a.y,0);')
    replace('        if(auto rc=a07::output(a,result,a.y))', '        auto y_synced=Clock::now();\n        if(auto rc=a07::output(a,result,a.y))')
    replace('{"algorithm_weight_bytes",a.w}', '''{"a11_input_copy_and_meta_seed_ms",ms(start,copied)},
                 {"a11_input_bo_sync_ms",ms(copied,synced)},
                 {"a11_set_args_ms",ms(synced,submitted)},
                 {"a11_submit_to_confirmed_completion_ms",ms(submitted,completed)},
                 {"a11_meta_sync_ms",ms(completed,meta_synced)},
                 {"a11_meta_validate_ms",ms(meta_synced,meta_checked)},
                 {"a11_output_bo_sync_and_map_ms",ms(meta_checked,y_synced)},
                 {"a11_output_validate_ms",ms(y_synced,ended)},
                 {"a11_weight_copy_ms",c->load_copy_ms},{"a11_weight_upload_sync_ms",c->load_sync_ms},
                 {"a11_full_service_scope","MUST_USE_EXTERNAL_CALL_TIMER_INCLUDING_QUANT_AND_RETURN_COPY"},
                 {"algorithm_weight_bytes",a.w}''')
    replace('    auto s=j.dump();', '''#ifdef SP_LINEAR_CONTROL_TEST
    for(auto it=j.begin();it!=j.end();++it)if(it.key().find("a11_")==0 && it.key().find("_ms")!=std::string::npos)it.value()=nullptr;
#endif
    j["candidate_scope"]="A11_BOUNDED_MAINTENANCE_NOT_DEFAULT_DEPLOYMENT";
    auto s=j.dump();''')
    out.mkdir(parents=True, exist_ok=False)
    with (out/'backend.cpp').open('x') as f:
        f.write(s)
    report = dict(domain='PC_SOURCE_DERIVATION',source=str(src),source_sha256=PIN,
                  derived_sha256=hashlib.sha256((out/'backend.cpp').read_bytes()).hexdigest(),
                  public_contract_changed=False,math_changed=False,bitstream_changed=False,
                  board_authorization_included=False,BOARD='NOT_TESTED',
                  changes=['private inherited flock','explicit NOT_ACCEPTED trial profile',
                           '4MiB explicit BO cap','23 successful submissions cap',
                           'host-side component timers; no fake pure kernel timer'])
    with (out/'derivation.json').open('x') as f:
        json.dump(report,f,indent=2)
    print(json.dumps(report))


if __name__ == '__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path,required=True)
    derive(ap.parse_args().out)
