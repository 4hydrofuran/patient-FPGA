"""Inspect leading newc archives without extracting or executing backup contents."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat

PIN = 'cdfd3b01230944d912f66475b38283bfdb576f516cbb38fd0da4077354b48a94'


def newc(raw, start=0):
    position, entries = start, []
    while True:
        header = raw[position:position+110]
        if len(header) != 110 or header[:6] != b'070701':
            raise ValueError('Expected complete newc header')
        fields = [int(header[i:i+8], 16) for i in range(6, 110, 8)]
        inode, mode, uid, gid, links, mtime, size, devmajor, devminor, rmajor, rminor, namesize, check = fields
        if not 1 <= namesize <= 4096 or check != 0:
            raise ValueError('Invalid newc name/check')
        begin = position + 110
        name_bytes = raw[begin:begin+namesize]
        if len(name_bytes) != namesize or name_bytes[-1:] != b'\0' or b'\0' in name_bytes[:-1]:
            raise ValueError('Invalid newc name bytes')
        name = name_bytes[:-1].decode('utf-8')
        if not name or name.startswith('/') or '..' in PurePosixPath(name).parts:
            raise ValueError('Unsafe archive path')
        data_start = (begin + namesize + 3) & ~3
        end = data_start + size
        if end > len(raw):
            raise ValueError('Truncated newc entry')
        entry_start = position
        position = (end + 3) & ~3
        if name == 'TRAILER!!!':
            if size:
                raise ValueError('Nonempty trailer')
            return entries, position
        entries.append({'path': name, 'mode': mode, 'bytes': size, 'links': links,
                        'data_start': data_start, 'data_end': end,
                        'entry_start': entry_start, 'entry_end': position})


def inspect(raw):
    if hashlib.sha256(raw).hexdigest() != PIN:
        raise ValueError('Backup digest mismatch')
    offset, archives = 0, []
    while raw[offset:offset+6] == b'070701':
        entries, end = newc(raw, offset)
        archives.append({'start': offset, 'end': end, 'entries': entries})
        offset = end
        while offset < len(raw) and raw[offset] == 0:
            offset += 1
    return {'status': 'PC_ARCHIVE_LAYOUT_ONLY', 'archives': archives,
            'tail_offset': offset, 'tail_bytes': len(raw)-offset,
            'tail_magic_hex': raw[offset:offset+16].hex()}


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('input', type=Path)
    p.add_argument('--output', required=True, type=Path)
    args = p.parse_args()
    result = inspect(args.input.read_bytes())
    with args.output.open('x') as f:
        json.dump(result, f, indent=2)
    print(json.dumps({k:v for k,v in result.items() if k != 'archives'}))
    for a in result['archives']:
        files = [e for e in a['entries'] if stat.S_ISREG(e['mode'])]
        print(json.dumps({'start':a['start'], 'end':a['end'], 'entries':len(a['entries']),
                          'regular_files':len(files), 'first_regular':files[:2],
                          'last_regular':files[-2:]}))
