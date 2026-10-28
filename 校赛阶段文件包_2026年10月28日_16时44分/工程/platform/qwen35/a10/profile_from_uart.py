"""Derive an observation-only profile from bounded UART captures; no device I/O."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import re


def body(record):
    text = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', record['raw']).replace('\r', '')
    match = re.search(r'^A10_([0-9a-f]{32})_BEGIN\n(.*?)^A10_\1_END:(\d+)\s*$',
                      text, re.M | re.S)
    if not record.get('completion_marker') or not match:
        raise ValueError('Missing or mismatched completion marker')
    if int(match[3]) != record.get('exit_code'):
        raise ValueError('Exit code does not match raw capture')
    return match[2]


def match_or_none(pattern, text):
    match = re.search(pattern, text, re.M)
    return match[1] if match else None


def memory_ranges(encoded, address_cells, size_cells):
    if encoded is None or address_cells is None or size_cells is None:
        return None
    if address_cells not in (1, 2) or size_cells not in (1, 2):
        raise ValueError('Unsupported DT cell count')
    raw = base64.b64decode(encoded, validate=True)
    width = 4 * (address_cells + size_cells)
    if not raw or len(raw) % width:
        raise ValueError('Malformed DT reg length')
    return [{'address_hex': hex(int.from_bytes(raw[i:i+4*address_cells], 'big')),
             'size_bytes': int.from_bytes(raw[i+4*address_cells:i+width], 'big')}
            for i in range(0, len(raw), width)]


def build(paths):
    records, sources = {}, []
    for path in paths:
        raw = path.read_bytes()
        doc = json.loads(raw.decode('utf-8-sig'))
        if doc.get('schema') != 'A10_UART_READONLY_V1' or doc.get('domain') != 'BOARD_READONLY':
            raise ValueError('Wrong capture schema/domain')
        if doc.get('status') != 'COLLECTED_REVIEW_REQUIRED' or doc.get('closed') is not True:
            raise ValueError('Incomplete collection or unreleased port')
        sources.append({'path': path.name, 'sha256': hashlib.sha256(raw).hexdigest(), 'utc': doc['utc']})
        for record in doc['records']:
            if record['name'] in records:
                raise ValueError('Duplicate observation group; select an explicit snapshot')
            records[record['name']] = body(record)
    identity, health = records.get('identity', ''), records.get('health', '')
    driver, kernel = records.get('driver', ''), records.get('kernel_build', '')
    sensors, network = records.get('sensors', ''), records.get('network', '')
    mem = {k: (int(v) if (v := match_or_none(r'^'+k+r':\s+(\d+) kB', health)) else None)
           for k in ('MemTotal', 'MemAvailable', 'CmaTotal', 'CmaFree')}
    temperatures = [{'path': path, 'celsius': int(value)/1000}
                    for path, value in re.findall(r'^(/sys/class/hwmon/hwmon\d+/temp\d+_input): (\d+)$', sensors, re.M)]
    properties = dict(re.findall(r'^(/proc/device-tree/\S+) BASE64=(\S+)$',
                                records.get('dt_memory', '') + records.get('dt_cells', ''), re.M))
    def cell(name):
        value = properties.get('/proc/device-tree/'+name)
        if value is None:
            return None
        raw = base64.b64decode(value, validate=True)
        if len(raw) != 4:
            raise ValueError('Malformed DT cell property')
        return int.from_bytes(raw, 'big')
    ranges = {p: memory_ranges(v, cell('#address-cells'), cell('#size-cells'))
              for p, v in properties.items() if re.fullmatch(r'/proc/device-tree/memory[^/]*/reg', p)}
    return {
        'schema': 'A10_OBSERVED_BOARD_PROFILE_V1', 'sources': sources,
        'status': 'PARTIAL_READONLY_NOT_A10_PASS',
        'os': match_or_none(r'^PRETTY_NAME="([^"]+)"', identity),
        'kernel': match_or_none(r'^Linux \S+ (\S+)', identity),
        'architecture': 'aarch64' if re.search(r'^Linux .*\baarch64\b', identity, re.M) else None,
        'dt_model': match_or_none(r'^(ZynqMP KV260[^\n]*)$', identity),
        'fru_identity_verified': False,
        'cpu_features': match_or_none(r'^Features\s*:\s*(.+)', health),
        'cpu_part': match_or_none(r'^CPU part\s*:\s*(.+)', health),
        'memory_kib': mem, 'memory_accounting': 'CMA is a subset/reservation, never add it to MemTotal, PSS or BO totals',
        'dt_memory_ranges': ranges, 'dt_properties_base64': properties,
        'bo_address_reachability': None, 'bo_budget_bytes': None, 'envelope_3200_mib_validated': False,
        'temperatures': temperatures,
        'xrt_package': match_or_none(r'^xrt\s+(\S+)', driver),
        'zocl': 'MODULE_NOT_FOUND' if 'modinfo: ERROR: Module zocl not found.' in driver else 'UNKNOWN',
        'card0_driver': match_or_none(r'^(/sys/bus/platform/drivers/\S+)', driver),
        'kernel_files_sha256': {p: h for h, p in re.findall(r'^([0-9a-f]{64})\s+(/\S+)$', kernel, re.M)},
        'eth0_addresses': match_or_none(r'^eth0\s+\S+\s+(.+)', network),
        'board_compute': 'NOT_TESTED', 'arm_program_smoke': 'NOT_TESTED',
        'board_vadd_comparisons': 0, 'recovery_test': 'NOT_TESTED',
        'warnings': ['Subshell exit 0 is not proof every command passed; inspect retained raw errors.',
                     'DT memory ranges do not establish PL/BO reachability.',
                     'No driver install, PL load, stress test, reboot or firmware write performed.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('captures', nargs='+', type=Path)
    args = parser.parse_args()
    profile = build(args.captures)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(profile, stream, indent=2, ensure_ascii=False)
        stream.write('\n')
    print(json.dumps({'status': profile['status'], 'output': str(args.output)}))
