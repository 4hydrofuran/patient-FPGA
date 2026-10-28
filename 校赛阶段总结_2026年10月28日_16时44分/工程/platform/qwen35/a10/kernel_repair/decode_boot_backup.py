"""Decode a bounded UART boot-script readback on PC; never execute its contents."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import struct
import zlib


def decode_record(record):
    if record.get('kind') != 'BOOT_SCRIPT_BACKUP':
        raise ValueError('wrong kind')
    if type(record.get('bytes')) is not int or not 72 <= record['bytes'] <= 16384:
        raise ValueError('size outside bound')
    if len(record['base64']) > 22000:
        raise ValueError('encoded size outside bound')
    blob = base64.b64decode(record['base64'], validate=True)
    if len(blob) != record['bytes'] or hashlib.sha256(blob).hexdigest() != record['sha256']:
        raise ValueError('length/SHA mismatch')
    magic, hcrc, stamp, size, load, entry, dcrc, os_id, arch, kind, comp, name = struct.unpack('>7I4B32s', blob[:64])
    if magic != 0x27051956 or kind != 6 or comp != 0:
        raise ValueError('not an uncompressed legacy U-Boot script')
    hdr = blob[:4] + bytes(4) + blob[8:64]
    payload = blob[64:]
    if zlib.crc32(hdr) != hcrc or size != len(payload) or zlib.crc32(payload) != dcrc:
        raise ValueError('uImage header/data CRC or size mismatch')
    length, terminator = struct.unpack('>2I', payload[:8])
    if terminator != 0 or length != len(payload) - 8:
        raise ValueError('not a single complete script')
    script = payload[8:].decode('utf-8')
    return blob, script


def recover(receipt, output):
    r = json.loads(receipt.read_text(encoding='utf-8-sig'))
    if r.get('exit_code') != 0 or r.get('closed') is not True or r.get('step') != 'boot_recovery_readonly':
        raise ValueError('readback not completed/closed')
    rows = [json.loads(line) for line in r['raw'].replace('\r', '').splitlines()
            if line.startswith('{"kind": "BOOT_SCRIPT_BACKUP"')]
    if len(rows) != 1:
        raise ValueError('missing/ambiguous backup record')
    blob, script = decode_record(rows[0])
    output.mkdir(parents=True, exist_ok=False)
    with (output / 'boot.scr.uimg').open('xb') as f:
        f.write(blob)
    with (output / 'boot-script.READ_ONLY.txt').open('x', encoding='utf-8', newline='\n') as f:
        f.write(script)
    summary = dict(status='BOOT_SCRIPT_BACKUP_SHA_AND_CRC_VERIFIED_NOT_FULL_ROLLBACK',
                   source_receipt_sha256=hashlib.sha256(receipt.read_bytes()).hexdigest(),
                   bytes=len(blob), sha256=hashlib.sha256(blob).hexdigest(),
                   script_executed=False, board_changed=False, full_fit_backed_up=False)
    with (output / 'manifest.json').open('x', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)
    return summary


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--receipt', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(recover(a.receipt, a.output)))
