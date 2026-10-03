"""Authorized A07 completion upload, exact bytes, isolated index, no force push."""
import hashlib,json,os,subprocess,tempfile
from pathlib import Path
R=Path(__file__).resolve().parents[3]
P=R/'release/a07_b04_v3'; E=R/'evidence/A07_publication/20261004-v3'
BRANCH='a/a07-complete-20261004'
BASE='26332e0907dd41990f0071164a91d1216a9ac45d'
URL='https://github.com/4hydrofuran/patient-FPGA.git'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):
    with p.open('x',encoding='utf-8') as f:json.dump(v,f,indent=2,ensure_ascii=False)
def git(*args,env=None,data=None):
    q=subprocess.run(['git',*args],cwd=R,env=env,input=data,capture_output=True)
    if q.returncode:raise RuntimeError(q.stderr.decode('utf-8',errors='replace'))
    return q.stdout
def main():
    E.mkdir(parents=True,exist_ok=False)
    assert git('remote','get-url','origin').decode().strip()==URL
    assert not git('ls-remote','--heads','origin','refs/heads/'+BRANCH).strip(),'branch exists; never overwrite'
    head=git('rev-parse','HEAD').decode().strip();index=git('diff','--cached','--raw')
    assert git('cat-file','-t',BASE).strip()==b'commit'
    manifest=json.loads((P/'files.sha256.json').read_text(encoding='utf-8'))
    report=json.loads((R/'evidence/A07_closeout/20261004-v1/REPORT.json').read_text(encoding='utf-8'))
    assert report['status']=='PASS_A07_OFFLINE' and sha(P/'files.sha256.json')==report['delivery_seal_sha256']
    files=[]
    for name,item in manifest.items():
        p=P/name
        assert p.resolve().is_relative_to(P.resolve()) and not p.is_symlink()
        assert sha(p)==item['sha256'] and p.stat().st_size==item['bytes'],name
        files.append(p)
    files.append(P/'files.sha256.json')
    for name in ['REPORT.md','REPORT.json','closeout-command.json','clean-run.json','package-final-verification.json','link-run.json','audit-v3-run.json','implementation-review.json','contracts-final.json','config-final.json']:
        files.append(R/'evidence/A07_closeout/20261004-v1'/name)
    files.extend([R/'docs/handoffs/A_A07_CLOSEOUT_20261004.md',R/'A07_COMPLETE_20261004.md',Path(__file__).resolve()])
    files=sorted(set(files));names=[p.relative_to(R).as_posix() for p in files]
    for p in files:
        assert p.suffix.lower() not in {'.lic','.pem','.key','.gguf','.safetensors','.wic','.vhd','.vhdx','.pyc'},p
        assert p.stat().st_size<50*1024*1024,p
    assert all('\n' not in n and '\r' not in n for n in names)
    save(E/'preflight.json',{'remote':URL,'branch':BRANCH,'parent':BASE,'working_head':head,
        'files':{n:{'bytes':p.stat().st_size,'sha256':sha(p)} for n,p in zip(names,files)},
        'status':'EXACT_SEALED_DELIVERY_VALIDATED','BOARD':'NOT_TESTED'})
    print(f'Validated {len(files)} selected files; creating exact-byte commit.',flush=True)
    # No filters: preserve binary and CRLF/LF evidence exactly. Do not touch normal index.
    blobs=git('hash-object','-w','--no-filters','--stdin-paths',data=('\n'.join(names)+'\n').encode('utf-8')).decode().splitlines()
    assert len(blobs)==len(files)
    with tempfile.TemporaryDirectory(prefix='a07-complete-publish-') as tmp:
        env=os.environ.copy();env['GIT_INDEX_FILE']=str(Path(tmp)/'index')
        git('read-tree',BASE,env=env)
        entries=b''.join(f'100644 {blob}\t{name}'.encode('utf-8')+b'\0' for name,blob in zip(names,blobs))
        git('update-index','-z','--index-info',env=env,data=entries)
        tree=git('write-tree',env=env).decode().strip()
        commit=git('-c','user.name=Member A (Codex)','-c','user.email=codex@localhost','commit-tree',tree,'-p',BASE,
            '-m','A07 complete offline delivery: routed xclbin, A53 runtime, control tests and clean reproduction',env=env).decode().strip()
    # Re-read Git objects and compare every selected file with the sealed local bytes.
    data=git('cat-file','--batch',data=('\n'.join(f'{commit}:{n}' for n in names)+'\n').encode('utf-8'))
    pos=0
    for p in files:
        end=data.index(b'\n',pos);header=data[pos:end].split();assert header[1]==b'blob'
        size=int(header[2]);content=data[end+1:end+1+size]
        assert hashlib.sha256(content).hexdigest()==sha(p),p
        pos=end+1+size+1
    assert pos==len(data)
    git('update-ref','refs/heads/'+BRANCH,commit,'0'*40)
    save(E/'commit.json',{'commit':commit,'tree':tree,'branch':BRANCH,'files':len(files),'git_blob_SHA256_verified':True})
    print('Exact Git blobs verified; pushing A07 completion branch.',flush=True)
    git('push','origin','refs/heads/'+BRANCH+':refs/heads/'+BRANCH)
    remote=git('ls-remote','--heads','origin','refs/heads/'+BRANCH).decode().strip()
    assert remote.split()[0]==commit
    assert git('rev-parse','HEAD').decode().strip()==head and git('diff','--cached','--raw')==index
    save(E/'publish.json',{'status':'PUSHED_AND_REMOTE_SHA_VERIFIED','commit':commit,'branch':BRANCH,'remote':URL,
        'remote_ref':remote,'files_added':len(files),'delivery':'release/a07_b04_v3',
        'delivery_seal_sha256':sha(P/'files.sha256.json'),'current_HEAD_and_index_unchanged':True,
        'A07':'PASS_A07_OFFLINE','BOARD':'NOT_TESTED','old_delivery_preserved':True,'main_and_B_branches_changed':False})
    print(json.dumps({'status':'PUSHED_AND_VERIFIED','commit':commit,'branch':BRANCH,'files':len(files)}),flush=True)
if __name__=='__main__':main()
