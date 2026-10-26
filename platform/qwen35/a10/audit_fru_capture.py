"""PC-only strict audit of bounded, previously captured FRU bytes; never writes EEPROM.

IPMI FRU Information Storage Definition v1.0 rev1.3 sections 8, 11, 13, 16.
This audits common/board headers and the linked multirecord chain, not OEM semantics.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import re
from summarize_driver_board import output_text


def sha(data):
    return hashlib.sha256(data).hexdigest()


def parse_fru(data):
    if not 8 <= len(data) <= 8192:
        raise ValueError('FRU capture size outside bounded range')
    if data[0] != 1 or data[6] != 0 or sum(data[:8]) % 256:
        raise ValueError('Common header version/reserved/checksum invalid')
    offset = data[3] * 8
    if offset < 8 or offset + 8 > len(data):
        raise ValueError('Board info absent or truncated')
    length = data[offset+1] * 8
    end = offset + length
    if data[offset] != 1 or length < 8 or end > len(data):
        raise ValueError('Board info version/length invalid')
    if sum(data[offset:end]) % 256:
        raise ValueError('Board info checksum invalid')
    language = data[offset+2]
    fields = []
    pos = offset + 6
    terminated = False
    while pos < end - 1:
        code = data[pos]
        pos += 1
        if code == 0xC1:
            terminated = True
            break
        count = code & 63
        if pos + count > end - 1:
            raise ValueError('Field overruns board info area')
        value = data[pos:pos+count]
        fields.append({'type': code >> 6, 'raw_hex': value.hex(),
                       'text': value.decode('ascii').rstrip('\x00 ') if
                       code >> 6 == 3 and language in (0,25) and all(x<128 for x in value) else None})
        pos += count
    if not terminated or len(fields) < 5:
        raise ValueError('Board mandatory fields/terminator missing')
    identity = dict(zip(('manufacturer','product','serial','part','file_id'), fields[:5]))
    records = []
    error = None
    pos = data[5] * 8
    if pos and pos < end:
        raise ValueError('Multirecord overlaps board area')
    terminated = not bool(pos)
    while pos and len(records) < 64:
        if pos + 5 > len(data):
            error = {'offset': pos, 'reason': 'TRUNCATED_HEADER_OR_MISSING_END'}
            break
        header = data[pos:pos+5]
        stop = pos + 5 + header[2]
        row = {'offset': pos, 'header_hex': header.hex(), 'record_type': header[0],
               'data_length': header[2], 'end_of_list': bool(header[1] & 128),
               'header_checksum_ok': sum(header)%256 == 0,
               'format_ok': header[1] & 127 == 2,
               'payload_checksum_ok': ((sum(data[pos+5:stop])+header[3])%256 == 0) if stop<=len(data) else None}
        records.append(row)
        if not row['header_checksum_ok'] or not row['format_ok']:
            error = {'offset': pos, 'reason': 'INVALID_HEADER', 'raw_hex': header.hex()}
            break
        if stop > len(data) or not row['payload_checksum_ok']:
            error = {'offset': pos, 'reason': 'TRUNCATED_OR_BAD_PAYLOAD'}
            break
        if row['end_of_list']:
            terminated = True
            break
        pos = stop
    if not terminated and error is None:
        error = {'offset':pos, 'reason':'RECORD_COUNT_LIMIT'}
    return {'common_header_checksum_ok': True, 'board_area_checksum_ok': True,
            'board_area_offset':offset, 'board_area_bytes':length, 'identity':identity,
            'custom_fields':fields[5:], 'multirecord_records':records,
            'multirecord_chain_valid': terminated and error is None,
            'multirecord_error':error, 'eeprom_entire_contents_verified':False,
            'scope':'Captured common/board identity and linked chain; OEM payload semantics not verified'}


def audit(capture):
    if capture.get('exit_code') != 0 or capture.get('closed') is not True:
        raise ValueError('Successful closed capture required')
    text = output_text(capture)
    rows = [json.loads(line) for line in text.splitlines() if line.startswith('{')]
    expected = {'/sys/bus/i2c/devices/1-0050/eeprom', '/sys/bus/i2c/devices/1-0051/eeprom'}
    if len(rows)!=2 or {r['path'] for r in rows} != expected:
        raise ValueError('Exact two EEPROM captures required')
    results = []
    for row in rows:
        data = base64.b64decode(row['base64'], validate=True)
        if row['bytes'] != 1024 or len(data) != row['bytes'] or sha(data) != row['sha256']:
            raise ValueError('Captured bytes/hash mismatch')
        results.append({'path':row['path'], 'bytes':len(data), 'sha256':sha(data), **parse_fru(data)})
    kernel = re.search(r'(?m)^([0-9a-f]{40})  /boot/vmlinuz-6\.8\.0-1015-xilinx$', text)
    if not kernel:
        raise ValueError('Kernel digest not observed')
    return {'schema':'A10_FRU_PC_AUDIT_V1', 'domain':'PC_ANALYSIS_OF_REAL_CAPTURE',
            'status':'IDENTITY_AREAS_VALID_MULTIRECORD_FAILURE_RETAINED' if any(not r['multirecord_chain_valid'] for r in results) else 'CAPTURED_AREAS_VALID',
            'records':results, 'installed_kernel_sha1':kernel[1],
            'board_modified':False, 'A10':'NOT_PASSED'}


if __name__ == '__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('capture',type=Path)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    raw=args.capture.read_bytes()
    result=audit(json.loads(raw.decode('utf-8-sig')))
    result['source']={'path':str(args.capture),'sha256':sha(raw)}
    with args.output.open('x',encoding='utf-8') as out:
        json.dump(result,out,indent=2,ensure_ascii=False)
        out.write('\n')
    print(json.dumps({'status':result['status'],'A10':result['A10'],
          'boards':[dict(product=r['identity']['product']['text'], serial=r['identity']['serial']['text'],error=r['multirecord_error']) for r in result['records']]}))
