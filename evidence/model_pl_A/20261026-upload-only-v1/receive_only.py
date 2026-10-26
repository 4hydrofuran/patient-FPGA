import json,os,urllib.request
from pathlib import Path
assert os.uname().release=='6.8.0-1036-xilinx'
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()=='a009c890-e320-408d-9334-bd43bfa52807'
directory=Path('/home/ubuntu/a12-resident-incoming-20261026-v1');directory.mkdir(mode=0o700)
name='a12-resident-board-candidate-20261026-v1.tar.gz'
target=directory/name
received=0
with target.open('xb') as output:
    with urllib.request.urlopen('http://192.168.2.1:8765/'+name,timeout=20) as response:
        while True:
            b=response.read(65536)
            if not b:break
            output.write(b);received+=len(b)
print('__A12_UPLOAD_BEGIN__',flush=True)
print(json.dumps(dict(status='TRANSFER_STREAM_COMPLETED_NOT_UNPACKED_OR_EXECUTED',path=str(target),received_bytes=received)),flush=True)
print('__A12_UPLOAD_END__',flush=True)
