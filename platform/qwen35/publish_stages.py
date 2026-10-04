"""Explicitly authorized stage engineering archives; isolated Git index, no force push.

This publishes source/test/material deltas, not private assets or clinical data.
"""
import hashlib,json,os,re,subprocess,sys,tempfile,zipfile
from pathlib import Path
R=Path(__file__).resolve().parents[2]
OUT=R/'release/a01-a09-engineering-20261004'
E=R/'evidence/A01_A09_publication/20261004-v1'
BASE='6dd1a93c2fa44b045276c24f4cc79d94e54b88b3'
BRANCH='a/a01-a09-engineering-20261004'
URL='https://github.com/4hydrofuran/patient-FPGA.git'
COMMON=['contracts/qwen35','scripts/release/check_contracts.py','scripts/release/qwen35_config.py',
        'config/qwen35','docs/PROJECT_STATUS.json','AGENTS.md']
SCOPES={
 'A01':['platform/qwen35/a01','models/model.lock.json','quant/qwen35_tensor_map.json'],
 'A02':['platform/qwen35/a02','system_qwen35/cases','system_qwen35/app','eval/qwen35/a02/dev','eval/qwen35/a02/heldout','eval/qwen35/a02/teacher_review.csv','eval/qwen35/a02/dataset.lock.json','eval/qwen35/a02/split_policy.json','eval/qwen35/a02/thresholds.json'],
 'A03':['platform/qwen35/a03','modules/voice_A','system_qwen35/app/audio_adapter.py','system_qwen35/app/pc_audio.py','system_qwen35/app/voice_cli.py','system_qwen35/app/voice_loop.py','system_qwen35/app/test_capture.py'],
 'A04':['platform/qwen35/a04','quant/export_w4a8','quant/reference','quant/tests','models/sidecar_A/qwen35-v1/manifest.json'],
 'A05':['platform/qwen35/a05','runtime/qwen35_w4a8','modules/linear_A','system_qwen35/app/native.py','system_qwen35/app/native_w4a8.py'],
 'A06':['platform/qwen35/a06','hw/linear_A/KERNEL_SOURCE.json'],
 'A07':['platform/qwen35/a07','modules/linear_A/xrt'],
 'A08':['platform/qwen35/a08','system_qwen35/app/default_e2e','system_qwen35/app/native.py','system_qwen35/app/audio_adapter.py'],
 'A09':['platform/qwen35/a09','config/qwen35','release/default_preboard/20261004-v2/README.md','release/default_preboard/20261004-v2/DEPENDENCIES.md','release/default_preboard/20261004-v2/DEPLOYMENT.md','release/default_preboard/20261004-v2/PREBOARD_CHECKLIST.md','release/default_preboard/20261004-v2/package.json','release/default_preboard/20261004-v2/source-bundle/paper']}
