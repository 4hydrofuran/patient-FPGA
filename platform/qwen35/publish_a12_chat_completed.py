"""Publish completed A12 chat work through an isolated index; never touch Board."""
import argparse,hashlib,io,json,os,subprocess,tarfile,tempfile,zipfile
from pathlib import Path
import publish_a12_resource_probe as common

ROOT=common.ROOT
BASE='0bbebc78f4abdb8a5b339db21e97518c34389242'
BRANCH='codex/a12-chat-completed-20261026'
EV=ROOT/'evidence/a12_chat_publication/20261026-v1'
REL=ROOT/'release/a12_chat_completed_20261026'
INDEX=ROOT/'docs/A12_CHAT_DELIVERY_20261026.md'
MODEL=ROOT/'evidence/model_pl_A'
FULL=('20261026-resident-v1','20261026-prompt-private-v1','20261026-basic-cpu-board-v1',
      '20261026-original-pl-board-v1','20261026-pl-authfix-board-v1',
      '20261026-pl-authfix-board-v2','20261026-upload-only-v1')
TEXT={'.py','.ps1','.sh','.cpp','.cc','.c','.h','.hpp','.cs','.cmake','.md','.json','.jsonl','.txt','.patch','.cfg','.jinja','.jinja2','.yaml','.yml','.lock'}

def write(p,obj):
 p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def digest(data):return hashlib.sha256(data).hexdigest()

def inspect(name,data,depth=0):
 common.scan(name,data)
 lower=name.lower()
 if lower.endswith(('.gguf','.safetensors','.vhd','.vhdx','.wic','.pem','.key')):
  raise RuntimeError('Model/image/key artifact is outside publication scope: '+name)
 if depth>3:raise RuntimeError('Nested archive exceeds publication depth: '+name)
 if data.startswith(b'PK\x03\x04'):
  with zipfile.ZipFile(io.BytesIO(data)) as z:
   for member in z.infolist():
    if not member.is_dir():inspect(name+':'+member.filename,z.read(member),depth+1)
 elif lower.endswith(('.tar.gz','.tgz')):
  with tarfile.open(fileobj=io.BytesIO(data),mode='r:gz') as t:
   for member in t:
    if member.isfile():inspect(name+':'+member.name,t.extractfile(member).read(),depth+1)

def selected():
 files=set();excluded=[]
 def add(p):
  if p.is_file() and not p.is_symlink():files.add(p)
 # A12 source and its existing runtime/application dependencies; not A13 work.
 for directory in ('platform/qwen35/a12','runtime/qwen35_w4a8/a12','runtime/qwen35_w4a8',
                   'system_qwen35/app','contracts/qwen35','config/qwen35','modules/linear_A'):
  for p in (ROOT/directory).rglob('*'):
   if '__pycache__' in p.parts:continue
   if p.suffix in TEXT or p.name=='CMakeLists.txt':add(p)
 add(ROOT/'system_qwen35/__init__.py')
 add(ROOT/'modules/voice_A/manifest.json')
 for p in (ROOT/'system_qwen35/cases').glob('SYN*.json'):add(p)
 for pattern in ('A12*.md',):
  for p in (ROOT/'docs').glob(pattern):add(p)
 for pattern in ('A_A12*','A12_*'):
  for p in (ROOT/'docs/handoffs').glob(pattern):
   if p.suffix in TEXT:add(p)
 for p in (ROOT/'docs/status').glob('A12*'):add(p)
 for name in FULL:
  for p in (MODEL/name).rglob('*'):
   if not p.is_file() or '__pycache__' in p.parts:continue
   relative=p.relative_to(MODEL/name)
   if len(relative.parts)>1 and relative.parts[0].startswith('bundle-fixed-'):
    excluded.append(dict(path=p.relative_to(ROOT).as_posix(),reason='Expanded runtime duplicate; immutable ZIP is published'))
    continue
   if p.suffix in TEXT or p.name.endswith(('.zip','.tar.gz','.tgz')):add(p)
   else:excluded.append(dict(path=p.relative_to(ROOT).as_posix(),reason='Loose generated/binary file; sealed review package retains reviewed content'))
 # Top-level build/review receipts are dependency evidence for the sealed work.
 for directory in MODEL.glob('20261026-*'):
  if directory.name in FULL:continue
  for p in directory.iterdir():
   if p.suffix in {'.json','.md','.py','.txt','.sh'}:add(p)
 # Existing admission/runtime helpers needed to interpret or rebuild these sources.
 for directory in ('platform/qwen35/a10','platform/qwen35/a11','runtime/qwen35_cpu'):
  for p in (ROOT/directory).rglob('*'):
   if '__pycache__' not in p.parts and p.suffix in TEXT:add(p)
 for name in ('scripts/release/check_contracts.py','scripts/release/qwen35_config.py',
              'platform/qwen35/publish_a12_chat_completed.py'):add(ROOT/name)
 return files,excluded

