"""Read ARM64 module ELF on PC without loading it; check every imported symbol CRC."""
import argparse
import hashlib
import json
from pathlib import Path
import struct


def sections(data):
    if data[:6] != b'\x7fELF\x02\x01' or struct.unpack_from('<H', data, 18)[0] != 183:
        raise ValueError('Expected little-endian ARM64 ELF64')
    offset = struct.unpack_from('<Q', data, 40)[0]
    size, count, strings = struct.unpack_from('<HHH', data, 58)
    if size != 64 or strings >= count or offset + size*count > len(data):
        raise ValueError('Invalid ELF section table')
    rows = [struct.unpack_from('<IIQQQQIIQQ', data, offset+i*size) for i in range(count)]
    string_row = rows[strings]
    names = data[string_row[4]:string_row[4]+string_row[5]]
    result = {}
    for row in rows:
        name = names[row[0]:].split(b'\0', 1)[0].decode('ascii')
        if row[1] != 8 and row[4]+row[5] > len(data):
            raise ValueError('Section outside ELF')
        result[name] = data[row[4]:row[4]+row[5]]
    return result


def compare_versions(raw, symvers):
    expected = {line.split()[1]: int(line.split()[0], 16)
                for line in symvers.splitlines() if line.strip()}
    # Exact Ubuntu 6.8.0-1015.16 module.h/modpost.c format:
    # packed u32 next, u32 crc, NUL name padded to 4, NULL entry, C-string NUL.
    # Not upstream's older fixed 64-byte format. Never autodetect/fall back.
    if len(raw) < 21:
        raise ValueError('Invalid Ubuntu modversion records')
    checks = []
    i = 0
    while i + 8 <= len(raw):
        width, crc = struct.unpack_from('<II', raw, i)
        if width == 0:
            if raw[i:] != b'\0'*9 or not checks:
                raise ValueError('Invalid Ubuntu modversion terminator')
            return checks
        if width < 12 or width % 4 or i + width > len(raw):
            raise ValueError('Invalid Ubuntu modversion next offset')
        name_bytes = raw[i+8:i+width]
        name, separator, padding = name_bytes.partition(b'\0')
        if not name or not separator or any(padding):
            raise ValueError('Invalid symbol name/padding')
        symbol = name.decode('ascii')
        if symbol not in expected or expected[symbol] != crc:
            raise ValueError('Missing/mismatched kernel symbol CRC: ' + symbol)
        checks.append({'symbol': symbol, 'crc': hex(crc)})
        i += width
    raise ValueError('Missing Ubuntu modversion terminator')


def audit(module, symvers):
    data = module.read_bytes()
    sec = sections(data)
    checks = compare_versions(sec['__versions'], symvers.read_text())
    info = sec['.modinfo'].decode().split('\0')
    magic = next(s for s in info if s.startswith('vermagic='))
    if magic != 'vermagic=6.8.0-1015-xilinx SMP preempt mod_unload modversions aarch64':
        raise ValueError('Unexpected vermagic: ' + magic)
    if 'version=2.18.0' not in info:
        raise ValueError('Unexpected driver version')
    return {'status': 'PASS_PC_ELF_AND_SYMBOL_CRCS_NOT_BOARD', 'sha256': hashlib.sha256(data).hexdigest(),
            'bytes': len(data), 'vermagic': magic, 'symbol_crc_count': len(checks), 'symbols': checks,
            'modversion_layout': 'Ubuntu 6.8.0-1015.16 packed next/crc/name; explicit format',
            'board_load': 'NOT_TESTED', 'signed_for_board': False}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('module', type=Path)
    p.add_argument('symvers', type=Path)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    result = audit(a.module, a.symvers)
    with a.output.open('x') as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps({k: v for k, v in result.items() if k != 'symbols'}))
