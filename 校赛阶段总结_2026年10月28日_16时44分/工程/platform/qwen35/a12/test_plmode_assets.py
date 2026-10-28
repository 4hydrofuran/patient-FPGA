"""Run the original root-owned file gate on SMALL local WSL fixtures only."""
import json
import os
from pathlib import Path
import tempfile
import types
from livegen_platform import import_original_verified
from plmode_assets import original_asset_gate

def main():
    assert os.geteuid()==0 and os.uname().machine=='x86_64' # root metadata policy; still cannot be a Board provider
    original=import_original_verified();gate=original_asset_gate(original);results=[]
    with tempfile.TemporaryDirectory(prefix='a12-root-asset-fixture-') as root:
        root=Path(root);bundle=root/'bundle';bundle.mkdir();(bundle/'evidence').mkdir();asset_root=root/'asset-root'
        model=asset_root/'artifacts/qwen35-0.8b/qwen35-text-Q4_K_M.gguf';model.parent.mkdir(parents=True);model.write_bytes(b'NOT_A_MODEL_PC_FIXTURE_ONLY\n')
        payload=bundle/'test.bin';payload.write_bytes(b'PC_ASSET_FIXTURE\n')
        manifest=dict(files=[dict(path='test.bin',bytes=payload.stat().st_size,sha256=original.sha(payload))])
        (bundle/'manifest.json').write_text(json.dumps(manifest));(bundle/'evidence/ACCEPTANCE.json').write_text(json.dumps(dict(model_sha256=original.sha(model))))
        (bundle/'evidence/RESOURCE_CALL_BUDGET.json').write_text(json.dumps(dict(profiles=[dict(scope='all',max_successful_runs=5000,weight_load_limit=72,explicit_bo_limit_bytes=140591104)])))
        owner=types.SimpleNamespace(review=dict(bundle_sha256=original.sha(bundle/'manifest.json'),scope='all',max_runs=5000,max_loads=72,explicit_bo_budget_bytes=140591104),
            owner_check=lambda:None,health=lambda:None)
        assert gate(owner,bundle,asset_root=asset_root)==model;results.append('ROOT_OWNED_EXACT_BYTES_AND_BUDGET')
        def reject(name,operation):
            try:operation()
            except (RuntimeError,ValueError,AssertionError,OSError):results.append(name);return
            raise AssertionError('asset mutation accepted: '+name)
        payload.write_bytes(b'changed');reject('CHANGED_PAYLOAD',lambda:gate(owner,bundle,asset_root=asset_root));payload.write_bytes(b'PC_ASSET_FIXTURE\n')
        owner.review['max_runs']=5001;reject('CHANGED_REVIEW_BUDGET',lambda:gate(owner,bundle,asset_root=asset_root));owner.review['max_runs']=5000
        payload.chmod(0o666);reject('ROOT_FILE_GROUP_WORLD_WRITABLE',lambda:gate(owner,bundle,asset_root=asset_root));payload.chmod(0o600)
        target=bundle/'real.bin';payload.rename(target);payload.symlink_to(target);reject('SYMLINK_PAYLOAD',lambda:gate(owner,bundle,asset_root=asset_root));payload.unlink();target.rename(payload)
        model.write_bytes(b'WRONG_MODEL_FIXTURE');reject('CHANGED_MODEL_DIGEST',lambda:gate(owner,bundle,asset_root=asset_root))
    print(json.dumps(dict(status='PASS_ORIGINAL_ROOT_ASSET_GATE_SMALL_WSL_FIXTURES',tests=results,
        actual_model_read=False,actual_Board_owner=False,actual_Board_health=False,BOARD='NOT_TESTED')))
if __name__=='__main__':main()
