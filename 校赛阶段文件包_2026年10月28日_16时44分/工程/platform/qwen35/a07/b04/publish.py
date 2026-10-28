"""Explicit narrow publication via a temporary index; preserve working HEAD/index.

User authorized GitHub upload. No force push, no credentials in argv, no PR.
"""
import hashlib,json,os,re,subprocess,tempfile
from pathlib import Path
R=Path(__file__).resolve().parents[4]
E=R/'evidence/A07_B04/v1'
P=R/'release/a07_b04_v1'
BRANCH='a/a07-b04-runtime-20261003'
URL='https://github.com/4hydrofuran/patient-FPGA.git'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,obj):
    with p.open('x',encoding='utf-8') as f:json.dump(obj,f,indent=2,ensure_ascii=False)
def git(*args,env=None,data=None):
    r=subprocess.run(['git',*args],cwd=R,env=env,input=data,capture_output=True)
    if r.returncode:raise RuntimeError(r.stderr.decode(errors='replace'))
    return r.stdout
def main():
    if git('remote','get-url','origin').decode().strip()!=URL:raise ValueError('wrong remote')
    if git('ls-remote','--heads','origin','refs/heads/'+BRANCH).strip():raise ValueError('remote branch exists; no overwrite')
    before_head=git('rev-parse','HEAD').decode().strip()
    before_index=git('diff','--cached','--raw')
    manifest=json.loads((P/'files.sha256.json').read_text())
    files=[]
    for name,item in manifest.items():
        p=P/name
        if not p.resolve().is_relative_to(P.resolve()) or p.is_symlink():raise ValueError('unsafe path')
        if digest(p)!=item['sha256'] or p.stat().st_size!=item['bytes']:raise ValueError('package hash mismatch '+name)
        files.append(p)
    files.append(P/'files.sha256.json')
    files.extend(p for p in E.glob('*.json') if p.name not in ('publish.json','publish-preflight.json'))
    files += [E/'REPORT.md',R/'docs/handoffs/A_A07_B04_20261003.md']
    files=sorted(set(files))
    secret=re.compile(rb'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}')
    for p in files:
        if p.suffix.lower() in {'.lic','.key','.pem','.gguf','.safetensors','.wic','.xo','.xclbin','.vhdx','.pyc'}:raise ValueError('excluded file '+str(p))
        if p.stat().st_size>25*1024*1024:raise ValueError('oversize '+str(p))
        if secret.search(p.read_bytes()):raise ValueError('secret pattern; review locally without printing')
    save(E/'publish-preflight.json',{'branch':BRANCH,'remote':URL,'working_head':before_head,
        'files':{p.relative_to(R).as_posix():{'bytes':p.stat().st_size,'sha256':digest(p)} for p in files},
        'publication_type':'independent delivery snapshot; no B/C branch or current HEAD/index changes',
        'secret_pattern_scan':'PASS_NOT_A_GENERAL_SECRET_GUARANTEE'})
    # New empty temporary index: excludes ALL unrelated dirty/history files.
    with tempfile.TemporaryDirectory(prefix='a07-publish-') as temp:
        env=os.environ.copy();env['GIT_INDEX_FILE']=str(Path(temp)/'index')
        git('read-tree','--empty',env=env)
        entries=[]
        for p in files:
            rel=p.relative_to(R).as_posix()
            # Raw blob hashes preserve exact CRLF/LF evidence despite root attributes.
            blob=git('hash-object','-w','--no-filters','--',rel).decode().strip()
            entries.append(f'100644 {blob}\t{rel}\n')
        git('update-index','--index-info',env=env,data=''.join(entries).encode())
        tree=git('write-tree',env=env).decode().strip()
        commit=git('-c','user.name=Member A (Codex)','-c','user.email=codex@localhost','commit-tree',tree,
            '-m','A07/B04 partial runtime delivery: meta fixes, ARM64 library/host, honest pending gates',env=env).decode().strip()
    git('update-ref','refs/heads/'+BRANCH,commit,'0'*40)
    # Normal non-force push only to a fresh A-owned branch.
    result=git('push','origin','refs/heads/'+BRANCH+':refs/heads/'+BRANCH).decode(errors='replace')
    remote=git('ls-remote','--heads','origin','refs/heads/'+BRANCH).decode().strip()
    if remote.split()[0]!=commit:raise ValueError('remote verification differs')
    if git('rev-parse','HEAD').decode().strip()!=before_head or git('diff','--cached','--raw')!=before_index:
        raise RuntimeError('concurrent HEAD/index change; inspect, do not reset')
    save(E/'publish.json',{'status':'PUSHED_AND_REMOTE_SHA_VERIFIED','remote':URL,'branch':BRANCH,'commit':commit,
        'file_count':len(files),'tree':tree,'push_stdout':result,'remote_ref':remote,
        'working_HEAD_and_index_unchanged':True,'A07_acceptance':'PARTIAL','BOARD':'NOT_TESTED'})
    print(json.dumps({'commit':commit,'branch':BRANCH,'files':len(files),'status':'PUSHED_PARTIAL'}))
if __name__=='__main__':main()
