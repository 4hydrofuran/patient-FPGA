"""Actual XO vs B04 profile and A production argument binding audit, no devices."""
import hashlib,json,re,zipfile,xml.etree.ElementTree as ET
from pathlib import Path
R=Path(__file__).resolve().parents[4]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    b=R/'hw/linear_B_received/B04-scope-9a75600-20261003'
    profile=json.loads((b/'config/b04/kernel_profile.json').read_text())
    src=json.loads((R/'hw/linear_A/KERNEL_SOURCE.json').read_text())
    xo=R/src['xo_path']
    assert sha(xo)==src['xo_sha256']==profile['xo_sha256']
    assert (R/'contracts/qwen35/sp_linear_v1.h').read_bytes()==(b/'contracts/sp_linear_v1.h').read_bytes()
    with zipfile.ZipFile(xo) as z:raw=z.read(src['embedded_metadata_member'])
    assert hashlib.sha256(raw).hexdigest()==src['embedded_metadata_sha256']==profile['embedded_kernel_xml_sha256']
    root=ET.fromstring(raw);kernel=root.find('.//kernel')
    assert kernel.attrib['name']==profile['kernel_name']=='w4a8_linear_v1'
    args=sorted(kernel.findall('./args/arg'),key=lambda a:int(a.attrib['id']))
    assert len(args)==17
    for actual,want in zip(args,profile['arguments']):
        row=actual.attrib
        assert int(row['id'])==want['index'] and row['name']==want['name']
        assert int(row['offset'],0)==want['control_offset'] and int(row['size'],0)==want['control_bytes']
        assert row['port']==want['port']
    code=(R/'modules/linear_A/xrt/backend.cpp').read_text()
    binds=re.findall(r'c->run.set_arg\((\d+),([^;]+)\);',code)
    expected=['v.w','v.sw','c->x','c->sx','c->y','c->meta','t','a.n','a.k','a.w','a.sw','a.x','a.sx','a.y','uint64_t(64)','job','uint32_t(1)']
    assert binds==[(str(i),value) for i,value in enumerate(expected)],binds
    assert 'c->kernel.group_id(i)' in code
    print(json.dumps({'status':'PASS_XO_PROFILE_PRODUCTION_BINDINGS','arguments':17,'meta_bytes':40,
        'xo_sha256':sha(xo),'source_sha256':sha(R/'modules/linear_A/xrt/backend.cpp'),
        'BOARD':'NOT_TESTED','actual_groups':None}))
if __name__=='__main__':main()
