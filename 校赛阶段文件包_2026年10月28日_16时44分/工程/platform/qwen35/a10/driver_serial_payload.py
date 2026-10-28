"""PC preparation and bounded board receiver for ONE hash-locked ZOCL file.

No driver execution, networking, package install, deletion or device writes.
Board receiver uses the existing empty, user-owned staging directory only.
"""
import base64
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import select
import stat
import sys
import time

EXPECTED = '545df42c8b66396dd847ccd6a280f19d9a0051d36e2e75c1ec84437caca328a9'
SIZE = 464752
MAX_COMPRESSED = 524288
TARGET = Path('/home/ubuntu/a10-driver-check-20261018-v2')


def decode_chunk(line, sequence):
    if len(line) > 1100:
        raise ValueError('chunk line too long')
    number, encoded = line.strip().split(':', 1)
    if int(number) != sequence:
        raise ValueError('out of order')
    data = base64.b64decode(encoded, validate=True)
    if not 1 <= len(data) <= 768:
        raise ValueError('chunk size')
    return data


def unpack(data, digest=EXPECTED, size=SIZE):
    if not 0 < len(data) <= MAX_COMPRESSED:
        raise ValueError('compressed size')
    with gzip.GzipFile(fileobj=io.BytesIO(data)) as stream:
        result = stream.read(size + 1)
    if len(result) != size or hashlib.sha256(result).hexdigest() != digest:
        raise ValueError('payload length or SHA256 mismatch')
    return result


def publish(directory, data):
    # No overwrite and no rename race. A failed write remains as failure evidence.
    with (directory / 'zocl.ko').open('xb') as output:
        output.write(data)
    if hashlib.sha256((directory / 'zocl.ko').read_bytes()).hexdigest() != EXPECTED:
        raise ValueError('readback hash mismatch')


def receive(count):
    import termios
    if platform.machine() != 'aarch64' or platform.release() != '6.8.0-1015-xilinx':
        raise ValueError('wrong target')
    if os.getuid() != 1000 or not sys.stdin.isatty() or not 1 <= count <= 683:
        raise ValueError('wrong user, terminal or count')
    temps = [int(p.read_text()) for p in Path('/sys/class/hwmon').glob('hwmon*/temp*_input')]
    if not temps or not all(0 < t < 60000 for t in temps):
        raise ValueError('temperature gate')
    TARGET.mkdir(mode=0o700)
    info = TARGET.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise ValueError('unsafe staging directory')
    if list(TARGET.iterdir()):
        raise ValueError('staging directory is not empty')
    os.umask(0o077)
    old = termios.tcgetattr(0)
    new = list(old)
    new[3] &= ~termios.ECHO
    deadline = time.monotonic() + 90
    try:
        termios.tcsetattr(0, termios.TCSANOW, new)
        print('A10DRV_READY', flush=True)
        with (TARGET / 'zocl.ko.gz.part').open('xb') as compressed:
            total = 0
            for sequence in range(count):
                remaining = min(8, deadline - time.monotonic())
                if remaining <= 0 or not select.select([0], [], [], remaining)[0]:
                    raise TimeoutError('transfer deadline; no automatic retry')
                chunk = decode_chunk(sys.stdin.readline(1101), sequence)
                total += len(chunk)
                if total > MAX_COMPRESSED:
                    raise ValueError('transfer size limit')
                compressed.write(chunk)
                print('A10DRV_ACK:%d:%s' % (sequence, hashlib.sha256(chunk).hexdigest()), flush=True)
        data = unpack((TARGET / 'zocl.ko.gz.part').read_bytes())
        publish(TARGET, data)
        print('A10DRV_DONE:' + EXPECTED, flush=True)
    finally:
        termios.tcsetattr(0, termios.TCSANOW, old)


def prepare(filename):
    data = Path(filename).read_bytes()
    if len(data) != SIZE or hashlib.sha256(data).hexdigest() != EXPECTED:
        raise ValueError('wrong source')
    compressed = gzip.compress(data, mtime=0)
    if len(compressed) > MAX_COMPRESSED:
        raise ValueError('compressed payload cap')
    chunks = [compressed[i:i+768] for i in range(0, len(compressed), 768)]
    source = Path(__file__).read_bytes()
    script = base64.b64encode(gzip.compress(source, mtime=0)).decode('ascii')
    # Exec uses an isolated namespace so __main__ dispatch is not re-entered.
    expression = "import base64,gzip; ns={'__name__':'receiver'}; exec(gzip.decompress(base64.b64decode('%s')),ns); ns['receive'](%d)" % (script, len(chunks))
    command = 'python3 -c "' + expression + '"'
    if len(command) > 3500:
        raise ValueError('receiver command exceeds terminal budget')
    return {'command': command, 'sha256': EXPECTED, 'bytes': SIZE,
            'compressed_bytes': len(compressed), 'receiver_sha256': hashlib.sha256(source).hexdigest(),
            'chunks': [{'line': str(i) + ':' + base64.b64encode(chunk).decode('ascii'),
                        'ack': 'A10DRV_ACK:%d:%s' % (i, hashlib.sha256(chunk).hexdigest())}
                       for i, chunk in enumerate(chunks)]}


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--prepare':
        print(json.dumps(prepare(sys.argv[2])))
    else:
        raise SystemExit('PC preparation only; board receiver is explicit')
