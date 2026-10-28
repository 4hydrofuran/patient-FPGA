"""Seal the tested candidate and stage it over the existing UART/IP link, without activation."""
import argparse
from datetime import datetime,timezone,timedelta
import hashlib
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
import json
from pathlib import Path
import zipfile
from fast_response_prepare_support import verify_package

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

RECEIVER=r'''
import hashlib,json,os,sys,time,urllib.request,zipfile
from pathlib import Path
result=dict(scope='UPLOAD_ONLY_NO_ACTIVATION',machine_sha256=PLAN['machine_sha256'],boot_id=PLAN['boot_id'],compute_runs=0,pl_loads=0,reboots=0,status='PENDING')
target=Path(PLAN['remote_directory'])
try:
    assert os.geteuid()==0 and hashlib.sha256(Path('/etc/machine-id').read_bytes()).hexdigest()==PLAN['machine_sha256']
    assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==PLAN['boot_id'] and os.uname().release=='6.8.0-1036-xilinx'
    assert not Path('/var/lock/kv260-a1/active').exists() and not Path('/sys/module/zocl').exists()
    assert Path('/sys/kernel/config/device-tree/overlays/k26-starter-kits_image_1/status').read_text().strip()=='applied'
    assert not target.exists();target.mkdir(mode=0o755)
    archive=target/PLAN['archive'];digest=hashlib.sha256();received=0
    with urllib.request.urlopen(PLAN['url'],timeout=15) as response,archive.open('xb') as output:
        deadline=time.monotonic()+60
        while True:
            block=response.read(65536)
            if not block:break
            assert time.monotonic()<deadline and received+len(block)<=PLAN['bytes']
            output.write(block);digest.update(block);received+=len(block)
    assert received==PLAN['bytes'] and digest.hexdigest()==PLAN['sha256']
    with zipfile.ZipFile(archive) as package:package.extractall(target)
    candidate=target/PLAN['candidate'];metadata=json.loads((candidate/'MANIFEST.json').read_text())
    assert metadata['status']=='UNBOUND' and metadata['authorization_included'] is False
    for row in metadata['files']:
        p=candidate/row['path'];assert p.stat().st_size==row['bytes'] and hashlib.sha256(p.read_bytes()).hexdigest()==row['sha256'],row['path']
    result.update(status='UPLOADED_HASH_VERIFIED_NOT_ACTIVATED',archive_sha256=digest.hexdigest(),bytes=received,files=len(metadata['files']),candidate=str(candidate))
except Exception as e:result.update(status='FAILED_PRESERVE_PARTIAL_STATE',error=type(e).__name__+': '+str(e))
finally:
    if target.is_dir():(target/'STAGING_STATUS.json').write_text(json.dumps(result,indent=2)+'\n')
    print('__TT10_UART_ROOT_SCENE_BEGIN__',flush=True);print(json.dumps(result),flush=True);print('__TT10_UART_ROOT_SCENE_END__',flush=True)
'''


def prepare(a):
    parent=a.parent.resolve();verify_package(parent)
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    now=datetime.now(timezone(timedelta(hours=8)));tag=now.strftime('%Y%m%d_%H%M')+f'_BJT_v{a.revision}'
    name='KV260_Qwen35_A12_B601e69ca_RealtimeWeb_BoardPrep_'+tag+'.zip'
    archive=out/name
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(parent.rglob('*')):
            if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc':z.write(p,parent.name+'/'+p.relative_to(parent).as_posix())
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None
    plan=dict(archive=name,bytes=archive.stat().st_size,sha256=sha(archive),candidate=parent.name,
        prepared_at=now.isoformat(),version=tag,url='http://192.168.2.1:18891/'+name,
        remote_directory='/home/ubuntu/kv260-staging/a12-b601e69ca-rt-'+now.strftime('%Y%m%d-%H%M')+f'-v{a.revision}',
        machine_sha256='ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec',
        boot_id='624d896f-3a30-4c85-990c-1970373d2d28',execute_compute=False)
    save(out/'STAGE_PLAN.json',plan)
    (out/'receiver.py').write_text('PLAN='+repr(plan)+'\n'+RECEIVER,encoding='utf-8')
    print(json.dumps(plan,indent=2))


def serve(a):
    out=a.output.resolve();plan=json.loads((out/'STAGE_PLAN.json').read_text(encoding='utf-8'))
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(out),**kwargs)
        def do_GET(self):
            if self.path!='/'+plan['archive']:self.send_error(404);return
            super().do_GET()
    server=ThreadingHTTPServer(('192.168.2.1',18891),Handler);server.timeout=.25
    print('READY_PRIVATE_STAGE_ARCHIVE_ONLY',flush=True)
    try:
        while not (out/'HTTP_STOP.json').exists():server.handle_request()
    finally:server.server_close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=('prepare','serve'))
    p.add_argument('--parent',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--revision',type=int,default=1);a=p.parse_args()
    prepare(a) if a.action=='prepare' else serve(a)
