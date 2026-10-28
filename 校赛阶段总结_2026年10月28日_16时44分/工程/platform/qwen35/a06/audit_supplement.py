"""A static acceptance of received bytes, provenance and actual XO metadata."""
import hashlib,json,re,sys,zipfile
from pathlib import Path
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[3]
B=ROOT/'hw/linear_B_received/B03-supplement-e227297-20261003/payload'
E=ROOT/'evidence/A06_acceptance/supplement-v1'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    package=read(B/'B03_package_manifest.json')
    for name,v in package['files'].items():
        p=B/name
        assert p.resolve().is_relative_to(B.resolve())
        assert p.stat().st_size==v['bytes'] and sha(p)==v['sha256'],name
    inventory=read(E/'inventory.json'); assert len(inventory['xo'])==1
    xo=inventory['xo'][0];candidate=read(B/'artifact/b03_candidate/candidate.json')
    art=candidate['artifact'];assert xo['sha256']==art['xo_sha256']
    assert sha(B/'src/w4a8_prefill_v1.cpp')==art['source_sha256']
    assert sha(B/'src/w4a8_linear_v1.hpp')==art['header_sha256']
    # B records the serialized loose XML hash, not the raw XO member hash.
    assert sha(B/'artifact/b03_candidate/kernel.xml')==art['kernel_xml_sha256']
    provenance=read(B/'reports/b03/supplement_provenance.json')
    resolved={}
    for name,claim in provenance['selected_current_receipts_all_inputs_exactly_resolved'].items():
        assert sha(B/name)==claim['receipt_sha256'],name
        receipt=read(B/name);assert receipt['exit_code']==0,name
        assert set(receipt['input_sha256'])==set(claim['input_resolution']),name
        for inp,v in claim['input_resolution'].items():
            assert sha(B/v['exact_file'])==v['sha256']==receipt['input_sha256'][inp].lower(),(name,inp)
        log=B/receipt['log'];assert log.is_file(),str(log)
        resolved[name]={'input_count':len(claim['input_resolution']),'log':str(log.relative_to(B)), 'log_sha256':sha(log)}
    groups={}
    for p in sorted((B/'evidence/b03/batches/double').glob('*/manifest.json')):
        m=read(p)
        missing=[]
        for name,v in m['files'].items():
            if not (p.parent/name).is_file():
                missing.append(name)
                assert name.endswith('.wdb'), ('required missing file',p,name)
            else:assert sha(p.parent/name)==v['sha256'],(p,name)
        assert m['receipt'] in resolved,m['receipt']
        groups[p.parent.name]={'transactions':m['transactions'],'cases':m['cases'],'file_count':len(m['files']),
                              'omitted_waveform_databases':missing}
    assert sum(v['transactions'] for v in groups.values())==66
    buffers=read(B/'reports/b03/supplement_buffers.json')
    with zipfile.ZipFile(B/'artifact/b03_candidate/w4a8_linear_v1.xo') as z:
        for name,v in buffers['reports_and_rtl_extracted_from_exact_xo'].items():
            assert z.read(v['xo_member'])==(B/name).read_bytes(),name
        xml=z.read(xo['embedded_metadata_path'])
    loose=B/'artifact/b03_candidate/kernel.xml'
    def tree(e):return (e.tag,sorted(e.attrib.items()),(e.text or '').strip(),[tree(c) for c in e])
    assert tree(ET.fromstring(loose.read_bytes()))==tree(ET.fromstring(xml)), 'semantic XML mismatch'
    k=ET.fromstring(xml).find('kernel')
    header=(B/'src/w4a8_linear_v1.hpp').read_text(encoding='utf-8')
    args=re.search(r'extern "C" void w4a8_linear_v1\((.*?)\);',header,re.S).group(1).split(',')
    metadata=list(k.find('args'));assert len(args)==len(metadata)==17
    typed=[]
    for a,x in zip(args,metadata):
        t,n=a.strip().rsplit(' ',1);assert n==x.attrib['name'];typed.append(dict(x.attrib,header_type=t))
    old=read(ROOT/'evidence/A06_acceptance/interface-map.candidate.json')
    old.update(status='ACTUAL_XO_HEADER_SIGNATURE_AUDITED',source_commit='e227297ee1bb0bdf542fc81761642b23639e15c0',
               metadata_path=xo['embedded_metadata_path'],metadata_sha256=xo['embedded_metadata_sha256'],
               loose_metadata_sha256=sha(loose),loose_xml_semantically_equal=True,
               kernel=k.attrib,arguments=typed,ports=[v.attrib for v in k.find('ports')],
               xo_path=str((B/'artifact/b03_candidate/w4a8_linear_v1.xo').relative_to(ROOT)).replace('\\','/'),
               xo_sha256=xo['sha256'],selected_variant='double',not_a_link_or_deployment_authorization=True)
    old.pop('metadata_matches_baseline_claim',None)
    with (E/'interface-map.json').open('x',encoding='utf-8') as f:json.dump(old,f,indent=2)
    for name in ['quant_v1.json','sp_linear_v1.h']:
        assert (B/'contracts'/name).read_bytes()==(ROOT/'contracts/qwen35'/name).read_bytes()
    result={'status':'PASS_STATIC_ONLY','payload_files':len(package['files']),'inventory_files':len(inventory['files']),
            'xo':xo,'candidate':candidate,'groups':groups,'receipts':resolved,'buffers':buffers,
            'old_source_math_changed':False,'old_source_interface_change':'gmem_sw max_widen_bitwidth=32 added',
            'BOARD':'NOT_TESTED','numeric_acceptance':'PENDING'}
    with (E/'static.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps({'status':'PASS_STATIC_ONLY','files':len(package['files']),'receipts':len(resolved),'rtl_transactions':66}))
if __name__=='__main__':main()
