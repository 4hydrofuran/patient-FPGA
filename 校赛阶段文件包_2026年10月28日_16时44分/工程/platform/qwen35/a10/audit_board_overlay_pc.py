"""Check DT reconstruction properties and reuse existing A1 static overlay audit."""
import base64
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
from profile_from_uart import body
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'a1'))
from audit_overlay_files import inspect_pair


capture_path, base, merged, output = map(Path, sys.argv[1:])
capture = json.loads(capture_path.read_text(encoding='utf-8-sig'))
props = json.loads(body(capture['records'][0]))
checked, derived_names = 0, 0
for name, encoded in props.items():
    p = PurePosixPath(name)
    # proc-device-tree synthesizes name from node names; dtc elides redundant name.
    if p.name == 'name':
        derived_names += 1
        continue
    node = '/' if str(p.parent) == '.' else '/'+str(p.parent)
    result = subprocess.run(['fdtget', '-t', 'bx', str(base), node, p.name],
                            check=True, capture_output=True, text=True)
    actual = bytes(int(word, 16) for word in result.stdout.split())
    if actual != base64.b64decode(encoded, validate=True):
        raise ValueError('Reconstruction mismatch: '+name)
    checked += 1
report = inspect_pair(base, merged)
report.update(domain='PC_STATIC_NOT_BOARD_DEPLOYMENT', reconstructed_property_bytes_verified=checked,
              proc_synthetic_name_properties=derived_names, board_load='NOT_TESTED', deployment_authorized=False)
with output.open('x') as stream:
    json.dump(report, stream, indent=2)
print(json.dumps(report))
