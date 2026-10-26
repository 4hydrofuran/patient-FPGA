"""Bounded R0 baseline windows; native binaries and all safety methods retained."""
import ast
import base64
import gzip
import hashlib
import json
from pathlib import Path
import shutil
from tt10_00_prepare import ROOT,OUT,sha,j,save

HEALTH=ROOT/'evidence/model_pl_A/20261024-cpu-opt-00-v1/frozen/health-bundle'
CPU02=ROOT/'evidence/model_pl_A/20261024-cpu-opt-02-v1/candidate/bundle-v1'


def function(text,name):
    node=next(n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef) and n.name==name)
    return '\n'.join(text.splitlines()[node.lineno-1:node.end_lineno])


def measured_case():
    text=function((CPU02/'control/cpu01_manager.py').read_text(encoding='utf-8'),'run_case')
    anchor="    results = []"
    audit="""    corpus = json.loads((BUNDLE / 'control/workloads.json').read_text())['real_inputs']
    token_audit = []
    for item in corpus:
        worker.send(dict(id='audit-'+item['id'], op='tokenize', prompt=item['prompt']))
        value = receive(worker, owner, path)
        assert value['type']=='tokens' and value['tokens']==item['tokens']
        token_audit.append(dict(id=item['id'],tokens=value['tokens']))
    save(path / 'corpus-tokenization.json',token_audit)
    maps=Path('/proc') / str(worker.process.pid) / 'maps'
    loaded=sorted({line.split()[-1] for line in maps.read_text().splitlines() if line.split()[-1].startswith('/') and '.so' in line.split()[-1]})
    save(path / 'loaded-libraries.json',{p:dict(bytes=Path(p).stat().st_size,sha256=sha(p)) for p in loaded})
"""
    assert text.count(anchor)==1;text=text.replace(anchor,audit+anchor)
    text=text.replace('        ob.start_request(request)',"        ob.ENABLED = bool(request['profile']) and SPEC['tt10_detailed_manager_available']\n        ob.start_request(request)")
    text=text.replace("ob.finish_request(r, case / 'management-profile.json')", "ob.finish_request(r if SPEC['tt10_detailed_manager_available'] else dict(id=r['id'],request_profile={}), case / 'management-profile.json')")
    a=text.index('        begin = time.monotonic_ns()');b=text.index('        save(case / \'result.json\', r)',a)
    old=text[a:b]
    replacement="""        app_clock = None
        if 'application' in request:
            template=(BUNDLE / 'control/chat_template.jinja').read_text()
            r,events,begin,ended,app_clock=measure_application(worker,lambda: receive(worker,owner,case),template,request)
        else:
"""+'\n'.join('    '+line for line in old.rstrip().splitlines())+'\n'
    text=text[:a]+replacement+text[b:]
    text=text.replace("        save(case / 'result.json', r)","        save(case / 'result.json', r)\n        if app_clock is not None: save(case / 'application-timing.json',app_clock)")
    text='\n'.join(line for line in text.splitlines() if "'representation-metrics.json'" not in line)
    return text+'\n'


