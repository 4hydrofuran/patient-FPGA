"""PC-only capsule checks at mode/window boundaries, never per projection."""
from pathlib import Path
from mode_evidence import ROOT,OUT,PARENT,read,save,sha,pin
from mode_journal import need

MODES={'PC_STRICT_CONTROL':1,'PC_BATCH_CANDIDATE':72}

def verify(path):
    d=read(path);need(d['schema']=='PC_MODE_CAPSULE_V1' and d['domain']=='PC_ONLY' and
        d['production_approved'] is False and d['modes']==MODES,'not a PC-only capsule')
    for row in d['files']:
        p=Path(row['path']);p=p if p.is_absolute() else ROOT/p
        need(p.is_file() and sha(p)==row['sha256'],'capsule artifact changed: '+str(p))
    need(sha(PARENT/'FINAL_REVIEW.json')==d['parent_final_review_sha256'],'parent PC acceptance changed')
    build=read(d['build']);reader=read(d['reader_build'])
    for name,key in [('library','library_sha256'),('existing_native','existing_native_sha256'),
            ('existing_cpu_library','existing_cpu_library_sha256')]:need(sha(build[name])==build[key],'PC build artifact changed')
    need(sha(reader['library'])==reader['library_sha256'],'reader changed')
    return d

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--revision',type=int,default=1);a=p.parse_args()
    parent=read(PARENT/'FINAL_REVIEW.json');pins={}
    for row in parent['source']:
        path=ROOT/row['path'];need(sha(path)==row['sha256'],'parent source changed');pins[str(path)]=dict(path=row['path'],sha256=row['sha256'])
    for row in read(PARENT/'PRESERVATION.json')['old_source_pins']:
        path=ROOT/row['path'];need(sha(path)==row['sha256'],'older dependency changed');pins[str(path)]=dict(path=row['path'],sha256=row['sha256'])
    bundle=ROOT/'evidence/model_pl_A/20261025-resource-probe-v1/bundle-v2'
    need(sha(bundle/'manifest.json')=='4fcb6af2d9e7d5b89f876697de6bd8f11e36174666169544a9016009551f070f','frozen bundle manifest changed')
    for row in read(bundle/'manifest.json')['files']:
        path=bundle/row['path']
        if path.suffix=='.py':
            need(sha(path)==row['sha256'],'frozen Python dependency changed');pins[str(path)]=dict(path=path.relative_to(ROOT).as_posix(),sha256=row['sha256'])
    names=('request_journal_verified.py','request_journal_candidate.py','native_request_journal.py',
        'native_request_run.py','resource_probe_policy.py','health_fence.py','mode_child.py','mode_reader.py',
        'mode_journal.py','mode_registry.py','mode_coordinator.py','mode_history.py','mode_evidence.py',
        'mode_page_reader.cpp','mode_reader_build.py')
    for name in names:
        path=ROOT/'platform/qwen35/a12'/name;pins[str(path)]=dict(path=path.relative_to(ROOT).as_posix(),sha256=sha(path))
    build=PARENT/'BUILD-v5-reviewed.json';reader=OUT/'READER_BUILD-v2.json'
    for path in (build,reader):pins[str(path)]=dict(path=path.relative_to(ROOT).as_posix(),sha256=sha(path))
    d=dict(schema='PC_MODE_CAPSULE_V1',domain='PC_ONLY',production_approved=False,modes=MODES,
        parent_final_review_sha256=sha(PARENT/'FINAL_REVIEW.json'),files=list(pins.values()),build=str(build),
        reader_build=str(reader),runner_sha256=sha(ROOT/'platform/qwen35/a12/microbatch_run.py'))
    save(OUT/('CAPSULE-v'+str(a.revision)+'.json'),d)