def prepare(refresh=False):
 if common.git('remote','get-url','origin').decode().strip()!=common.REMOTE:raise RuntimeError('Remote differs')
 if common.git('ls-remote','--heads','origin','refs/heads/'+BRANCH).strip():raise RuntimeError('Destination exists; no overwrite')
 EV.mkdir(parents=True,exist_ok=True);REL.mkdir(parents=True,exist_ok=True)
 if (EV/'PREPARED.json').exists():
  if not refresh:raise RuntimeError('Already prepared; publish the existing review')
  version=1
  while (EV/f'PREPARED-first-v{version}.json').exists():version+=1
  (EV/'PREPARED.json').rename(EV/f'PREPARED-first-v{version}.json')
  (EV/f'MANIFEST-first-v{version}.json').write_bytes((REL/'MANIFEST.json').read_bytes())
 if (EV/'WORKSPACE_BEFORE.json').exists():
  if json.loads((EV/'WORKSPACE_BEFORE.json').read_text())!=common.workspace():raise RuntimeError('Workspace changed since prepare')
 else:write(EV/'WORKSPACE_BEFORE.json',common.workspace())
 expected=json.loads((MODEL/'20261026-pl-authfix-board-v2/SUMMARY.json').read_text(encoding='utf-8'))
 assert expected['status']=='PASS_ORDINARY_R0_WARM_HIT_BOARD'
 assert expected['platform_restored'] and not expected['active_lease']
 scoped=dict(scope='COMPLETED_CHAT_WORK_ONLY_LATEST_OPTIMIZATION_SUGGESTIONS_EXCLUDED',
  ordinary_PL=expected,resident_candidate_BOARD='NOT_TESTED',
  resident_candidate_review=json.loads((MODEL/'20261026-resident-v1/FINAL_REVIEW.json').read_text(encoding='utf-8'))['status'],
  full_A12_acceptance=False,production_ready=False,board_contact_during_publication=False)
 write(ROOT/'docs/status/A12_CHAT_COMPLETED_20261026.json',scoped)
 INDEX.write_text('''# A12 本对话已完成工程交付（2026-10-26）

本次仅发布本对话已完成的工程、说明及其依赖/失败证据。上一条关于首token小于10秒的后续优化建议未纳入，也没有把建议写成已实现功能。

| 内容 | 实际状态与入口 |
| --- | --- |
| 普通PL验收及授权修复 | [最终报告](../evidence/model_pl_A/20261026-pl-authfix-board-v2/REPORT.md)：真实R0/warm/hit通过，2880次权限提交；完整核验应答60.71→27.85秒，单组样本；首token16.97秒，未达10秒 |
| 可复用普通探测包 | [bundle-fixed-v2.zip](../evidence/model_pl_A/20261026-pl-authfix-board-v2/bundle-fixed-v2.zip)：修复授权绑定、应用适配器导入和瞬时扫描中止；保持UNBOUND，授权不随包交付 |
| 无板常驻候选 | [收口说明](A12_PARALLEL_PREBOARD_CLOSEOUT_20261026.md)、[交接](handoffs/A_A12_BOUNDED_RESIDENT_NOBOARD_20261026.md)、[PC入口](A12_RESIDENT_PC_CLI_USAGE_20261026.md)：无板验证与A53制品准备完成，候选仍未板测 |
| 短提示词私有链前件 | [交接](handoffs/A_A12_FACTS_ONLY_PRIVATE_ROUTE_PC_20261026.md)：保留原PC证据与封存包，不追认为BOARD通过 |
| 文件传输和CPU基础运行 | [CPU报告](../evidence/model_pl_A/20261026-basic-cpu-board-v1/REPORT.md)、evidence/model_pl_A/20261026-upload-only-v1；CPU结果不替代PL验收 |
| 原PL失败与关机记录 | [失败报告](../evidence/model_pl_A/20261026-original-pl-board-v1/REPORT.md)、同目录shutdown.json；历史现场描述以各自记录时间为准 |
| 本次测试中的失败 | [v1记录](../evidence/model_pl_A/20261026-pl-authfix-board-v1/REPORT.md)、最终报告中的失败说明；旧失败、未知退出码与租约归档证据保留 |

最新板测结束时worker和管理器退出0，默认PL/GDM恢复，ZOCL卸载，活动租约为空。此为验收结束时的已记录状态，不是发布时重新访问板卡所得。整体A12、医学、长期稳定性及生产启用未完成。

源码包括A12工程及其既有运行时/应用依赖；依赖文件随包提供不表示本对话重新实施或验证了所有历史模块。原模型权重、开发机工具链、凭据、许可证和系统镜像不在交付范围。

当前汇总见[范围状态](status/A12_CHAT_COMPLETED_20261026.json)，完整文件清单及字节摘要见[发布清单](../release/a12_chat_completed_20261026/MANIFEST.json)。历史封存文档中NOT_TESTED和当时现场原样保留，最新结论以本页链接的最终PL报告为准。
''',encoding='utf-8')
 files,excluded=selected();files.add(INDEX)
 # Verify the two existing seals without rewriting their historical manifests.
 for directory in ('20261026-resident-v1','20261026-prompt-private-v1'):
  review=json.loads((MODEL/directory/'FINAL_REVIEW.json').read_text(encoding='utf-8'))
  pin=review.get('archive',dict(path='evidence/model_pl_A/20261026-prompt-private-v1/facts-only-private-PC-review-v1.zip',sha256='68ae3b18670b4f2bd65f4a42fd163155b223d0d1221f6483d547e14b391a4c25'));p=ROOT/pin['path']
  if digest(p.read_bytes())!=pin['sha256']:raise RuntimeError('Sealed archive differs: '+str(p))
 entries=[]
 for p in sorted(files):
  data=p.read_bytes();name=p.relative_to(ROOT).as_posix()
  if len(data)>90*1024*1024:raise RuntimeError('File too large: '+name)
  inspect(name,data)
  entries.append(dict(path=name,bytes=len(data),sha256=digest(data)))
 write(REL/'EXCLUDED.json',dict(excluded=excluded,not_published=['Latest optimization proposal','Model weights','Credentials and licenses','System images','Unrelated workspace/A13 changes']))
 entries.append(dict(path=(REL/'EXCLUDED.json').relative_to(ROOT).as_posix(),bytes=(REL/'EXCLUDED.json').stat().st_size,sha256=digest((REL/'EXCLUDED.json').read_bytes())))
 write(REL/'MANIFEST.json',dict(base=BASE,branch=BRANCH,scope=scoped['scope'],files=entries))
 (REL/'SHA256SUMS.txt').write_text(''.join(r['sha256']+'  '+r['path']+'\n' for r in entries),encoding='utf-8')
 write(EV/'PREPARED.json',dict(status='PREPARED',base=BASE,branch=BRANCH,files=len(entries)+2,
  bytes=sum(r['bytes'] for r in entries),manifest_sha256=digest((REL/'MANIFEST.json').read_bytes()),archives_scanned=True,latest_proposal_excluded=True))
 print(json.dumps(dict(files=len(entries)+2,MiB=round(sum(r['bytes'] for r in entries)/1048576,2),branch=BRANCH)))