ALLOW={'.py','.cpp','.cc','.c','.h','.hpp','.md','.json','.jsonl','.yaml','.yml','.toml','.cfg','.ini','.cmake','.txt','.csv','.sh','.ps1','.cmd','.bat','.patch','.tcl','.xml','.lock','.rst','.pdf','.png','.svg','.sql','.map','.in','.nix','.j2','.jinja','.jinja2','.html','.js','.css'}
SPECIAL={'LICENSE','NOTICE','AUTHORS','Makefile','Dockerfile','.gitignore','.gitattributes','contracts.lock'}
SECRET=[re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----\r?\n'),re.compile(rb'gh[pousr]_[A-Za-z0-9]{30,}'),re.compile(rb'github_pat_[A-Za-z0-9_]{50,}'),re.compile(rb'AKIA[A-Z0-9]{16}')]
def git(*args,env=None,data=None):
    r=subprocess.run(['git',*args],cwd=R,env=env,input=data,capture_output=True)
    if r.returncode:raise RuntimeError(r.stderr.decode(errors='replace'))
    return r.stdout
def sha(b):return hashlib.sha256(b).hexdigest()
def save(p,x):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:json.dump(x,f,indent=2,ensure_ascii=False)
def scan(p):
    if p.is_file():return [p]
    if p.is_dir():return sorted(p.rglob('*'))
    raise FileNotFoundError(p)
def reason(p):
    low=[x.lower() for x in p.parts]
    if p.is_symlink():return 'symlink'
    if any(x in low for x in ['__pycache__','.git','.venv','venv','spool','before','downloads','node_modules']):return 'cache/private/runtime'
    if p.suffix.lower() not in ALLOW and p.name not in SPECIAL:return 'not-source-or-selected-material'
    if any(x in p.name.lower() for x in ['license-install','credential','secret','token-cache']):return 'private-installation-metadata'
    if p.stat().st_size>12*1024*1024:return 'large-artifact-kept-local'
    return None
def prepare():
    assert git('remote','get-url','origin').decode().strip()==URL
    refs=git('ls-remote','--heads','origin').decode()
    assert BASE+'\trefs/heads/a/a07-complete-20261004' in refs
    OUT.mkdir(parents=True,exist_ok=False);E.mkdir(parents=True,exist_ok=False)
    remote={}
    for item in git('ls-tree','-rz',BASE).split(b'\0'):
        if not item:continue
        meta,name=item.split(b'\t',1);_,kind,oid=meta.split()
        if kind==b'blob':remote.setdefault(oid.decode(),[]).append(name.decode())
    summary={}; exclusions=[]
    for stage,paths in SCOPES.items():
        sources={}
        for name in COMMON+paths:
            for p in scan(R/name):
                if p.is_file():sources[p.relative_to(R).as_posix()]=p
        # A01 includes the already-audited pinned llama source, not the mutable vendor checkout.
        if stage=='A01':
            vendor=R/'release/default_preboard/20261004-v2/source-bundle/project/third_party/llama'
            for p in scan(vendor):
                if p.is_file():sources['third_party/llama/'+p.relative_to(vendor).as_posix()]=p
        # Compact stage reports only. Never recursively publish audio/session raw logs.
        roots=[R/'eval/qwen35'/stage.lower()]
        if stage=='A06':roots=[R/'evidence/A06_acceptance/final-20261004-v1']
        if stage=='A07':roots=[R/'evidence/A07_closeout/20261004-v1']
        for root in roots:
            if root.exists():
                for p in root.rglob('*'):
                    if p.is_file() and p.name in {'REPORT.md','REPORT.json','REPORT.v2.json','A01_REPORT.json','DESIGN_GAP.md','FAILURE_BUCKETS.md','LIFECYCLE_DEFECT.md','package-verification.json'} and 'before' not in p.parts:
                        sources[p.relative_to(R).as_posix()]=p
        for p in (R/'docs/handoffs').glob('A_'+stage+'*.md'):sources[p.relative_to(R).as_posix()]=p
        included={};existing={};data={}
        for name,p in sorted(sources.items()):
            why=reason(p)
            if why:exclusions.append({'stage':stage,'path':name,'reason':why});continue
            b=p.read_bytes()
            if any(pattern.search(b) for pattern in SECRET):raise ValueError('Potential credential: '+name)
            if p.suffix.lower()=='.jsonl' and 'eval/' in name:exclusions.append({'stage':stage,'path':name,'reason':'raw-session-data'});continue
            oid=hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
            item={'sha256':sha(b),'bytes':len(b)}
            if oid in remote:existing[name]=dict(item,remote_paths=remote[oid],commit=BASE)
            else:included[name]=item;data[name]=b
        manifest={'stage':stage,'snapshot':'CURRENT_ENGINEERING_20261004_NOT_HISTORICAL_STAGE_CHECKOUT','base_commit':BASE,'files':included,'already_uploaded':existing,'BOARD':'NOT_TESTED',
                  'restore':'Start with referenced A07 branch and resolve already_uploaded by remote_paths; unpack project/ paths from stage archives into a NEW directory. Shared files can overlap with identical bytes. No automatic install/board execution.'}
        dest=OUT/stage;dest.mkdir()
        save(dest/'MANIFEST.json',manifest)
        archive=dest/(stage+'-engineering-delta.zip')
        with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            for name,b in data.items():z.writestr('project/'+name,b)
            z.writestr('MANIFEST.json',json.dumps(manifest,ensure_ascii=False,indent=2).encode())
        assert archive.stat().st_size<50*1024*1024
        with zipfile.ZipFile(archive) as z:
            assert z.testzip() is None
            assert set(z.namelist())=={'project/'+n for n in included}|{'MANIFEST.json'}
            for n,v in included.items():assert sha(z.read('project/'+n))==v['sha256']
        summary[stage]={'new_files':len(included),'already_uploaded_files':len(existing),'archive':archive.relative_to(OUT).as_posix(),'bytes':archive.stat().st_size,'sha256':sha(archive.read_bytes())}
        print(json.dumps({stage:summary[stage]}),flush=True)
    save(OUT/'INDEX.json',{'stages':summary,'base_commit':BASE,'branch':BRANCH,'BOARD':'NOT_TESTED','no_weights_audio_secrets_or_OS_images':True})
    save(OUT/'EXCLUDED.json',exclusions)
    save(E/'preflight.json',{'working_HEAD':git('rev-parse','HEAD').decode().strip(),'remote_refs_before':refs,'source_scope':SCOPES,'archives':summary,'status':'NINE_ARCHIVES_VERIFIED_NOT_YET_PUSHED'})
def publish():
    assert git('remote','get-url','origin').decode().strip()==URL
    assert not git('ls-remote','--heads','origin','refs/heads/'+BRANCH).strip()
    head=git('rev-parse','HEAD');index=git('diff','--cached','--raw')
    info=json.loads((OUT/'INDEX.json').read_text(encoding='utf-8'))
    for v in info['stages'].values():assert sha((OUT/v['archive']).read_bytes())==v['sha256']
    files=sorted(p for p in OUT.rglob('*') if p.is_file())+[Path(__file__).resolve()]
    names=[p.relative_to(R).as_posix() for p in files]
    hashes=git('hash-object','-w','--no-filters','--stdin-paths',data=('\n'.join(names)+'\n').encode()).decode().splitlines()
    with tempfile.TemporaryDirectory(prefix='a-stages-publish-') as tmp:
        env=dict(os.environ,GIT_INDEX_FILE=str(Path(tmp)/'index'));git('read-tree',BASE,env=env)
        entries=b''.join(f'100644 {h}\t{n}'.encode()+b'\0' for h,n in zip(hashes,names))
        git('update-index','-z','--index-info',env=env,data=entries)
        tree=git('write-tree',env=env).decode().strip()
        commit=git('-c','user.name=Member A (Codex)','-c','user.email=codex@localhost','commit-tree',tree,'-p',BASE,'-m','Publish A01-A09 missing engineering files as verified per-stage archives',env=env).decode().strip()
    for p,n in zip(files,names):assert sha(git('show',commit+':'+n))==sha(p.read_bytes())
    git('update-ref','refs/heads/'+BRANCH,commit,'0'*40)
    save(E/'commit.json',{'commit':commit,'branch':BRANCH,'tree':tree,'files':len(files),'blob_hashes_verified':True})
    git('push','origin','refs/heads/'+BRANCH+':refs/heads/'+BRANCH)
    remote=git('ls-remote','--heads','origin','refs/heads/'+BRANCH).decode().strip();assert remote.split()[0]==commit
    assert git('rev-parse','HEAD')==head and git('diff','--cached','--raw')==index
    save(E/'publish.json',{'status':'PUSHED_REMOTE_SHA_VERIFIED','branch':BRANCH,'commit':commit,'remote':URL,'files':len(files),'working_HEAD_and_index_unchanged':True,'B_C_and_main_unchanged':True,'BOARD':'NOT_TESTED'})
    print(json.dumps({'status':'PUSHED_REMOTE_SHA_VERIFIED','commit':commit,'branch':BRANCH,'files':len(files)}),flush=True)
def supplement_vendor():
    # Completeness audit: preserve CPU assembly/grammar and other upstream text source,
    # not only C/C++ extensions. No live vendor checkout is read.
    vendor=R/'release/default_preboard/20261004-v2/source-bundle/project/third_party/llama'
    dest=OUT/'A01';m=json.loads((dest/'MANIFEST.json').read_text(encoding='utf-8'))
    additions={}
    for p in vendor.rglob('*'):
        if not p.is_file() or p.is_symlink() or '__pycache__' in p.parts:continue
        name='third_party/llama/'+p.relative_to(vendor).as_posix()
        if name in m['files'] or name in m['already_uploaded']:continue
        if p.suffix.lower() in {'.mp3','.mp4','.webp','.jpg','.jpeg','.ico','.jar','.pyc'}:continue
        b=p.read_bytes()
        try:b.decode('utf-8')
        except UnicodeDecodeError:continue
        if any(pattern.search(b) for pattern in SECRET):raise ValueError('Potential credential: '+name)
        additions[name]=b;m['files'][name]={'sha256':sha(b),'bytes':len(b)}
    archive=dest/'A01-engineering-delta.zip';tmp=dest/'A01-complete.tmp.zip'
    with zipfile.ZipFile(archive) as old,zipfile.ZipFile(tmp,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as new:
        for name in old.namelist():
            if name!='MANIFEST.json':new.writestr(name,old.read(name))
        for name,b in additions.items():new.writestr('project/'+name,b)
        new.writestr('MANIFEST.json',json.dumps(m,indent=2,ensure_ascii=False).encode())
    with zipfile.ZipFile(tmp) as z:
        assert z.testzip() is None
        for name,v in m['files'].items():assert sha(z.read('project/'+name))==v['sha256']
    os.replace(tmp,archive)
    (dest/'MANIFEST.json').write_text(json.dumps(m,ensure_ascii=False,indent=2),encoding='utf-8')
    index=json.loads((OUT/'INDEX.json').read_text());v=index['stages']['A01'];v.update(new_files=len(m['files']),bytes=archive.stat().st_size,sha256=sha(archive.read_bytes()))
    (OUT/'INDEX.json').write_text(json.dumps(index,ensure_ascii=False,indent=2),encoding='utf-8')
    excluded=json.loads((OUT/'EXCLUDED.json').read_text());excluded=[x for x in excluded if not(x['stage']=='A01' and x['path'] in additions)]
    (OUT/'EXCLUDED.json').write_text(json.dumps(excluded,ensure_ascii=False,indent=2),encoding='utf-8')
    save(E/'completeness-audit.json',{'vendor_text_sources_added':len(additions),'A01_final':v,'reason':'Include CPU assembly, grammars and complete upstream text source; media/compiled wrapper dependencies remain excluded'})
    print(json.dumps({'vendor_text_sources_added':len(additions),'A01_final':v}))
def complete_inputs():
    common=['contracts','scripts/release','platform/a1/lease.py','platform/a1/record.py','platform/a1/collect_board.py','platform/ra02/build_queue.py','docs/DESIGN_GAP.md','docs/TEST_MATRIX.md','docs/DECISIONS.md','docs/AI_ASSISTANCE.md']
    index=json.loads((OUT/'INDEX.json').read_text());counts={}
    for stage in SCOPES:
        dest=OUT/stage;m=json.loads((dest/'MANIFEST.json').read_text(encoding='utf-8'));add={}
        names=list(common)
        if stage=='A01':
            names += ['artifacts/qwen35-0.8b/source/'+n for n in ['config.json','LICENSE','README.md','chat_template.jinja','tokenizer_config.json','tokenizer.json','merges.txt','vocab.json','model.safetensors.index.json']]
        for name in names:
            for p in scan(R/name):
                if not p.is_file() or p.is_symlink() or '__pycache__' in p.parts:continue
                n=p.relative_to(R).as_posix()
                if n in m['files'] or n in m['already_uploaded']:continue
                if p.suffix.lower() not in ALLOW and p.name not in SPECIAL:continue
                b=p.read_bytes()
                if any(pattern.search(b) for pattern in SECRET):raise ValueError('Potential credential: '+n)
                add[n]=b;m['files'][n]={'sha256':sha(b),'bytes':len(b)}
        archive=OUT/index['stages'][stage]['archive'];tmp=dest/(stage+'-inputs.tmp.zip')
        with zipfile.ZipFile(archive) as old,zipfile.ZipFile(tmp,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as new:
            for n in old.namelist():
                if n!='MANIFEST.json':new.writestr(n,old.read(n))
            for n,b in add.items():new.writestr('project/'+n,b)
            new.writestr('MANIFEST.json',json.dumps(m,ensure_ascii=False,indent=2).encode())
        with zipfile.ZipFile(tmp) as z:
            assert z.testzip() is None and len(z.namelist())==len(set(z.namelist()))
            for n,v in m['files'].items():assert sha(z.read('project/'+n))==v['sha256']
        os.replace(tmp,archive);assert archive.stat().st_size<50*1024*1024
        (dest/'MANIFEST.json').write_text(json.dumps(m,ensure_ascii=False,indent=2),encoding='utf-8')
        index['stages'][stage].update(new_files=len(m['files']),bytes=archive.stat().st_size,sha256=sha(archive.read_bytes()));counts[stage]=len(add)
    (OUT/'INDEX.json').write_text(json.dumps(index,ensure_ascii=False,indent=2),encoding='utf-8')
    save(E/'input-completeness.json',{'added_counts':counts,'scope':'Legacy and current contracts, helper code, model metadata/tokenizer; no weight bytes','archives':index['stages']})
    print(json.dumps({'input_completeness':'PASS','counts':counts}))
if __name__=='__main__':{'prepare':prepare,'supplement-vendor':supplement_vendor,'complete-inputs':complete_inputs,'publish':publish}[sys.argv[1]]()
