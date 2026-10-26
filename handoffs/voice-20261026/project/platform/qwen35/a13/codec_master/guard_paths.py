"""约束官方BD派生工程的全部生成路径在当前独立尝试内。"""
import json
from pathlib import Path
import re
import sys

work = Path.cwd().resolve()
assert re.fullmatch(r'C:/Patientqwen/local/a13c_b[0-9][0-9]', work.as_posix())
bd = Path(sys.argv[1]).resolve()
assert bd.is_relative_to(work)
design = json.loads(bd.read_text(encoding='utf-8'))['design']
generated = (bd.parent / design['design_info']['gen_directory']).resolve()
assert generated.is_relative_to(work)
for cell in design['components'].values():
    if cell.get('xci_path'):
        assert (generated / cell['xci_path']).resolve().is_relative_to(work)
print(json.dumps({'BD': str(bd), 'generated': str(generated), 'paths_within_attempt': True}))
