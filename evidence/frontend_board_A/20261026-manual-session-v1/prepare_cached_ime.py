import hashlib
from pathlib import Path
out=Path(__file__).parent
data=(out/'ime-packages.zip').read_bytes();(out/'collect.py').write_bytes(data)
p=out/'install_cached_ime.py'
p.write_text(p.read_text().replace('PACKAGE_SHA',repr(hashlib.sha256(data).hexdigest())))
(out/'ime-progress-v4.py').write_text((out/'ime_progress.py').read_text().replace('manual-web-20261026-v3','manual-web-20261026-v4'))
