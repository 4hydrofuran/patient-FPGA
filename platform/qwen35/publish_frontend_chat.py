"""Package and publish only this frontend chat; use a separate Git index."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile
import publish_a12_resource_probe as common

ROOT=common.ROOT
BASE='ec5542e7a86f670410550661a4c46f2b206317f4'
GATEWAY='40498c2388b6293d68f38907c71ffd8933a5803e'
BRANCH='codex/frontend-continuous-delivery-20261026'
REL='release/frontend_chat_20261026'
EV=ROOT/'evidence/frontend_chat_publication/20261026-v1'
TEXT={'.py','.ps1','.sh','.md','.json','.jsonl','.txt','.png','.cfg','.jinja','.yml','.yaml'}


def sha(data):return hashlib.sha256(data).hexdigest()
def encoded(obj):return (json.dumps(obj,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
def write(path,data):
    path=ROOT/path;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)


def inspect(name,data,depth=0):
    common.scan(name,data)
    if name.lower().endswith(('.gguf','.safetensors','.pem','.key','.lic','.wic','.vhdx','.deb','.exe')):
        raise RuntimeError('Out-of-scope artifact: '+name)
    if data.startswith(b'PK\x03\x04'):
        if depth>=3:raise RuntimeError('Unexpected archive nesting: '+name)
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            if z.testzip() is not None:raise RuntimeError('Archive CRC: '+name)
            for info in z.infolist():
                if not info.is_dir():inspect(name+':'+info.filename,z.read(info),depth+1)


def tree_files(commit,prefix):
    for entry in common.git('ls-tree','-r','-z',commit,'--',prefix).split(b'\0'):
        if not entry:continue
        meta,name=entry.split(b'\t',1);mode,kind,oid=meta.decode().split()
        if kind!='blob':continue
        yield name.decode(),mode,common.git('cat-file','blob',oid)


def payload():
    files={};origins={};excluded=[]
    def add(name,data,origin,mode='100644'):
        if len(data)>90*1024*1024:raise RuntimeError('Git object too large: '+name)
        inspect(name,data);files[name]=(mode,data);origins[name]=origin
    # This chat's implementation, tests and actual board operation/evidence files.
    for directory in ('platform/qwen35/web','bench/qwen35/web','evidence/frontend_board_A'):
        for p in sorted((ROOT/directory).rglob('*')):
            if not p.is_file() or '__pycache__' in p.parts or p.is_symlink():continue
            if p.suffix=='.py' and p.read_bytes().startswith(b'PK\x03\x04'):
                excluded.append(dict(path=p.relative_to(ROOT).as_posix(),reason='Temporary HTTP transport name contains downloaded input-method package archive, not Python source'))
                continue
            archive=p.suffix=='.zip' and ('overlay' in p.name or p.name=='board-receipt.zip')
            if p.suffix in TEXT or archive:add(p.relative_to(ROOT).as_posix(),p.read_bytes(),'THIS_CHAT')
    for p in sorted((ROOT/'docs/handoffs').glob('A_FRONTEND*.md')):
        add(p.relative_to(ROOT).as_posix(),p.read_bytes(),'THIS_CHAT')
    for name in ('docs/handoffs/A_HDMI_GRAPHICAL_PREVIEW_20261026.md','docs/FRONTEND_CHAT_SUMMARY_20261026.md',
                 'system_qwen35/app/web_managed.py','system_qwen35/app/native_pl.py',
                 'platform/qwen35/publish_frontend_chat.py'):
        add(name,(ROOT/name).read_bytes(),'THIS_CHAT_OR_REUSED_APPLICATION_DEPENDENCY')
    # The previously published gateway is a pinned, unchanged dependency.
    for name,mode,data in tree_files(GATEWAY,'web_gateway'):
        add(name,data,'GATEWAY_COMMIT:'+GATEWAY,mode)
    # Minimal dependencies needed by the included offline tests, from the base.
    for name in ('system_qwen35/__init__.py','system_qwen35/app/__init__.py','system_qwen35/app/native.py',
                 'platform/qwen35/a12/capacity_policy.py','platform/qwen35/publish_a12_resource_probe.py'):
        if name not in files:add(name,common.git('show',BASE+':'+name),'BASE_COMMIT:'+BASE)
    pinned='evidence/model_pl_A/20261026-pl-authfix-board-v2/bundle-fixed-v2/'
    for suffix in ('control/resource_probe_manager.py','control/support/kernel_log_gate.py',
                   'platform/qwen35/a12/cpu01b_kernel_gate.py','platform/qwen35/a12/cpu02_support.py','platform/qwen35/a12/cpu01b_observer.py'):
        name=pinned+suffix;add(name,(ROOT/name).read_bytes(),'TESTED_BASE_SOURCE_FIXTURE')
    exclusions=encoded(dict(excluded=excluded,other_exclusions=['Downloaded .deb/.exe and ime-packages.zip','Model weights, credentials, licenses and system images','Other chats dirty working files']))
    write(REL+'/EXCLUDED.json',exclusions);add(REL+'/EXCLUDED.json',exclusions,'PUBLICATION_METADATA')
    return files,origins


def prepare():
    if common.git('remote','get-url','origin').decode().strip()!=common.REMOTE:raise RuntimeError('Remote differs')
    if common.git('ls-remote','--heads','origin','refs/heads/'+BRANCH).strip():raise RuntimeError('Destination exists')
    EV.mkdir(parents=True,exist_ok=True)
    if (EV/'PREPARED.json').exists():raise RuntimeError('Already prepared')
    if (EV/'WORKSPACE_BEFORE.json').exists():
        if json.loads((EV/'WORKSPACE_BEFORE.json').read_text())!=common.workspace():raise RuntimeError('Working HEAD or index changed')
    else:write(EV.relative_to(ROOT)/'WORKSPACE_BEFORE.json',encoded(common.workspace()))
    # Ensure the implementation being published is the actual final deployed one.
    runtime=json.loads((ROOT/'evidence/frontend_board_A/20261026-continuous-session-v1/SOURCES.json').read_text())
    for name,pin in runtime['files'].items():
        p=ROOT/('system_qwen35/app/'+name if name in ('web_managed.py','native_pl.py') else 'platform/qwen35/web/'+name)
        if sha(p.read_bytes())!=pin:raise RuntimeError('Runtime source changed after board test: '+name)
    readme='''# 本窗口前端工程交付

入口：[任务总结](../../docs/FRONTEND_CHAT_SUMMARY_20261026.md)。最后状态：板子已正常关机。

`engineering-package.zip` 包含本窗口源码、网关依赖、离线测试、部署过程和实际成功/失败/关机证据；逐文件摘要见MANIFEST.json、SHA256SUMS.txt。

网关依赖固定为frontend/web-gateway-20261026 / 40498c2388b6293d68f38907c71ffd8933a5803e；分支基于已发布A12交付ec5542e7a86f670410550661a4c46f2b206317f4。依赖随包提供不代表本窗口重新验证其全部功能。

解压到新目录后，在有Jinja2的Linux Python环境运行：`python3 -m unittest discover -s bench/qwen35/web -v`。

本包不含模型权重、整机镜像、凭据、许可证或下载的输入法安装包。板端仍需既有已验收普通bundle、模型与Python环境。已包含的部署脚本是实际操作记录，不可原样重放已消费的窗口；再次部署使用新的独立目录/Owner，先核对现场内核和占用。包不是刷写镜像，不带可重放的计算授权。

历史文档和回执原样保留；最新结论以任务总结、连续服务REPORT和最终关机证据为准。所有PC协议替身仍是PC测试，不替代BOARD。60000次/4小时是配置，不冒充已经通过4小时压力试验。
'''
    write(REL+'/README.md',readme.encode('utf-8'))
    files,origins=payload()
    files[REL+'/README.md']=('100644',readme.encode('utf-8'));origins[REL+'/README.md']='PUBLICATION_METADATA'
    entries=[dict(path=name,mode=mode,bytes=len(data),sha256=sha(data),origin=origins[name]) for name,(mode,data) in sorted(files.items())]
    manifest=dict(schema='FRONTEND_CHAT_DELIVERY_V1',base=BASE,gateway=GATEWAY,branch=BRANCH,
                  scope='THIS_CHAT_FRONTEND_ENGINEERING_WITH_PINNED_DEPENDENCIES',board_state='POWER_DOWN_CONFIRMED',files=entries)
    manifest_data=encoded(manifest);write(REL+'/MANIFEST.json',manifest_data)
    sums=''.join(r['sha256']+'  '+r['path']+'\n' for r in entries)+sha(manifest_data)+'  '+REL+'/MANIFEST.json\n'
    write(REL+'/SHA256SUMS.txt',sums.encode())
    files[REL+'/MANIFEST.json']=('100644',manifest_data);files[REL+'/SHA256SUMS.txt']=('100644',sums.encode())
    archive=ROOT/REL/'engineering-package.zip'
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for name,(mode,data) in sorted(files.items()):
            info=zipfile.ZipInfo(name,date_time=(2026,10,26,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=(int(mode,8)<<16);z.writestr(info,data)
    package=dict(schema='FRONTEND_PACKAGE_V1',path=REL+'/engineering-package.zip',bytes=archive.stat().st_size,
                 sha256=sha(archive.read_bytes()),files=len(files),manifest_sha256=sha(manifest_data))
    write(REL+'/PACKAGE.json',encoded(package))
    write(EV.relative_to(ROOT)/'PREPARED.json',encoded(dict(status='PREPARED',package=package,workspace=common.workspace())))
    print(json.dumps(package))


def publish():
    before=json.loads((EV/'WORKSPACE_BEFORE.json').read_text())
    if common.workspace()!=before:raise RuntimeError('Working HEAD or index changed')
    if common.git('ls-remote','--heads','origin','refs/heads/'+BRANCH).strip():raise RuntimeError('Destination exists')
    manifest=json.loads((ROOT/REL/'MANIFEST.json').read_text(encoding='utf-8'))
    archive=ROOT/REL/'engineering-package.zip';package=json.loads((ROOT/REL/'PACKAGE.json').read_text())
    if sha(archive.read_bytes())!=package['sha256']:raise RuntimeError('Package changed')
    with zipfile.ZipFile(archive) as z:
        rows=[];oids=[]
        for r in manifest['files']:
            data=z.read(r['path'])
            if sha(data)!=r['sha256']:raise RuntimeError('Package member changed')
            rows.append((r['path'],r['mode']));oids.append(common.git('hash-object','-w','--stdin',data=data).decode().strip())
    for name in ('MANIFEST.json','SHA256SUMS.txt','PACKAGE.json','engineering-package.zip'):
        p=ROOT/REL/name;rows.append((REL+'/'+name,'100644'))
        oids.append(common.git('hash-object','-w','--no-filters',str(p)).decode().strip())
    with tempfile.TemporaryDirectory(prefix='frontend-publish-index-') as directory:
        env=dict(os.environ,GIT_INDEX_FILE=str(Path(directory)/'index'))
        common.git('read-tree',BASE,env=env)
        data=b''.join((mode+' '+oid+'\t'+name).encode()+b'\0' for (name,mode),oid in zip(rows,oids))
        common.git('update-index','-z','--index-info',data=data,env=env)
        tree=common.git('write-tree',env=env).decode().strip()
        message='Deliver graphical frontend integration and continuous consultations\n\nInclude this chat summary, pinned gateway, tested runtime adapters, offline tests, retained failures, board evidence and normal shutdown record.\n'
        commit=common.git('-c','user.name=Member A (Codex)','-c','user.email=codex@localhost','commit-tree',tree,'-p',BASE,data=message.encode()).decode().strip()
    changed={p for p in common.git('diff-tree','--no-commit-id','--name-only','-r','-z',BASE,commit).decode().split('\0') if p}
    if not changed.issubset({name for name,mode in rows}):raise RuntimeError('Unexpected commit changes')
    if common.workspace()!=before:raise RuntimeError('Working checkout changed')
    write(EV.relative_to(ROOT)/'COMMIT.json',encoded(dict(commit=commit,tree=tree,branch=BRANCH,changed_files=len(changed))))
    common.git('push','origin',commit+':refs/heads/'+BRANCH)
    remote=common.git('ls-remote','--heads','origin','refs/heads/'+BRANCH).decode().split()[0]
    if remote!=commit:raise RuntimeError('Remote SHA differs')
    if common.workspace()!=before:raise RuntimeError('Working checkout changed after publication')
    result=dict(status='PUSHED_AND_REMOTE_SHA_VERIFIED',commit=commit,branch=BRANCH,changed_files=len(changed),package_sha256=package['sha256'],working_HEAD_branch_index_unchanged=True,board_contact=False)
    write(EV.relative_to(ROOT)/'PUBLISHED.json',encoded(result));print(json.dumps(result))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=('prepare','publish'))
    if parser.parse_args().action=='prepare':prepare()
    else:publish()
