PLAN={'archive': 'case20-debug-t4.zip', 'bytes': 33073781, 'sha256': '8a0341e1a80361a75880a7bab887868f6fe22aba16bfd396570ed8407a64f8c0', 'url': 'http://192.168.2.1:18894/case20-debug-t4.zip', 'board_source': '/home/ubuntu/kv260-staging/a12-case20-debug-20261027-v1/case20-debug-t4', 'kernel': '6.8.12-a10irq2', 'boot_id': '98886b24-96d3-409e-a783-ce9c54873da9'}
import hashlib,json,os,subprocess,urllib.request,zipfile
from pathlib import Path
r=dict(status='PENDING',board_mutations=['STAGE_NEW_DIRECTORY'],pl_loads=0)
try:
 assert hashlib.sha256(Path('/etc/machine-id').read_bytes()).hexdigest()=='ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec'
 assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==PLAN['boot_id'] and os.uname().release==PLAN['kernel']
 interfaces=json.loads(subprocess.run(['ip','-j','-4','addr','show','dev','eth0'],capture_output=True,text=True,check=True).stdout)
 addresses={(x['local'],x['prefixlen']) for x in interfaces[0]['addr_info']}
 assert ('192.168.137.2',24) in addresses
 if ('192.168.2.2',24) not in addresses:
  subprocess.run(['ip','addr','add','192.168.2.2/24','dev','eth0'],check=True)
  r['temporary_address_added']='192.168.2.2/24'
 target=Path(PLAN['board_source']).parent
 assert not target.exists();target.mkdir(parents=True)
 archive=target/PLAN['archive'];h=hashlib.sha256();total=0
 opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
 with opener.open(PLAN['url'],timeout=15) as response,archive.open('xb') as f:
  while True:
   b=response.read(262144)
   if not b:break
   h.update(b);f.write(b);total+=len(b)
 assert total==PLAN['bytes'] and h.hexdigest()==PLAN['sha256']
 with zipfile.ZipFile(archive) as z:z.extractall(target)
 candidate=Path(PLAN['board_source']);m=json.loads((candidate/'MANIFEST.json').read_text())
 for row in m['files']:
  f=candidate/row['path'];assert f.stat().st_size==row['bytes'] and hashlib.sha256(f.read_bytes()).hexdigest()==row['sha256'],row['path']
 r.update(status='CASE20_RANDOM_STAGED_NOT_STARTED',files=len(m['files']),path=str(candidate),sha256=h.hexdigest(),bytes=total)
 (target/'STAGED.json').write_text(json.dumps(r,indent=2)+'\n')
except Exception as e:r.update(status='FAILED_PRESERVE_PARTIAL_STATE',error=type(e).__name__+': '+str(e))
print('__TT10_UART_ROOT_SCENE_BEGIN__',flush=True);print(json.dumps(r),flush=True);print('__TT10_UART_ROOT_SCENE_END__',flush=True)
