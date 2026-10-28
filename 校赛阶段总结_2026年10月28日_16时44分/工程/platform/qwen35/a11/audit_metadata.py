"""PC-only MLP metadata/HWH crosscheck; does not use vector-add addresses."""
import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[3]


def audit(release):
    hashes=json.loads((release/'files.sha256.json').read_text())
    evidence={}
    def checked(name):
        p=release/name; data=p.read_bytes();entry=hashes[name]
        expected=entry['sha256'] if isinstance(entry,dict) else entry
        actual=hashlib.sha256(data).hexdigest()
        if actual!=expected:raise ValueError('A07 pin differs: '+name)
        evidence[name]=actual
        return data
    hw=ET.fromstring(checked('artifacts/MPSoC_ext_platform.hwh'))
    metadata=ET.fromstring(checked('reports/implementation/EMBEDDED_METADATA.xml'))
    modules={m.attrib['INSTANCE']:m for m in hw.findall('.//MODULE')}
    kernel=modules['w4a8_linear_v1_1']
    intc=modules['axi_intc_0']
    params=lambda m:{p.attrib['NAME']:p.attrib['VALUE'] for p in m.findall('./PARAMETERS/PARAMETER')}
    kp,ip=params(kernel),params(intc)
    mem=json.loads(checked('reports/implementation/MEM_TOPOLOGY.json'))['mem_topology']['m_mem_data']
    con=json.loads(checked('reports/implementation/CONNECTIVITY.json'))['connectivity']['m_connection']
    ips=json.loads(checked('reports/implementation/IP_LAYOUT.json'))['ip_layout']['m_ip_data']
    if len(ips)!=1 or ips[0]['m_name']!='w4a8_linear_v1:w4a8_linear_v1_1':raise ValueError('unexpected kernels')
    bindings={int(v['arg_index']):int(v['mem_data_index']) for v in con if v['m_ip_layout_index']=='0'}
    if len(con)!=6 or set(bindings)!=set(range(6)):raise ValueError('ambiguous connections')
    groups=[bindings[i] for i in range(6)]
    windows=[dict(base=int(mem[g]['m_base_address'],0),span=int(mem[g]['m_sizeKB'],0)*1024) for g in groups]
    if any(mem[g]['m_used']!='1' or mem[g]['m_tag']!='HP0' for g in groups):raise ValueError('unexpected physical path')
    ranges=kernel.findall('./MEMORYMAP/MEMRANGE')
    if not ranges:ranges=kernel.findall('.//MEMRANGE')
    ports={r.attrib['MASTERBUSINTERFACE']:r.attrib for r in ranges if r.attrib.get('ADDRESSBLOCK')=='HP0_DDR_LOW'}
    expected_ports={'m_axi_gmem_w','m_axi_gmem_sw','m_axi_gmem_x','m_axi_gmem_y','m_axi_gmem_meta'}
    if set(ports)!=expected_ports:raise ValueError('MLP HWH master memory path differs')
    if any(int(r['BASEVALUE'],0)!=windows[0]['base'] or int(r['HIGHVALUE'],0)+1!=windows[0]['span'] for r in ports.values()):
        raise ValueError('xclbin and HWH physical window differ')
    args=metadata.findall('.//kernel/arg')
    if len(args)!=17:raise ValueError('17-argument ABI required')
    expected_names=['w_packed','sw','xq','sx','y','meta','t','n','k','w_bytes','sw_bytes','x_bytes','sx_bytes','y_bytes','meta_bytes','job_id','abi_version']
    for i,(arg,name) in enumerate(zip(args,expected_names)):
        if int(arg.attrib['id'])!=i or arg.attrib['name']!=name:raise ValueError('argument order differs')
    cu_addr=int(ips[0]['m_base_address'],0)
    ps=modules['ps_e']
    mapped=[r.attrib for r in ps.findall('.//MEMRANGE') if r.attrib['INSTANCE']=='w4a8_linear_v1_1']
    if len(mapped)!=1 or int(mapped[0]['BASEVALUE'],0)!=cu_addr:raise ValueError('CU HWH address differs')
    if int(ip['C_NUM_INTR_INPUTS'],0)!=32 or int(ip['C_KIND_OF_INTR'],0)!=0xfffffffd:
        raise ValueError('interrupt controller differs from reviewed irq2 path')
    return dict(domain='PC_METADATA_NOT_DEPLOYMENT',BOARD='NOT_TESTED',source_hashes=evidence,
                kernel='w4a8_linear_v1',cu_instance='w4a8_linear_v1_1',cu_address=cu_addr,
                cu_span=int(mapped[0]['HIGHVALUE'],0)+1-cu_addr,cu_interrupt=int(ips[0]['m_interrupt_id']),
                argument_groups=groups,argument_address_windows=windows,arguments=[a.attrib for a in args],
                intc_params=ip,kernel_params=kp,
                warning='Addressability is metadata, NOT verified allocation capacity or safe global memory budget')


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',required=True,type=Path)
    args=ap.parse_args();result=audit(ROOT/'release/a07_b04_v3')
    with args.out.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps({k:result[k] for k in ('domain','BOARD','cu_address','cu_span','cu_interrupt','argument_groups')}))