def main():
    assert j(OUT/'logs/prepare_01.json')['exit_code']==0
    reqs=j(CPU02/'control/requests.json');diag=next(r for r in reqs if r['id']=='diag_exact')
    diag=dict(diag);short=dict(id='short_proxy',op='generate',tokens=list(range(1,10)),teacher_tokens=[10],max_tokens=1,
                               profile=False,prefill_chunk=256,logits_mode='final',cache_policy='R0',state_fingerprint=False)
    natural=next(r for r in j(OUT/'WORKLOADS.json')['real_inputs'] if r['id']=='DEV-001')
    natural={k:v for k,v in natural.items() if k!='prefix_audit'}
    requests=[diag,short,*[dict(natural,id=name,profile=profile,max_tokens=8) for name,profile in
                          [('app_plain_1',False),('app_plain_2',False),('app_profile',True)]]]
    maximum=sum(72*((len(r['tokens'])+7)//8+r['max_tokens']-1) for r in requests)
    assert maximum==4896
    save(OUT/'RESOURCE_CALL_BUDGET.json',dict(status='FROZEN_BEFORE_BOARD',max_runs_per_window=5000,calculated_worst_case_runs=maximum,
        windows=2,expected_natural_EOS_runs_per_window=4680,max_loads_per_window=72,explicit_BO_count=148,explicit_BO_bytes=140591104,
        session_seconds=1800,requests_per_backend=5,real_corpus_tokenize_only=25,tokenizer_PL_runs=0,
        cache_snapshots_this_stage=0,snapshot_capacity_for_TT10_01='NOT_YET_MEASURED',XRT_implicit_bytes=None,
        future_suffix_lengths=[1,8,9,16,17,24,32,48],future_suffix_probes_this_BOARD=False,
        scope='Only R0 baseline, two ordinary and one profile of the frozen real application input; final 100 requests belong to TT10-08'))
    configurations=[];integrity={}
    base_case=measured_case()
    for mode,parent,remote_parent,entry in [('health',HEALTH,'/var/lib/kv260-a12/health-opt-20261024-v1','health_opt_manager.py'),
                                          ('cpu02',CPU02,'/var/lib/kv260-a12/cpu02-candidate-20261024-v1','cpu01_manager.py')]:
        parent_m=j(parent/'manifest.json');bundle=OUT/mode/'bundle-v1';bundle.parent.mkdir();shutil.copytree(parent,bundle)
        deployed_manifest=parent/'manifest.json' if mode=='health' else ROOT/'evidence/model_pl_A/20261024-cpu-opt-02-v1/candidate/readback-v1/manifest.json'
        deployed={r['path']:r for r in j(deployed_manifest)['files']}
        assert all(deployed[r['path']]==r for r in parent_m['files'] if r['path']!='control/preflight.json')
        for row in parent_m['files']:assert sha(parent/row['path'])==row['sha256']
        source=(parent/'control'/entry).read_text(encoding='utf-8')
        old=function(source,'run_case');source=source.replace(old,base_case.rstrip(),1)
        additions="""\nimport cpu01b_observer as ob
from cpu01_profile import audit_profile
from cpu01_numeric import compare_cases
from cpu01_usage import process_usage
sys.path.insert(0,str(BUNDLE/'application'))
from tt10_00_app import measure as measure_application
"""
        # Imports are added after trusted package search paths have been set.
        at=source.index('\nSPEC =') if '\nSPEC =' in source else source.index('\nSPEC=')
        source=source[:at]+additions+source[at:]
        target=bundle/'control/tt10_00_manager.py';target.write_text(source,encoding='utf-8',newline='\n')
        compile(source,str(target),'exec')
        # All functions other than request runner are AST-identical to the parent.
        a={n.name:ast.dump(n,include_attributes=False) for n in ast.parse((parent/'control'/entry).read_text()).body if isinstance(n,(ast.ClassDef,ast.FunctionDef)) and n.name!='run_case'}
        b={n.name:ast.dump(n,include_attributes=False) for n in ast.parse(source).body if isinstance(n,(ast.ClassDef,ast.FunctionDef)) and n.name!='run_case'}
        assert a==b;integrity[mode]=dict(safety_classes_and_main_AST_identical=True,functions=list(a),native_sha256=sha(bundle/'bin/qwen35-a12'))
        support=bundle/'platform/qwen35/a12'
        for name in ['cpu01_profile.py','cpu01_numeric.py','cpu01_usage.py','cpu01b_observer.py']:
            shutil.copyfile(CPU02/'platform/qwen35/a12'/name,support/name)
        observer=support/'cpu01b_observer.py';s=observer.read_text()
        s=s.replace('MAX_ROWS = 12000','MAX_ROWS = 12000\nENABLED = False')
        for name,args in [('span','name'),('scope','kind')]:
            needle='def '+name+'('+args+'):\n';assert s.count(needle)==1
            s=s.replace(needle,needle+'    if not ENABLED:\n        yield\n        return\n',1)
        observer.write_text(s,encoding='utf-8',newline='\n')
        shutil.copyfile(ROOT/'platform/qwen35/a12/tt10_00_app.py',support/'tt10_00_app.py')
        for name in ['__init__.py','domain.py','planning.py','checking.py','scoring.py','session.py']:
            src=ROOT/'system_qwen35/app'/name;dest=bundle/'application/system_qwen35/app'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dest)
        dest=bundle/'application/system_qwen35/__init__.py';shutil.copyfile(ROOT/'system_qwen35/__init__.py',dest)
        shutil.copytree(ROOT/'system_qwen35/cases',bundle/'application/system_qwen35/cases')
        shutil.copyfile(ROOT/'artifacts/qwen35-0.8b/source/chat_template.jinja',bundle/'control/chat_template.jinja')
        shutil.copyfile(OUT/'WORKLOADS.json',bundle/'control/workloads.json')
        spec=j(parent/'control/window-spec.json');spec.update(window_id='a12-tt10-00-'+mode+'-20261024-v1',variant='tt10_00_'+mode,
             request_limit=5,max_runs=5000,prompt_token_limit=128,output_token_limit=8,
             baseline_path='/var/lib/kv260-a12/tt10-00-health-20261024-v1' if mode=='cpu02' else None,
             tt10_detailed_manager_available=mode=='cpu02')
        (bundle/'control/window-spec.json').write_text(json.dumps(spec,indent=2)+'\n')
        (bundle/'control/requests.json').write_text(json.dumps(requests,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        shutil.copyfile(deployed_manifest,bundle/'tt10-parent-manifest.json')
        manifest=dict(schema_version=1,module_id='A12_TT10_00_'+mode.upper(),provider='B',maintainer='A',scope='all',
              contract_sha256=parent_m['contract_sha256'],parent_manifest_sha256=sha(deployed_manifest),authorization_included=False,budget=spec)
        manifest['files']=[dict(path=p.relative_to(bundle).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(bundle.rglob('*')) if p.is_file() and p!=bundle/'manifest.json']
        (bundle/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
        prior={r['path']:r for r in parent_m['files']}
        delta={r['path']:base64.b64encode(gzip.compress((bundle/r['path']).read_bytes())).decode() for r in manifest['files'] if prior.get(r['path'],{}).get('sha256')!=r['sha256']}
        delta['control/preflight.json']=base64.b64encode(gzip.compress((bundle/'control/preflight.json').read_bytes())).decode()
        configurations.append(dict(mode=mode,parent=remote_parent,parent_manifest_sha256=sha(deployed_manifest),
            remote='/var/lib/kv260-a12/tt10-00-'+mode+'-20261024-v1',manager='tt10_00_manager.py',manifest=manifest,delta=delta))
    data=dict(parent='',parent_manifest_sha256='',preflight=base64.b64encode(gzip.compress((ROOT/'platform/qwen35/a12/step06_preflight.py').read_bytes())).decode(),configurations=configurations)
    driver=(ROOT/'platform/qwen35/a12/cpu01b_board_driver.py').read_text()
    driver=driver.replace('DATA = None','DATA = '+repr(data),1)
    driver=driver.replace("parent=Path(DATA['parent'])","parent=Path(config['parent'])").replace("DATA['parent_manifest_sha256']","config['parent_manifest_sha256']")
    driver=driver.replace("('short_profile','natural_plain','natural_profile')",repr(tuple(r['id'] for r in requests)))
    code=OUT/'board_driver_reviewed.py';code.write_text(driver,encoding='utf-8',newline='\n')
    gz=OUT/'board_driver_reviewed.py.gz';gz.write_bytes(gzip.compress(code.read_bytes()))
    remote='/home/ubuntu/a12-tt10-00-driver-20261024-v1.py.gz'
    (OUT/'execute_reviewed.py').write_text("import gzip,hashlib,os\nfrom pathlib import Path\nassert os.geteuid()==0\np=Path(%r);b=p.read_bytes()\nassert len(b)==%d and hashlib.sha256(b).hexdigest()==%r\nexec(compile(gzip.decompress(b),'tt10_00_reviewed','exec'))\n"%(remote,gz.stat().st_size,sha(gz)),encoding='utf-8')
    save(OUT/'INTEGRITY.json',dict(status='PASS_PARENT_SAFETY_AST_AND_NATIVE_PRESERVED',modes=integrity,
         changes=['application measured Session adapter','input and timing capture','detailed observer disabled in ordinary cases, enabled in profile'],
         fsync_and_health_implementation_unchanged=True,cache_restore_implemented=False,default_backend_changed=False))
    save(OUT/'PACKAGE.json',dict(status='PREPARED_REQUIRES_PC_GATES_BEFORE_BOARD',remote_driver=remote,gzip_sha256=sha(gz),gzip_bytes=gz.stat().st_size,
         windows=[dict(mode=c['mode'],remote=c['remote'],parent=c['parent'],program_sha256=integrity[c['mode']]['native_sha256']) for c in configurations],
         expected_actual_runs=9360,hard_max_runs_each=5000,rollback='/var/lib/kv260-a12/cpu02-candidate-20261024-v1'))
    print('TT10_00_TWO_BOUNDED_BASELINE_WINDOWS_PACKAGED')

if __name__=='__main__':main()
