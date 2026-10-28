"""Summarize a real read-only binding capture without contacting the board."""
import base64
import hashlib
import json
from pathlib import Path
import sys
from profile_from_uart import body


def summarize(path):
    data = path.read_bytes()
    capture = json.loads(data.decode('utf-8-sig'))
    if not capture['closed'] or capture['status'] != 'COLLECTED_REVIEW_REQUIRED':
        raise ValueError('Incomplete/unreleased capture')
    record = next(r for r in capture['records'] if r['name'] == 'dt_binding')
    tree = json.loads(body(record))
    if tree['count'] != len(tree['nodes']):
        raise ValueError('Node count mismatch')
    nodes = []
    for node in tree['nodes']:
        prop = node['properties']
        compatible = base64.b64decode(prop['compatible'], validate=True).rstrip(b'\0').decode().split('\0')
        if any('zocl' in s or s == 'fpga-region' for s in compatible):
            nodes.append({'path': node['path'], 'compatible': compatible,
                          'firmware_name': base64.b64decode(prop.get('firmware-name', ''), validate=True).rstrip(b'\0').decode() or None})
    zocl_nodes = [n for n in nodes if any(s in ('xlnx,zocl', 'xlnx,zoclsvm', 'xlnx,zocl-ert', 'xlnx,zocl-versal') for s in n['compatible'])]
    return {'domain': 'BOARD_READONLY_DERIVED', 'capture_sha256': hashlib.sha256(data).hexdigest(),
            'capture': path.name, 'compatible_nodes_checked': tree['count'], 'relevant_nodes': nodes,
            'zocl_platform_nodes': zocl_nodes,
            'status': 'NO_ZOCL_DT_BINDING' if not zocl_nodes else 'BINDING_REQUIRES_REVIEW',
            'driver_install_alone_sufficient': False if not zocl_nodes else None,
            'overlay_load': 'NOT_PERFORMED', 'board_compute': 'NOT_TESTED'}


if __name__ == '__main__':
    result = summarize(Path(sys.argv[1]))
    with Path(sys.argv[2]).open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps(result))
