"""One approved linkage-only ELF transfer. Derives the tested UART receiver;
no execution, root writes, library replacement, or old staging-directory reuse.
"""
import base64
import gzip
import hashlib
import json
from pathlib import Path
import sys

EXPECTED='d25040172f0bb67b04e2e85233a2ae4a27e85cc6314de4beb9994b60d4f0243d'
SIZE=277392
BOOT='d07af077-84c9-4910-8529-95757a09106d'
TARGET='/home/ubuntu/a10-linkage-check-20261018-v1'
SOURCE=Path(__file__).with_name('driver_serial_payload.py')


def receiver_source():
    source=SOURCE.read_text(encoding='utf-8')
    changes={
        "EXPECTED = '545df42c8b66396dd847ccd6a280f19d9a0051d36e2e75c1ec84437caca328a9'":"EXPECTED = '%s'"%EXPECTED,
        'SIZE = 464752':'SIZE = 277392',
        "TARGET = Path('/home/ubuntu/a10-driver-check-20261018-v2')":"TARGET = Path('%s')"%TARGET,
        'deadline = time.monotonic() + 90':'deadline = time.monotonic() + 30',
        '    import termios':"    import termios\n    if Path('/proc/sys/kernel/random/boot_id').read_text().strip() != '%s':\n        raise ValueError('boot changed')"%BOOT,
    }
    for old,new in changes.items():
        if source.count(old)!=1:raise ValueError('Receiver base changed; review required')
        source=source.replace(old,new)
    source=source.replace('zocl.ko','a10-vadd-short')
    return source.encode()


def prepare(path):
    data=Path(path).read_bytes()
    if len(data)!=SIZE or hashlib.sha256(data).hexdigest()!=EXPECTED:
        raise ValueError('Wrong approved ELF')
    payload=gzip.compress(data,mtime=0)
    if len(payload)>200000:raise ValueError('Transfer exceeds short budget')
    chunks=[payload[i:i+768] for i in range(0,len(payload),768)]
    source=receiver_source()
    encoded=base64.b64encode(gzip.compress(source,mtime=0)).decode()
    expression="import base64,gzip; ns={'__name__':'receiver'}; exec(gzip.decompress(base64.b64decode('%s')),ns); ns['receive'](%d)"%(encoded,len(chunks))
    command='python3 -c "'+expression+'"'
    if len(command)>3500:raise ValueError('Receiver exceeds terminal line budget')
    return dict(command=command,sha256=EXPECTED,bytes=SIZE,compressed_bytes=len(payload),
                receiver_sha256=hashlib.sha256(source).hexdigest(),target=TARGET,
                base_receiver_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                boot_id=BOOT,execution='NOT_PERFORMED',
                chunks=[dict(line=str(i)+':'+base64.b64encode(b).decode(),
                             ack='A10DRV_ACK:%d:%s'%(i,hashlib.sha256(b).hexdigest())) for i,b in enumerate(chunks)])


if __name__=='__main__':
    if len(sys.argv)!=3 or sys.argv[1]!='--prepare':raise SystemExit('PC preparation only')
    print(json.dumps(prepare(sys.argv[2])))
