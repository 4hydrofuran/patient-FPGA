"""Review exact compiled bytes and reversible source edits; no ARM execution."""
import ast
import hashlib
from pathlib import Path
import subprocess
import zipfile
from plmode_evidence import ROOT,OUT,PARENT,read,save,sha,pin
import plmode_manager as manager
from plmode_journal import JOURNAL_EDITS
from plmode_runtime import machine

def exports(path):
    r=subprocess.run(['nm','-D','--defined-only',str(path)],capture_output=True,text=True,check=True)
    return sorted(line.split()[-1] for line in r.stdout.splitlines())

def reverse(text,edits):
    for old,new in reversed(edits):
        assert text.count(new)==1;text=text.replace(new,old)
    return text

def main():
    b=read(OUT/'BUILD-v2.json');board=read(OUT/'BOARD_BUILD-v2-complete.json');source=read(OUT/'SOURCE-v2.json');work=Path(b['workspace'])
    required={'ROOT_ASSET_TEST.json':'PASS','OWNER_INTERFACE_TEST.json':'PASS','POLICY_TEST-v1.json':'PASS',
        'CANCELLATION_TEST.json':'PASS','LATE_CLOSE_CANCEL_TEST.json':'PASS','OBSERVER_TEST.json':'PASS',
        'INIT_CLEANUP_COUNTEREXAMPLE.json':'PASS','RELOCATION_TEST.json':'PASS'}
    for name,prefix in required.items():assert read(OUT/name)['status'].startswith(prefix),name
    assert read(OUT/'POLICY_TEST-v1.json')['count']==22 and read(OUT/'RELOCATION_TEST.json')['count']==5
    for tag in ('normal04','fallback04'):assert read(OUT/tag/'AUDIT.json')['status']=='PASS_RAW_MODEL_AND_MODE_HISTORY'
    assert read(OUT/'fsync01/RESULT.json')['status']=='PASS_PC_MODE_SCENARIO'
    for row in source['source']:assert sha(work/'arm-source'/row['name'])==row['sha256']
    restored=reverse((work/'arm-source/backend.cpp').read_text(),source['backend_reversible_edits'])
    assert hashlib.sha256(restored.encode()).hexdigest()==source['original_backend_sha256']
    assert len(source['backend_reversible_edits'])==3
    assert '#ifndef SP_LINEAR_CONTROL_TEST\n    // This candidate cannot be activated' in restored
    assert (work/'arm-source/plmode_observer.cpp').read_bytes()==(ROOT/'platform/qwen35/a12/plmode_observer.cpp').read_bytes()
    # Independently reverse the final Python derivations, including the later
    # close-handshake milestone absent from the earlier build-time snapshot.
    constructor=reverse(manager.constructor,manager.CTOR_EDITS)
    tree=ast.parse(manager.frozen.text);cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Manager')
    import textwrap
    node=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='__init__')
    assert constructor==textwrap.dedent('\n'.join(manager.frozen.text.splitlines()[node.lineno-1:node.end_lineno]))
    original=ROOT/'platform/qwen35/a12/modelpl_manager.py'
    assert reverse(manager.request,manager.REQUEST_EDITS)==manager.method(original,'ModelManager','run_request')
    assert reverse(manager.close_text,manager.CLOSE_EDITS)==manager.method(original,'ModelManager','normal_close')
    assert reverse(manager.page_text,manager.PAGE_EDITS)==(ROOT/'platform/qwen35/a12/plm_page.py').read_text()
    save(OUT/'FINAL_DERIVATION.json',dict(constructor_edits=manager.CTOR_EDITS,request_edits=manager.REQUEST_EDITS,
        page_edits=manager.PAGE_EDITS,close_edits=manager.CLOSE_EDITS,journal_edits=JOURNAL_EDITS,
        backend_reversible_edits=source['backend_reversible_edits'],all_reversible_checks_passed=True,
        current_sources=[pin(p) for p in sorted((ROOT/'platform/qwen35/a12').iterdir()) if p.is_file() and p.name.startswith(('plmode_','test_plmode_'))]))
    rows=b['runtime_artifacts']+b['manager_artifacts']+b['ARM_artifacts']+board['runtime_artifacts']+board['auxiliary_artifacts']
    rows += [dict(path=b['observer_library'],sha256=b['observer_sha256'])]
    for row in rows:assert sha(row['path'])==row['sha256'],row['path']
    assert sha(b['imported_quant_object']['path'])==b['imported_quant_object']['sha256']
    parent=read(PARENT/'BUILD-v2.json');assert b['runtime_artifacts']==parent['runtime_artifacts']
    assert b['math_libraries_before_and_after']==parent['math_libraries_before_and_after']
    for row in b['math_libraries_before_and_after']:assert sha(row['path'])==row['sha256']
    old_arm=read(ROOT/'evidence/model_pl_A/20261026-generation-binding-v1/ARM_RESULT-v3.json')['artifact']
    original_exports=exports(old_arm['path']);compiled=[]
    for row in b['ARM_artifacts']:
        assert machine(row['path'])==183;symbols=exports(row['path'])
        assert symbols==(['a12_plm_observe_fd_v1'] if 'observer' in row['path'] else original_exports)
        assert not any('test_' in s or 'control_test' in s for s in symbols)
        compiled.append(dict(artifact=row,exports=symbols))
    assert machine(b['observer_library'])==62 and exports(b['observer_library'])==['a12_plm_observe_fd_v1']
    for row in read(OUT/'BASELINE.json')['files']:assert sha(ROOT/row['path'])==row['sha256']
    assert sha(ROOT/'contracts/qwen35/sp_linear_v1.h')=='d97e544444b8566a32d0bd25e67e2e548f71678ac6e63ac63e96aa415b1a76f9'
    probe=ROOT/'evidence/model_pl_A/20261025-resource-probe-v1/bundle-v2.zip'
    assert sha(probe)=='acd578ddd66140a3d0507d71ea9a1d30245c632c7537f0a940227935cc17a7fa'
    unique={r['path']:dict(path=r['path'],sha256=r['sha256']) for r in rows}
    save(OUT/'ARTIFACT_REVIEW.json',dict(status='PASS_PREPARED_PL_MODE_OFFLINE_ONLY',artifacts=list(unique.values()),compiled_exports=compiled,
        math_recompiled=False,quantization_recompiled=False,public_ABI_unchanged=True,backend_gate_edits=3,
        default_backend='UNBOUND_UNSUPPORTED',candidate_backend='SEPARATE_A53_BUILD_REQUIRES_ACTUAL_OWNER_AND_LIVE_SOURCE',
        candidate_executed=False,BOARD='NOT_TESTED',actual_PL_results_consumed=False,production_enabled=False,SERVICE_ready=False,
        final_model_trials=['normal04','fallback04'],model_fixture_math='ACTUAL_CPU_ONLY',
        prior_model_trials='DEVELOPMENT_EVIDENCE_RETAINED_NOT_INDEPENDENT_BOARD_SAMPLES'))
    files={}
    for p in sorted((ROOT/'platform/qwen35/a12').iterdir()):
        if p.is_file() and p.name.startswith(('plmode_','test_plmode_')):files['source/'+p.name]=p.read_bytes()
    for name in ('BUILD-v2.json','BOARD_BUILD-v2-complete.json','FINAL_DERIVATION.json','ARTIFACT_REVIEW.json',*required):
        files['review/'+name]=(OUT/name).read_bytes()
    for tag in ('normal04','fallback04'):
        files['review/'+tag+'-AUDIT.json']=(OUT/tag/'AUDIT.json').read_bytes()
    for row in b['ARM_artifacts']:files['arm/'+Path(row['path']).name]=Path(row['path']).read_bytes()
    files['pc/libplmode_observer.so']=Path(b['observer_library']).read_bytes()
    files['README.txt']=('OFFLINE REVIEW ONLY. NOT STANDALONE OR AUTHORIZED FOR DEPLOYMENT.\n'
        'Requires the frozen repository, original native/math/model assets and a separately reviewed fixed-root layout.\n'
        'No Board lease/source/provider was instantiated; no ARM artifact was executed.\n'
        'The unbound backend refuses device_open. The separate bound candidate requires the original root ARM64 Owner, live gates and both inherited locks.\n'
        'Coordinator stays in that owning parent process. Board failure retains quarantine; recovery is external, followed by an explicit new-input strict window.\n'
        'The three-request window is not an unlimited SERVICE. PC model/count evidence is not FPGA evidence.\n'
        'First later Board baseline remains the unchanged ordinary resource bundle, after separate recovery, safe release and fresh authorization.\n'
        'No model, weights, sidecars, bitstream, install/recovery or Board execution scripts are included.\n').encode()
    archive=OUT/'pl-mode-offline-review-v1.zip'
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for name,data in files.items():z.writestr(name,data)
    members=[dict(name=n,bytes=len(v),sha256=hashlib.sha256(v).hexdigest()) for n,v in sorted(files.items())]
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None and set(z.namelist())==set(files)
        for r in members:assert hashlib.sha256(z.read(r['name'])).hexdigest()==r['sha256']
    save(OUT/'PACKAGE_REVIEW.json',dict(status='PASS_ALL_REVIEW_PACKAGE_BYTES',archive=pin(archive),members=members,standalone=False,deployable=False))
    print('PASS_PREPARED_PL_MODE_OFFLINE_ONLY',len(unique),'artifacts',len(files),'package members')
if __name__=='__main__':main()
