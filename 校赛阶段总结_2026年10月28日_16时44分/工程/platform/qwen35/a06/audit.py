"""Static evidence audit; missing artifacts never acquire PASS by title."""
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[3]
B=ROOT/'hw/linear_B_received/B03-fdd1d656290b-20261003'
E=ROOT/'evidence/A06_acceptance'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def save(p,value):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,ensure_ascii=False)
def verify_relative(base,files):
    result=[]
    for name,claim in files.items():
        p=base/Path(name.replace('\\','/'))
        if not p.resolve().is_relative_to(base.resolve()):raise ValueError('unsafe claimed path')
        actual=digest(p) if p.is_file() else None
        expected=claim['sha256'] if isinstance(claim,dict) else claim
        result.append({'path':name,'expected_sha256':expected.lower(),'actual_sha256':actual,
                       'status':'MISSING' if actual is None else 'MATCH' if actual==expected.lower() else 'MISMATCH'})
    return result
def main():
    download=read(E/'intake-v1/download-manifest.json')
    checks=verify_relative(B,{v['path']:v for v in download['files']})
    if any(v['status']!='MATCH' for v in checks):raise RuntimeError('intake changed')
    tree=read(E/'intake-v1/remote-tree.json')
    allpaths=[v['path'] for v in tree['tree'] if v['type']=='blob']
    claims=read(B/'reports/b03/artifact_guard.json')
    variants={}
    for name in ('baseline','reuse','double'):
        source='baseline/b02/src/w4a8_linear_v1.cpp' if name=='baseline' else 'src/w4a8_prefill_v1.cpp'
        header='baseline/b02/src/w4a8_linear_v1.hpp' if name=='baseline' else 'src/w4a8_linear_v1.hpp'
        v=claims['variants'][name]
        receipt=read(B/v['synthesis_receipt'])
        records=[]
        for r in sorted((B/f'evidence/b03/verification/{name}').glob('*.receipt.json')):
            body=read(r)
            records.append({'receipt':str(r.relative_to(B)),'exit_code':body['exit_code'],
                            'input_checks':verify_relative(B,body.get('input_sha256',{}))})
        variants[name]={'source':source,'source_sha256':digest(B/source),
                        'source_matches_claim':digest(B/source)==v['source_sha256'],
                        'header':header,'header_sha256':digest(B/header),
                        'header_matches_claim':digest(B/header)==v['header_sha256'],
                        'config':f'hls_prefill_{name}.cfg','config_sha256':digest(B/f'hls_prefill_{name}.cfg'),
                        'claimed_xo_sha256':v['xo_sha256'],'actual_xo_sha256':None,
                        'claimed_metadata_sha256':v['kernel_xml_sha256'],
                        'XO':'MISSING_FROM_REMOTE_TREE_AND_RELEASES',
                        'synthesis_receipt':v['synthesis_receipt'],'synthesis_exit':receipt['exit_code'],
                        'synthesis_input_checks':verify_relative(B,receipt['input_sha256']),
                        'verification_receipts':records}
    groups={}
    for p in sorted((B/'evidence/b03/batches/baseline').glob('*/manifest.json')):
        body=read(p);files=verify_relative(p.parent,body['files'])
        groups[p.parent.name]={'provider_status':body['status'],'transactions':body['transactions'],
                               'cases':body['cases'],'file_checks':files,
                               'A_replay':'BLOCKED_MISSING_RAW_TV_DATA',
                               'missing':sum(x['status']=='MISSING' for x in files),
                               'mismatch':sum(x['status']=='MISMATCH' for x in files)}
    xmlpath=B/'evidence/b03/batches/baseline/gate_t1/kernel.xml'
    kernel=ET.parse(xmlpath).getroot().find('kernel')
    header=(B/variants['baseline']['header']).read_text(encoding='utf-8')
    args=re.search(r'extern "C" void w4a8_linear_v1\((.*?)\);',header,re.S).group(1).split(',')
    typed=[]
    for xml,arg in zip(kernel.find('args'),args):
        t,n=arg.strip().rsplit(' ',1)
        if n!=xml.attrib['name']:raise RuntimeError('argument order mismatch')
        typed.append(dict(xml.attrib,header_type=t))
    assert len(args)==len(typed)==17
    mapping={'status':'PROVISIONAL_HEADER_AND_LOOSE_XML_ONLY_XO_NOT_RECEIVED','provider':'B',
             'source_commit':download['source_commit'],'kernel':kernel.attrib,
             'metadata_path':str(xmlpath.relative_to(ROOT)),'metadata_sha256':digest(xmlpath),
             'metadata_matches_baseline_claim':digest(xmlpath)==variants['baseline']['claimed_metadata_sha256'],
             'ports':[p.attrib for p in kernel.find('ports')],'arguments':typed,
             'meta':{'bytes':40,'fields':[
                 {'name':n,'offset':o,'bytes':s} for n,o,s in
                 [('abi_magic',0,4),('kernel_build_id',4,4),('job_id',8,8),('status',16,4),
                  ('done',20,4),('hw_completed_count',24,8),('algorithm_weight_bytes',32,8)]],
                 'magic':'0x57344138','abi_version':1,
                 'build_ids':{'baseline':'0xB3020002','reuse':'0xB3030001','double':'0xB3030002'},
                 'counter_semantics':'Reads prior counter from supplied meta, increments on success; not an independent free-running hardware counter',
                 'algorithm_weight_bytes':'Np*Kp/2, W4 only; excludes Sw, pre-scan, repeated reads'},
             'minimum_lengths':{'w':'Np*Kp/2','sw':'Np*G*4','xq':'T*Kp','sx':'T*4','y':'T*Np*4','meta':40},
             'target_shapes':[{'N':n,'K':k,'T':[1,8],'w_bytes':1835008,'sw_bytes':114688,
                               'x_bytes_T1_T8':[k,8*k],'sx_bytes_T1_T8':[4,32],
                               'y_bytes_T1_T8':[n*4,n*32]} for n,k in [(3584,1024),(1024,3584)]],
             'private_errors':{'0':'OK','1':'BAD_ABI','2':'BAD_DIMENSION','3':'BAD_BUFFER_LENGTH','4':'NULL_POINTER','5':'INVALID_W4_CODE'},
             'host_must_check':['job_id != 0','checked length arithmetic and actual BO capacity',
                                'A8 != -128','finite positive Sw/Sx','W/X zero padding and Sw padding=1',
                                'meta completion/magic/version/build/job/status before consuming Y',
                                'finite Y after sync; private kernel does not reject restore overflow'],
             'deployment':{'status':'DEPLOYMENT_PENDING_BOARD','CMA':None,'max_verified_bo_bytes':None,
                           'resident_budget_bytes':None,'BO_bank_mapping':None},
             'A07_owner':'A: XRT BO/sync/kernel/meta/poisoned recovery; B: kernel correction and missing artifacts',
             'not_a_link_or_deployment_authorization':True}
    save(E/'interface-map.candidate.json',mapping)
    public={p: digest(B/'contracts'/p)==digest(ROOT/'contracts/qwen35'/p) for p in ['quant_v1.json','sp_linear_v1.h']}
    audit={'status':'NOT_ACCEPTED_MISSING_DELIVERY','provider':'B','remote_commit':download['source_commit'],
           'intake_files_verified':len(checks),'public_contract_byte_match':public,'variants':variants,
           'baseline_cosim_groups':groups,'remote_xo_files':[p for p in allpaths if p.endswith('.xo')],
           'releases':read(E/'intake-v1/releases.json'),
           'scope':'No download of whole repository; no board, no remote writes, no new kernel',
           'BOARD':'NOT_TESTED','implementation':'NOT_TESTED','hardware_error':None}
    save(E/'static-audit.json',audit)
    print(json.dumps({'intake_files_verified':len(checks),'public_contract_byte_match':public,
                      'variants_source_match':{k:v['source_matches_claim'] for k,v in variants.items()},
                      'cosim_manifest_missing':{k:v['missing'] for k,v in groups.items()},
                      'cosim_manifest_mismatches':{k:v['mismatch'] for k,v in groups.items()},
                      'status':audit['status']}))
if __name__=='__main__':main()
