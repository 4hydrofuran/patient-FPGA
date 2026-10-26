"""Pin the actual frozen XRT call sites; emit review data, never execute PL."""
from mode_evidence import ROOT,OUT,read,save,sha

bundle=ROOT/'evidence/model_pl_A/20261025-resource-probe-v1/bundle-v2'
assert sha(bundle/'manifest.json')=='4fcb6af2d9e7d5b89f876697de6bd8f11e36174666169544a9016009551f070f'
pins={r['path']:r for r in read(bundle/'manifest.json')['files']}
paths=['source/backend.cpp','source/supervisor_gate.hpp','runtime/qwen35_w4a8/a12/route.cpp']
sources=[]
for name in paths:
    p=bundle/name;assert sha(p)==pins[name]['sha256'];sources.append(dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p)))
path=bundle/paths[0];text=path.read_text();lines=text.splitlines();sites={}
markers=[('argument_validation','a07::inputs(a,x,xb,sx,sb,y,yb)'),('old_submit_permission','a12::permit("submit",job)'),
    ('input_sync','c->x.sync(XCL_BO_SYNC_BO_TO_DEVICE'),('life_begin','c->life.begin(job,timeout)'),
    ('kernel_start','c->run.start()'),('metadata_validation','a07::validate_meta('),('output_validation','a07::output(a,result,a.y)'),
    ('commit_and_copy','c->life.completed_and_validated();++c->runs;std::memcpy(y,result,a.y)')]
for key,marker in markers:
    hits=[i+1 for i,line in enumerate(lines) if marker in line];assert len(hits)==1,(key,hits)
    sites[key]=dict(line=hits[0],source_line=lines[hits[0]-1].strip())
order=[sites[k]['line'] for k,_ in markers];assert order==sorted(order)
assert text.count('c->run.start()')==1
save(OUT/'PL_BINDING_SITES_UNBOUND.json',dict(status='ACTUAL_FROZEN_XRT_CALL_GRAPH_REVIEWED_NOT_IMPLEMENTED',sources=sources,sites=sites,
    finding='Replacing only the old submit permit leaves BO sync/set_args between authority check and kernel start',
    required_binding=[
        'Keep real lease/dual-lock/boot/kernel/CMA/temperature preconditions and the original resource probe package',
        'Bind the new authority to the actual reviewed platform/device generation, BO ownership and kernel artifact identity',
        'Reserve before any BO transfer and retain unknown IO ownership; recheck cancellation/epoch/deadline immediately before run.start',
        'Promote exactly one start intent per reserved job; do not label host intent/credit as hardware completion',
        'Keep RUNNING-before-start, timeout/ERT poisoning, exact metadata/finite-Y checks and no stale output',
        'Complete private authorization only with confirmed completion; do not copy Y on a failed/revoked result',
        'Accept legacy router and new backend sequence lanes without duplicating local authoritative budget',
        'Port/compile the private gate for the existing A53 toolchain; current x86 guard is not ARM proof',
        'First PC XRT-double fault closure, then actual ARM compile; Board activation remains separately prohibited'],
    B_HLS_and_public_ABI_changed=False,ARM_build='NOT_PERFORMED',real_PL_binding='NOT_IMPLEMENTED',
    BOARD='NOT_TESTED',device_operations=0,production_enabled=False))
