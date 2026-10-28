"""Reconstruct a proc-device-tree snapshot into a NEW PC directory for dtc -I fs."""
import base64
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys
from profile_from_uart import body


def reconstruct(capture_path, destination):
    raw = capture_path.read_bytes()
    capture = json.loads(raw.decode('utf-8-sig'))
    if capture.get('status') != 'COLLECTED_REVIEW_REQUIRED' or capture.get('closed') is not True:
        raise ValueError('Capture incomplete')
    props = json.loads(body(next(r for r in capture['records'] if r['name'] == 'dt_snapshot')))
    decoded = {}
    for name, value in props.items():
        path = PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts or '\\' in name or not name or ':' in name:
            raise ValueError('Unsafe property path')
        decoded[name] = base64.b64decode(value, validate=True)
    destination.mkdir(parents=False, exist_ok=False)
    for name, value in decoded.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(value)
    return {'domain': 'PC_RECONSTRUCTION_FROM_BOARD_READONLY', 'capture_sha256': hashlib.sha256(raw).hexdigest(),
            'properties': len(decoded), 'property_bytes': sum(map(len, decoded.values())),
            'directory': str(destination), 'not_original_fdt_binary': True,
            'board_dt_write': 'NOT_PERFORMED'}


if __name__ == '__main__':
    print(json.dumps(reconstruct(Path(sys.argv[1]), Path(sys.argv[2]))))
