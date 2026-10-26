"""Explicit S1 selection, same per-turn IPC, no per-layer Python IPC/fallback."""
from pathlib import Path
import hashlib,json
from .native import NativeCPU
from .native import ROOT
class NativeW4A8(NativeCPU):
    def __init__(self,output,*,threads=4,kernel_threads=4,thread_env=None,manifest_path=None):
        if kernel_threads not in (1,2,3,4):raise ValueError('CPU kernel thread range 1..4')
        if manifest_path not in (None,'modules/linear_A/manifest.a08.json','modules/linear_A/manifest.a09.json'):raise ValueError('Unapproved native manifest')
        if kernel_threads in (2,3) and manifest_path is None:raise ValueError('Thread 2/3 requires isolated A08 build')
        config=json.loads((ROOT/'config/qwen35/selection.json').read_text())
        if config.get('linear_backend')!='A' or config.get('fallback')!='disabled':raise RuntimeError('S1 CPU entry requires explicit default A/no-fallback selection')
        manifest=json.loads((ROOT/(manifest_path or 'modules/linear_A/manifest.json')).read_text())
        if manifest.get('execution_kind')!='CPU_REFERENCE' or manifest.get('backend_id')!='A_CPU_W4A8_V1':raise RuntimeError('Wrong S1 module')
        for filename,entry in manifest['files'].items():
            if hashlib.sha256((ROOT/filename).read_bytes()).hexdigest()!=entry['sha256']:raise RuntimeError('Runtime artifact integrity failure: '+filename)
        # Public app entry accepts no arbitrary model path or silent model switch.
        h=hashlib.sha256()
        with (ROOT/'artifacts/qwen35-0.8b/qwen35-text-Q4_K_M.gguf').open('rb') as f:
            for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
        if h.hexdigest()!='bb9fda88db8a7ee4ae8648e71d5189ed5209151a7e6a437d18999a9c33bbac1c':raise RuntimeError('Unapproved original GGUF container')
        entry=manifest['native_entry']
        if entry not in manifest['files'] or manifest.get('physical_ubatch')!=8 or manifest.get('attention_schedule')!='SIMD_QUERY_ORDER_NO_SPLIT_KV_OR_QUERY_TILING':
            raise RuntimeError('S1 physical-batch build is not sealed in module manifest')
        super().__init__(output,binary=ROOT/entry,threads=threads,extra_args=('all','TILED',kernel_threads,8),thread_env=thread_env)
        b=self.ready.get('bridge',{})
        if not (self.ready.get('quantization')=='S1_W4A8_MLP' and b.get('scope')=='all'
                and b.get('contract_sha256')=='83bd402b39350710d8689d50f79296e9625e9c75ccb0ecee145f08067c4ee3b6'
                and b.get('execution_kind')=='CPU_REFERENCE' and b.get('weight_count')==72
                and b.get('weight_load_count')==72 and self.ready.get('cache_policy')=='R0_CLEAR_ALL_REPLAY'
                and b.get('cpu_threads')==kernel_threads and b.get('cpu_algorithm')=='TILED'
                and self.ready.get('physical_ubatch')==8
                and self.ready.get('threads')==threads and self.ready.get('kernel_threads')==kernel_threads
                and self.ready.get('non_mlp_projection_schedule')=='STABLE_PER_TOKEN_SIMD_GEMV'
                and self.ready.get('attention_schedule')=='SIMD_QUERY_ORDER_NO_SPLIT_KV_OR_QUERY_TILING'):
            self.close();raise RuntimeError('S1 identity/readiness mismatch; fallback disabled')
    def generate(self,messages,timeout_s=20):
        r=super().generate(messages,timeout_s)
        if r.get('quantization')!='S1_W4A8_MLP' or not r.get('state_cleared_before_response') or r.get('state_position_after_clear')!=-1:
            self.broken=True;raise RuntimeError('S1 state/identity failure; no candidate usable')
        if r.get('bridge',{}).get('weight_load_count')!=72:
            self.broken=True;raise RuntimeError('Unexpected repeated weight loading')
        return r
