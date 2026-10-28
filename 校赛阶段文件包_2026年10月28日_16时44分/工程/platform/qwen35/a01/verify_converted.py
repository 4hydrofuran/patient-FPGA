"""Check both real GGUF inventories/template against fixed original files."""
import json
from audit_model import ROOT, SRC, sha, gguf

lock=json.loads((ROOT/'models/model.lock.json').read_text())
template=(SRC/'chat_template.jinja').read_text(encoding='utf-8')
seen=None;result={}
for name,entry in lock['converted_files'].items():
    path=ROOT/'artifacts/qwen35-0.8b'/name
    assert sha(path)==entry['sha256']
    r=gguf.GGUFReader(str(path))
    inventory={t.name:t.shape.tolist() for t in r.tensors}
    if seen is None:seen=inventory
    else:assert inventory==seen
    assert r.fields['general.architecture'].contents()=='qwen35'
    assert r.fields['qwen35.block_count'].contents()==24
    assert r.fields['tokenizer.chat_template'].contents()==template
    result[name]={'tensor_count':len(inventory),'template_exact_match':True,'block_count':24,'sha256':entry['sha256']}
print(json.dumps({'domain':'PC','files':result,'status':'PASS','board':'NOT_TESTED'}))
