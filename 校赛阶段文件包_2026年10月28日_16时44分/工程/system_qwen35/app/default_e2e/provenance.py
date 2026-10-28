"""Small immutable provenance references; weights are verified by their loaders, not per turn."""
import hashlib,json
from .policy import ROOT

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def capture(profile,registry,prompt_style,native_manifest):
    config={'profile':profile,'registry':registry,'prompt_style':prompt_style,'native_manifest':native_manifest}
    names=[native_manifest,'models/model.lock.json','models/sidecar_A/qwen35-v1/manifest.json',
           'modules/voice_A/resources.lock.json','modules/voice_A/manifest.json','contracts/qwen35/contracts.lock']
    lock=json.loads((ROOT/'models/model.lock.json').read_text(encoding='utf-8'))
    return {'run_config_sha256':hashlib.sha256(json.dumps(config,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
            'model_revision':lock['revision'],'runtime_commit':lock['runtime_commit'],
            'identity_files_sha256':{n:sha(ROOT/n) for n in names},
            'scope':'Configuration/lock identities. Native and voice loaders validate resources at startup; no per-token weight hashing.'}
