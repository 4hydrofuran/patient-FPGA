"""Record actual isolated dependency/API metadata without printing license bodies."""
import hashlib
import importlib.metadata as md
import inspect
import json
import platform
import sys
from pathlib import Path
import sherpa_onnx

ROOT=Path(__file__).resolve().parents[1]
data=dict(python=sys.version, executable=sys.executable, platform=platform.platform(),
    machine=platform.machine(), packages=[],
    ctc_factory_signature=str(inspect.signature(sherpa_onnx.OnlineRecognizer.from_zipformer2_ctc)),
    hotwords_parameter_supported=False, decoder_bias='NONE',
    ctc_factory_source_sha256=hashlib.sha256(inspect.getsource(sherpa_onnx.OnlineRecognizer.from_zipformer2_ctc).encode()).hexdigest(),
    onnx_license_status='REVIEW_PENDING', user_license_answer='暂无补充，先保留待确认')
for name in ['sherpa-onnx','sherpa-onnx-core','numpy']:
    dist=md.distribution(name)
    metadata_path=next(p for p in dist.files if str(p).endswith('.dist-info/METADATA'))
    data['packages'].append(dict(name=name,version=dist.version,requires=dist.requires,
        declared_license=dist.metadata.get('License-Expression') or dist.metadata.get('License'),
        metadata_sha256=hashlib.sha256(Path(dist.locate_file(metadata_path)).read_bytes()).hexdigest()))
(ROOT/'evidence/c01/runtime.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
wheels=json.loads((ROOT/'assets/wheels/wheels.lock.json').read_text())
names={'numpy':'numpy','sherpa_onnx':'sherpa-onnx','sherpa_onnx_core':'sherpa-onnx-core'}
lines=['# Offline Windows cp312 x64 wheels; use --no-index --find-links assets/wheels --require-hashes']
for row in wheels:
    name,version=Path(row['path']).name.split('-')[:2]
    lines.append(f"{names[name]}=={version} --hash=sha256:{row['sha256']}")
(ROOT/'requirements-c01.lock.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print('Audited isolated runtime and pinned dependencies')
