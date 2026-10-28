"""Verify actual catalog proofs/coverage and report browser A/B with one clock per browser."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time
import tracemalloc

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
from answer_cache_paths import vendor_source,default_parent
sys.path.insert(0,str(vendor_source()))
from verified_answer_cache import VerifiedAnswerCache,file_sha,model_identity,digest


def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def catalog_verify(folder,parent,output):
    folder=Path(folder);doc=read(folder/'catalog.json');result=read(folder/'RESULT.json')
    prefix=read(parent/'continuous/bundle/control/prefix-config.json')
    profile=read(parent/'continuous/profile.json')
    identity=model_identity(prefix['identity'],vendor_source()/'patient_web/reference',
        generation_policy=profile.get('natural_patient_policy'))
    deps=read(parent/'PC_DEPENDENCIES.json')
    if file_sha(Path(deps['model']))!=identity['assets']['model_sha256']:raise RuntimeError('actual model asset differs')
    from answer_cache_build import enumerate_plans
    from patient_web.reference.checking import check
    tracemalloc.start();cache=VerifiedAnswerCache(folder/'catalog.json',identity=identity,expected_sha256=result['catalog_sha256'])
    retained,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
    proofs={r['key']:r for r in doc['entries']};accepted=[]
    for case,p in enumerate_plans():
        hit=cache.lookup(case,p)
        if hit is None:raise RuntimeError('missing current fact plan')
        row=proofs[hit['provenance']['key']];origin=row['origin'];raw_path=folder/origin['result_path']
        if file_sha(raw_path)!=origin['result_sha256']:raise RuntimeError('origin result SHA differs')
        r=read(raw_path)
        if (r.get('type')!='result' or r.get('status')!='OK' or r.get('eos') is not True or r.get('teacher_forced') is not False
            or r.get('id')!=origin['native_request_id'] or r['text']!=hit['text'] or check(p,r['text'])['status']!='pass'
            or r['bridge'].get('execution_kind')!='CPU_REFERENCE'):raise RuntimeError('origin was not accepted actual CPU generation')
        accepted.append(dict(key=row['key'],case_id=case.case_id,slots=list(p.required_fact_ids),status='REAL_MODEL_EOS_CHECK_PASS'))
    expected=len(list(enumerate_plans()))
    if len(accepted)!=expected or result['worker_exit']!=0:raise RuntimeError('catalog incomplete or worker did not close')
    report=dict(status='PASS_REAL_MODEL_PROOFS_AND_CURRENT_PLAN_RECHECK',entries=len(accepted),catalog_bytes=cache.bytes,
        cache_python_retained_bytes=retained,cache_python_peak_bytes=peak,model_asset_sha256=identity['assets']['model_sha256'],
        origin_kind='CPU_REFERENCE',new_model_calls=0,rows=accepted,BOARD='NOT_TESTED')
    save(output,report);return report


def compare(live,cache,output):
    a=read(live/'RESULT.json');b=read(cache/'RESULT.json');ar={r['id']:r for r in a['rows']};br={r['id']:r for r in b['rows']}
    if set(ar)!=set(br) or len(ar)!=25:raise RuntimeError('A/B input cohort differs')
    rows=[]
    for key,x in ar.items():
        y=br[key]
        if x['question']!=y['question'] or x['case_id']!=y['case_id'] or x['answer']!=y['answer']:
            raise RuntimeError('A/B question/case/output differs: '+key)
        ams=x['timing']['submit_to_paint_ms'];bms=y['timing']['submit_to_paint_ms']
        rows.append(dict(id=key,live_ms=ams,cache_ms=bms,reduction_ms=ams-bms,reduction_percent=100*(1-bms/ams)))
    def stats(key):
        v=[r[key] for r in rows];return dict(min=min(v),median=statistics.median(v),max=max(v),samples=len(v))
    report=dict(status='PASS_REAL_HTTP_BROWSER_PAIRED_AB',rows=rows,live_ms=stats('live_ms'),cache_ms=stats('cache_ms'),
        reduction_ms=stats('reduction_ms'),within_1s=sum(r['cache_ms']<=1000 for r in rows),total=25,
        metric='Browser submit to checked full answer DOM observed after two animation frames',
        cached_answer_origin='Previously actual CPU Qwen; rechecked per question, not current PL inference',BOARD='NOT_TESTED')
    save(output,report);return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--suite',choices=('catalog','compare'),required=True)
    p.add_argument('--catalog-build',type=Path);p.add_argument('--parent',type=Path,default=default_parent())
    p.add_argument('--live',type=Path);p.add_argument('--cache',type=Path);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    r=catalog_verify(a.catalog_build,a.parent,a.output) if a.suite=='catalog' else compare(a.live,a.cache,a.output)
    print(json.dumps({k:v for k,v in r.items() if k!='rows'},indent=2))