def publish():
 before=json.loads((EV/'WORKSPACE_BEFORE.json').read_text())
 if common.workspace()!=before:raise RuntimeError('Workspace HEAD/index changed')
 if common.git('ls-remote','--heads','origin','refs/heads/'+BRANCH).strip():raise RuntimeError('Destination exists')
 manifest=json.loads((REL/'MANIFEST.json').read_text(encoding='utf-8'))
 rows=manifest['files'][:]
 for name in ('MANIFEST.json','SHA256SUMS.txt'):
  p=REL/name;rows.append(dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=digest(p.read_bytes())))
 paths=[]
 for r in rows:
  p=ROOT/r['path'];data=p.read_bytes()
  if len(data)!=r['bytes'] or digest(data)!=r['sha256']:raise RuntimeError('Prepared bytes changed: '+r['path'])
  paths.append(p.as_posix())
 oids=common.git('hash-object','-w','--no-filters','--stdin-paths',data=('\n'.join(paths)+'\n').encode()).decode().splitlines()
 assert len(oids)==len(rows)
 with tempfile.TemporaryDirectory(prefix='a12-chat-isolated-index-') as directory:
  env=dict(os.environ,GIT_INDEX_FILE=str(Path(directory)/'index'))
  common.git('read-tree',BASE,env=env)
  index=b''.join(('100644 '+oid+'\t'+r['path']).encode()+b'\0' for oid,r in zip(oids,rows))
  common.git('update-index','-z','--index-info',data=index,env=env)
  tree=common.git('write-tree',env=env).decode().strip()
  message='Publish completed A12 chat engineering and PL acceptance evidence\n\nInclude bounded resident candidate, CPU diagnostic, ordinary PL fixes and retained failures. Exclude the latest unimplemented latency optimization proposal.\n'
  commit=common.git('-c','user.name=Member A (Codex)','-c','user.email=codex@localhost',
                    'commit-tree',tree,'-p',BASE,data=message.encode()).decode().strip()
 actual_tree={}
 for item in common.git('ls-tree','-r','-z',commit).split(b'\0'):
  if item:
   meta,name=item.split(b'\t',1);actual_tree[name.decode()]=meta.split()[2].decode()
 if any(actual_tree.get(r['path'])!=oid for r,oid in zip(rows,oids)):raise RuntimeError('Commit tree bytes differ')
 changed=set(common.git('diff-tree','--no-commit-id','--name-only','-r','-z',BASE,commit).decode().strip('\0').split('\0'))
 if not changed.issubset({r['path'] for r in rows}):raise RuntimeError('Unexpected changed commit path')
 write(EV/'COMMIT.json',dict(commit=commit,tree=tree,branch=BRANCH,files=len(rows)))
 if common.workspace()!=before:raise RuntimeError('Workspace changed before push')
 common.git('push','origin',commit+':refs/heads/'+BRANCH)
 actual=common.git('ls-remote','--heads','origin','refs/heads/'+BRANCH).decode().split()[0]
 if actual!=commit:raise RuntimeError('Remote SHA differs')
 if common.workspace()!=before:raise RuntimeError('Workspace changed')
 write(EV/'PUBLISHED.json',dict(status='PUSHED_REMOTE_SHA_VERIFIED',commit=commit,branch=BRANCH,remote=common.REMOTE,
  files=len(rows),HEAD_branch_index_unchanged=True,latest_proposal_excluded=True,board_contact=False))
 print(json.dumps(dict(status='PUSHED_REMOTE_SHA_VERIFIED',commit=commit,branch=BRANCH,files=len(rows))))

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('action',choices=('prepare','reprepare','publish'));args=parser.parse_args()
 if args.action=='publish':publish()
 else:prepare(refresh=args.action=='reprepare')
