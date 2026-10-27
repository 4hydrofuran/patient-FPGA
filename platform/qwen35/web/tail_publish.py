"""Publish only the sealed delivery allowlist through the existing isolated worktree."""
import argparse
from datetime import datetime,timezone,timedelta
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[3]
BASE='e7a76cb0d60ae087f796c98fcb10def74733042b'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def stamp():return datetime.now(timezone(timedelta(hours=8))).isoformat()
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def publish(a):
    root=a.root.resolve();work=a.worktree.resolve()
    def git(*args,binary=False):
        result=subprocess.run(['git','-c','core.autocrlf=false','-c','gc.auto=0','-c','credential.interactive=false',
            '-c','user.name=Member A (Codex)','-c','user.email=codex@localhost','-C',str(work),*args],
            capture_output=True,check=True)
        return result.stdout if binary else result.stdout.decode('utf-8').strip()
    assert git('rev-parse','HEAD')==BASE and not git('status','--porcelain')
    assert not subprocess.check_output(['git','-C',str(ROOT),'diff','--cached','--name-only'])
    delivery=read(root/'DELIVERY.json');assert delivery['status']=='PASS_ALL_ARCHIVES_CRC_SHA_READBACK'
    rows=read(root/'ENGINEERING_MANIFEST.json')['files']
    selected={r['path']:r['sha256'] for r in rows}
    for p in root.rglob('*'):
        if not p.is_file() or '__pycache__' in p.parts or p.suffix=='.pyc':continue
        if p.suffix=='.zip' and p.name!=delivery['recommended']['name']:continue
        selected[p.relative_to(ROOT).as_posix()]=sha(p)
    assert sha(root/delivery['recommended']['name'])==delivery['recommended']['sha256']
    git('checkout','-b',a.branch)
    for relative,expected in selected.items():
        source=ROOT/relative;assert sha(source)==expected,relative
        dest=work/relative;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,dest)
    allowlist=root/'PUBLISH_ALLOWLIST.nul'
    allowlist.write_bytes(b''.join(p.encode('utf-8')+b'\0' for p in sorted(selected)))
    git('add','-f','--pathspec-from-file='+str(allowlist),'--pathspec-file-nul')
    staged=git('diff','--cached','--name-only','-z',binary=True).decode('utf-8').strip('\0').split('\0')
    assert staged and set(staged)<=set(selected)
    index={}
    for entry in git('ls-files','--stage','-z',binary=True).split(b'\0'):
        if not entry:continue
        header,name=entry.split(b'\t',1);index[name.decode('utf-8')]=header.split()[1].decode()
    for relative in staged:
        data=(ROOT/relative).read_bytes()
        assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==index[relative],relative
    git('commit','-m','Optimize A12 real-model tail latency with dual neutral prefixes; package PC evidence')
    payload=git('rev-parse','HEAD');push_started=stamp()
    git('push','-u','origin',a.branch)
    remote=git('ls-remote','origin','refs/heads/'+a.branch).split()[0];assert remote==payload
    receipt=dict(status='PASS_REMOTE_PAYLOAD_VERIFIED',branch=a.branch,repository='https://github.com/4hydrofuran/patient-FPGA',
        payload_commit=payload,push_started_at=push_started,remote_verified_at=stamp(),timezone='Asia/Shanghai UTC+08:00',
        recommended_archive=delivery['recommended'],staged_files=len(staged),selected_files=len(selected),
        staging='explicit allowlist in isolated worktree; byte-exact index verified',BOARD='NOT_TESTED')
    save(root/'PUBLISH_RECEIPT.json',receipt)
    receipt_relative=(root/'PUBLISH_RECEIPT.json').relative_to(ROOT).as_posix()
    shutil.copyfile(root/'PUBLISH_RECEIPT.json',work/receipt_relative)
    git('add','-f','--',receipt_relative);git('commit','-m','Record verified A12 delivery upload time and payload commit')
    git('push','origin',a.branch)
    head=git('rev-parse','HEAD');assert git('ls-remote','origin','refs/heads/'+a.branch).split()[0]==head
    assert not git('status','--porcelain')
    assert not subprocess.check_output(['git','-C',str(ROOT),'diff','--cached','--name-only'])
    print(json.dumps(dict(status='PASS_REMOTE_FINAL_HEAD_AND_CLEAN_WORKTREE',branch=a.branch,payload_commit=payload,
        final_commit=head,remote_verified_at=stamp(),archive=delivery['recommended']),indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True)
    p.add_argument('--branch',required=True);p.add_argument('--worktree',type=Path,default=Path('C:/Patientqwen_publish/a12_fast_response_cache_20261027'))
    publish(p.parse_args())
