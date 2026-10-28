"""Reuse frozen A02 dev cases/assertions with explicit real S1 constructor."""
import argparse,importlib.util,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from system_qwen35.app.native_w4a8 import NativeW4A8
ap=argparse.ArgumentParser();ap.add_argument('--output',required=True);a=ap.parse_args()
spec=importlib.util.spec_from_file_location('a02_actual_dev',ROOT/'platform/qwen35/a02/run_model.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
# Dependency injection selects the actual native backend, not a fake response.
m.NativeCPU=NativeW4A8
sys.argv=[str(ROOT/'platform/qwen35/a02/run_model.py'),'--output',str(ROOT/a.output),'--dev','eval/qwen35/a02/dev/questions-v2.json']
rc=m.main()
summary=json.loads((ROOT/a.output/'summary.json').read_text())
summary.update(quantization='S1_ORIGINAL_W4A8_MLP_OTHER_TENSORS_Q4_K_M',entry_adapter='system_qwen35/app/native_w4a8.py',model_source_hash=summary.pop('model_hash'),sidecar_manifest_sha256='cdb2a04dbd95d426ea8967cda0adb219a769d3630107a2af72d6ddf2d5285688',note='Actual S1 worker was injected into unchanged frozen A02 dev runner. Original runner summary labels its historical Q4-only identity; this separate identity-corrected report is authoritative for this run. No final heldout read.')
with (ROOT/a.output/'S1-summary.json').open('x') as f:json.dump(summary,f,ensure_ascii=False,indent=2)
raise SystemExit(rc)
