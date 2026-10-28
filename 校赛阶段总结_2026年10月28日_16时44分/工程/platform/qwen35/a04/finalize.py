"""Check preservation, identities and real receipts; seal A04 without board calls."""
import hashlib,json,os,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'eval/qwen35/a04'
UPDATED=['docs/PROJECT_STATUS.json','docs/status/A.md','docs/DESIGN_GAP.md',
         'docs/TEST_MATRIX.md','docs/DECISIONS.md','docs/AI_ASSISTANCE.md']
def read(p):return json.loads((ROOT/p).read_text(encoding='utf-8'))
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()
def main():
    prior=read('eval/qwen35/a03/closeout-v1/files.sha256.json');changed=[]
    for rel,digest in prior.items():
        if rel in UPDATED:
            assert sha(OUT/'before'/rel)==digest,('before changed',rel)
            changed.append(rel)
        else:assert sha(ROOT/rel)==digest,('historical evidence changed',rel)
    assert set(changed)==set(UPDATED)
    report=read('eval/qwen35/a04/REPORT.v2.json');status=read('docs/PROJECT_STATUS.json')
    assert report['status']==status['stage_status'] and status['stage']=='A04'
    assert report['integer_bit_exact'] and report['fp32_bit_exact'] and report['real_projection_count']==48
    assert report['payload_bytes']==140378112 and report['S1_to_S2_error'] is None
    assert report['domains']['BOARD']=='NOT_TESTED' and status['pl_bo_budget_bytes'] is None
    for rel in ('quant/export_w4a8','quant/reference','platform/qwen35/a04'):
        for p in (ROOT/rel).glob('*.py'):compile(p.read_text(),str(p),'exec')
    for folder in ('qwen35-v1','qwen35-repro-v1'):
        base=ROOT/'models/sidecar_A'/folder;m=json.loads((base/'manifest.json').read_text())
        assert sha(base/'manifest.json')==report['manifest_sha256']
        for p,h in m['producer'].items():assert sha(ROOT/p)==h,('producer drift',p)
        assert len(m['entries'])==72
        for e in m['entries']:
            for entry in e['files'].values():
                p=base/entry['file'];assert p.stat().st_size==entry['bytes'] and sha(p)==entry['sha256']
    for name,digest in report['binaries'].items():
        assert sha(Path('/home/member-a/qwen35-a04/build-v1')/name)==digest
    for p,h in read('eval/qwen35/design_import/build/identity.json')['files'].items():assert sha(Path(p))==h
    commands=[]
    for p in sorted((ROOT/'platform/qwen35/a04/evidence').glob('*.json')):
        if p.name=='finalize.json':continue  # Own outer receipt completes after this seal.
        v=json.loads(p.read_text());assert v['exit_code'] is not None,('still running',p)
        expected=1 if p.name=='vectors-v1.json' else 0
        assert v['exit_code']==expected,('unexpected command exit',p,v['exit_code'])
        commands.append({'path':p.relative_to(ROOT).as_posix(),'exit_code':v['exit_code'],'argv':v['argv']})
    branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    assert branch==status['branch'] and commit==status['base_commit']
    with (OUT/'git-after.txt').open('x') as f:subprocess.run(['git','status','--short'],cwd=ROOT,stdout=f,check=True)
    audit={'status':'PASS_A04_FINAL_AUDIT','prior_seal_entries':len(prior),
           'intentional_document_changes_with_before':changed,'all_other_prior_files_unchanged':True,
           'current_report':'eval/qwen35/a04/REPORT.v2.json','branch':branch,'head':commit,'new_commit':None,
           'commands':commands,'BOARD':'NOT_TESTED','hardware_error':None,
           'unsealed_outer_receipt':'platform/qwen35/a04/evidence/finalize.json'}
    with (OUT/'FINAL_AUDIT.json').open('x') as f:json.dump(audit,f,indent=2)
    files=set(ROOT/p for p in UPDATED+['docs/handoffs/A_A04_20261002.md','models/model.lock.json','quant/qwen35_tensor_map.json'])
    links=[]
    for rel in ('quant/export_w4a8','quant/reference','platform/qwen35/a04','eval/qwen35/a04','models/sidecar_A/qwen35-v1','models/sidecar_A/qwen35-repro-v1'):
        for directory,dirs,names in os.walk(ROOT/rel,followlinks=False):
            dirs[:]=[d for d in dirs if d!='__pycache__']
            for name in names:
                p=Path(directory)/name
                if p.is_symlink():
                    links.append({'path':p.relative_to(ROOT).as_posix(),'target':os.readlink(p),'scope':'negative loader fixture, not followed'})
                elif p.suffix!='.pyc' and p.name not in ('files.sha256.json','files.sha256','finalize.json'):files.add(p)
    with (OUT/'negative-fixture-links.json').open('x') as f:json.dump(links,f,indent=2)
    files.add(OUT/'negative-fixture-links.json')
    seal={p.relative_to(ROOT).as_posix():sha(p) for p in sorted(files)}
    with (OUT/'files.sha256.json').open('x') as f:json.dump(seal,f,indent=2)
    digest=sha(OUT/'files.sha256.json')
    with (OUT/'files.sha256').open('x') as f:f.write(digest+'  files.sha256.json\n')
    print(json.dumps({'status':'PASS_A04_FINAL_AUDIT','sealed_files':len(seal),'sha256':digest,
                      'historical_preservation':len(prior),'BOARD':'NOT_TESTED'}))
if __name__=='__main__':main()
