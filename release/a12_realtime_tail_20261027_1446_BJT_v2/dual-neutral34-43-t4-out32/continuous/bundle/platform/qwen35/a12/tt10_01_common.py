import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
OUT=ROOT/'evidence/model_pl_A/20261024-ttft10-01-v1'
FROZEN=ROOT/'evidence/model_pl_A/20261024-ttft10-00-v1'
WORK=Path('/home/member-a/kv260-build/a12-tt10-01-20261024-v1')
def j(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for block in iter(lambda:f.read(1048576),b''):h.update(block)
    return h.hexdigest()
def save(p,x):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def config(binary,libraries):
    corpus=j(FROZEN/'WORKLOADS.json')['real_inputs'];neutral=corpus[0]['tokens'][:70]
    return dict(schema='TT10_01_CONFIG_V1',max_slots=2,max_slot_bytes=67108864,
        allowed_prefixes=[neutral,neutral[:64],list(range(1,9)),list(range(1,10))],
        identity=dict(model_sha256=sha(ROOT/'artifacts/qwen35-0.8b/qwen35-text-Q4_K_M.gguf'),executable_sha256=sha(binary),
            model_revision='2fc06364715b967f1860aea9cf38778875588b17',runtime_base_commit='81e39ad34368329b5db77620721510fd91107e80',
            sidecar_sha256=sha(ROOT/'models/sidecar_A/qwen35-v1/manifest.json'),tensor_map_sha256=sha(ROOT/'quant/qwen35_tensor_map.json'),
            template_sha256=sha(ROOT/'artifacts/qwen35-0.8b/source/chat_template.jinja'),contract_sha256='83bd402b39350710d8689d50f79296e9625e9c75ccb0ecee145f08067c4ee3b6',
            threads=2,kernel_threads=2,physical_ubatch=8,context=1024,n_seq_max=1,n_rs_seq=0,sampler='fresh_greedy_v1',
            layout='pinned_memory_state_plus_last_logits_v1',quantization='A12_W4A8_MLP',libraries=libraries))
