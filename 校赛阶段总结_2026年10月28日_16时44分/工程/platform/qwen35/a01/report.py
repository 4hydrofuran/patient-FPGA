"""Summarize observed logs only, keep PC and BOARD separate."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'eval/qwen35/a01'
EV=ROOT/'platform/qwen35/a01/evidence'


def read(path):return json.loads(path.read_text(encoding='utf-8'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    metrics={}
    for key in ('f16','q4'):
        baseline=read(OUT/(key+'-v1')/'summary.json')
        probe=read(OUT/(key+'-decode-v1')/'summary.json')
        assert baseline['status']=='PASS' and probe['status']=='PASS'
        metrics[key]={'baseline_ready':baseline['ready'],
            'contexts':[{k:r[k] for k in ['id','prompt_tokens','prefill_ms','ttft_ms','decode_ms','decode_calls','peak_rss_kib']} for r in baseline['results'] if r['id'].startswith('context-')],
            'short_answer':probe,'functional_failures':baseline['failures'],
            'cancellation':[r for r in baseline['results'] if r['id']=='cancel']}
    commands=[]
    for p in sorted(EV.glob('*.json')):
        if p.name=='report.json':continue
        entry=read(p)
        if 'argv' in entry:
            commands.append({'log':p.relative_to(ROOT).as_posix(),'argv':entry['argv'],'exit_code':entry['exit_code']})
    assert read(EV/'model-audit-final.json')['exit_code']==0
    assert read(EV/'converted-check.json')['exit_code']==0
    assert read(EV/'audit-tests.json')['exit_code']==0
    report={'role':'A','stage':'A01','status':'PASS_PC_TEXT_BASELINE_AND_ARCHITECTURE','date':'2026-10-02',
      'branch':subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip(),
      'base_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'new_commit':None,
      'requested_assistant':'GPT-6 Astra / High / Standard','actual_assistant':'unknown; no settings changed',
      'model_lock':'models/model.lock.json','tensor_map':'quant/qwen35_tensor_map.json','native_entry':'runtime/qwen35_cpu/entrypoint.json',
      'architecture':{'layers':24,'hidden':1024,'mlp':3584,'linear_attention':18,'full_attention':6,'mlp_mappings':72,'tied_embedding_head':True,'source_tensors':{'text':320,'vision':153,'mtp':15},'text_gguf_tensors':320},
      'domains':{'PC':'PASS','Csim':'NOT_TESTED','Cosim':'NOT_TESTED','synthesis':'NOT_TESTED','implementation':'NOT_TESTED','cross_build':'NOT_TESTED','BOARD':'NOT_TESTED','medical_quality':'NOT_TESTED','power':'NOT_TESTED'},
      'metrics':metrics,'commands':commands,
      'failures_preserved':[
       {'log':'fetch-weight.json','cause':'HTTP ended 13,795,760 bytes early','repair':'Exact 206 Content-Range tail recovery plus official LFS SHA256; original partial retained'},
       {'log':'model-audit.json','cause':'Substring v. falsely matched text attn_v.weight','repair':'Exact vision namespace prefix; regression added'},
       {'log':'model-audit-retry.json','cause':'Visual MLP bias included in text no-bias assertion','repair':'Restrict assertion to model.language_model.layers; retain visual tensors in inventory; regression added'}],
      'warnings':[
       'Converter Transformers 4.57.6 does not recognize qwen3_5 AutoConfig; upstream converter explicitly reads actual config.json and uses its own registered Qwen3_5 implementation. Warning preserved, no global upgrade.',
       'Converter reused read-only existing Python env: torch2.13.0+cpu/numpy2.5.1 rather than upstream requirements torch2.11.0/numpy2.2.x; actual successful conversion and versions logged; no environment mutation.',
       'Runtime archive lacks .git; build banner alone does not identify commit. Fixed codeload commit and source archive SHA are in model.lock.',
       'Native build has nonfatal misleading-indentation warning; full compiler logs retained.',
       'F16 is a converted high-precision reference, not independent Transformers forward verification; Q4_K_M is NOT custom W4A8.',
       'Each performance sample is a small PC test, no confidence interval/p95 claim; synthetic context padding and greedy decoding disclosed.',
       'Model load uses mmap and existing filesystem cache; not cold disk latency. ru_maxrss is cumulative process high-water, not summed workspace estimates.',
       'Some metadata/hash audit ran during baseline preparation; these timings are descriptive, not a controlled optimization comparison.',
       'Every generated token ID retained; template closes empty think before generation, no output filtering to conceal reasoning.',
       'Full memory clear and prompt replay used per request; not optimized incremental session caching.',
       'No GPU used; no board execution; no licenses/credentials copied into public deliverables.'],
      'unresolved':['Official KV260 boot chain and DT/CMA match','Actual Linux/PL BO memory budget','A-vadd timeout quarantine before board','A02 medical teacher review','A03 voice licenses and implementation','W4A8 and PL full-model integration in later stages'],
      'next':'A02 case constraints, scoring and frozen test set; B/C candidate absence not blocking'}
    with (OUT/'A01_REPORT.json').open('x',encoding='utf-8') as f:json.dump(report,f,ensure_ascii=False,indent=2)
    files=[]
    for directory in ['platform/qwen35/a01','runtime/qwen35_cpu','eval/qwen35/a01']:
        files.extend(p for p in (ROOT/directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name not in {'report.json','files.sha256.json'})
    files += [ROOT/p for p in ['models/model.lock.json','quant/qwen35_tensor_map.json','docs/PROJECT_STATUS.json','config/qwen35/selection.json','scripts/release/ownership.json']]
    hashes={p.relative_to(ROOT).as_posix():sha(p) for p in sorted(set(files))}
    with (OUT/'files.sha256.json').open('x') as f:json.dump(hashes,f,indent=2)
    print(json.dumps({'status':report['status'],'files':len(hashes),'report_sha256':sha(OUT/'A01_REPORT.json'),'manifest_sha256':sha(OUT/'files.sha256.json')}))


if __name__=='__main__':main()
