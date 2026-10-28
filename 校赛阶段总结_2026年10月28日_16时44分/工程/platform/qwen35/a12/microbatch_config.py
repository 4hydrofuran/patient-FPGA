"""Pinned existing CPU model inputs plus the new private adapter identity."""
from microbatch_evidence import ROOT,read,save,sha
from request_journal_verified import digest

def prepare(build):
    work=__import__('pathlib').Path(build['workspace'])
    prefix=read(ROOT/'evidence/model_pl_A/20261025-resource-probe-v1/native-PC-02/prefix-config-PC.json')
    context=digest(dict(identity=prefix['identity'],native_sha256=build['existing_native_sha256'],
        scope='all',CPU_library_sha256=build['existing_cpu_library_sha256']))
    config=ROOT/'modules/linear_A/cpu_threads2_config.json'
    adapter=dict(schema='A12_NATIVE_CPU_MICROBATCH_V1',execution_kind='CPU_REFERENCE',
        contract_sha256='83bd402b39350710d8689d50f79296e9625e9c75ccb0ecee145f08067c4ee3b6',
        allow_device_access=False,cpu_library=build['existing_cpu_library'],
        cpu_library_sha256=build['existing_cpu_library_sha256'],cpu_config=str(config),cpu_config_sha256=sha(config),
        context_sha256=context,controlled_trusted_worker_only=True)
    ap=work/'adapter-config.json';save(ap,adapter)
    route=dict(contract_sha256=adapter['contract_sha256'],fallback='disabled',fpga_required=True,scope='all',
        execution_kind='PC_MATH_DOUBLE',library=build['library'],library_sha256=build['library_sha256'],
        backend_config=str(ap),backend_config_sha256=sha(ap),trace_limit=4096)
    rp=work/'route-config.json';save(rp,route)
    prefix['identity']['libraries']['liba12_native_cpu_control.so']=build['library_sha256']
    prefix['identity']['pc_adapter_config_sha256']=sha(ap);prefix['identity']['pc_route_config_sha256']=sha(rp)
    save(work/'native-prefix-config.json',prefix)
    return adapter

if __name__=='__main__':
    import sys
    prepare(read(sys.argv[1]))
