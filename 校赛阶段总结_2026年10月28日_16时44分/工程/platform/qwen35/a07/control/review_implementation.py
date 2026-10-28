"""Review the actual routed reports and linked metadata; never execute hardware.

The warning allowlist is an explicit review of this frozen kernel, not a blanket
waiver for future implementations. Unexpected checks fail closed.
"""
import hashlib,json,re,shutil,sys,xml.etree.ElementTree as ET,zipfile
from pathlib import Path
R=Path(__file__).resolve().parents[4]
W=Path(sys.argv[1]).resolve(); A=Path(sys.argv[2]).resolve()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):
    with p.open('x') as f:json.dump(v,f,indent=2)
def rules(path):
    text=path.read_text()
    rows=re.findall(r'^\|\s*([A-Z]+-\d+)\s*\|\s*(Warning|Advisory|Critical Warning|Error)\s*\|[^\n]*\|\s*(\d+)\s*\|$',text,re.M)
    assert sum(int(n) for _,_,n in rows)==int(re.search(r'Checks found:\s*(\d+)',text)[1])
    return {name:{'severity':sev,'count':int(n)} for name,sev,n in rows}
assert json.loads((A/'vivado.json').read_text())['exit_code']==0
timing=(A/'routed/timing.rpt').read_text()
assert 'All user specified timing constraints are met.' in timing
line=timing.split('WNS(ns)',1)[1].splitlines()[2].split()
assert len(line)==12,line
names=['WNS_ns','TNS_ns','setup_failing_endpoints','setup_total_endpoints','WHS_ns','THS_ns','hold_failing_endpoints','hold_total_endpoints','WPWS_ns','TPWS_ns','pulse_failing_endpoints','pulse_total_endpoints']
summary=dict(zip(names,map(float,line)))
assert all(summary[n]>=0 for n in ['WNS_ns','WHS_ns','WPWS_ns'])
assert all(summary[n]==0 for n in ['TNS_ns','THS_ns','TPWS_ns','setup_failing_endpoints','hold_failing_endpoints','pulse_failing_endpoints'])
checks=dict((n,int(c)) for n,c in re.findall(r'checking ([a-z_]+) \((\d+)\)',timing))
assert len(checks)==12 and not any(checks.values()),checks
route=(A/'routed/route_status.rpt').read_text()
route_errors=int(re.search(r'nets with routing errors[^:]*:\s*(\d+)',route)[1]);assert route_errors==0
fully=int(re.search(r'fully routed nets[^:]*:\s*(\d+)',route)[1])
routable=int(re.search(r'of routable nets[^:]*:\s*(\d+)',route)[1]);assert fully==routable
drc=rules(A/'routed/drc.rpt')
assert drc=={'DPIP-2':{'severity':'Warning','count':28},'DPOP-3':{'severity':'Warning','count':37},'DPOP-4':{'severity':'Warning','count':28},'AVAL-155':{'severity':'Advisory','count':14},'AVAL-156':{'severity':'Advisory','count':4}},drc
method=rules(A/'routed/methodology.rpt')
assert method=={'CLKC-40':{'severity':'Advisory','count':1},'CLKC-56':{'severity':'Advisory','count':1}}
assert 'All paths are Safely Timed.' in (A/'routed/cdc.rpt').read_text()
src=json.loads((R/'hw/linear_A/KERNEL_SOURCE.json').read_text());xo=R/src['xo_path']
assert src['accepted'] and src['frozen'] and sha(xo)==src['xo_sha256']
with zipfile.ZipFile(xo) as z:raw=z.read(src['embedded_metadata_member'])
assert hashlib.sha256(raw).hexdigest()==src['embedded_metadata_sha256']
xok=ET.fromstring(raw).find('.//kernel'); linked=ET.parse(A/'EMBEDDED_METADATA.xml').find('.//kernel')
assert linked.get('name')==xok.get('name')=='w4a8_linear_v1'
assert linked.get('hwControlProtocol')==xok.get('hwControlProtocol')=='ap_ctrl_hs'
args=list(linked.iter('arg')); original=list(xok.iter('arg'));assert len(args)==len(original)==17
for got,want in zip(args,original):
    for field in ['name','id','port','size','offset','hostSize','addressQualifier','type']:
        assert got.get(field)==want.get(field),(field,got.attrib,want.attrib)
ports={p.get('name'):{k:p.get(k) for k in ['mode','dataWidth','portType']} for p in linked.iter('port')}
for p in xok.iter('port'):
    assert ports[p.get('name')]=={k:p.get(k) for k in ['mode','dataWidth','portType']}
ip=json.loads((A/'IP_LAYOUT.json').read_text())['ip_layout']['m_ip_data'];assert len(ip)==1 and ip[0]['m_ip_control']=='AP_CTRL_HS'
groups=json.loads((A/'GROUP_CONNECTIVITY.json').read_text())['group_connectivity']['m_connection']
logical={}
for c in groups:
    assert int(c['m_ip_layout_index'])==0
    idx=int(c['arg_index']); group=int(c['mem_data_index'])
    assert idx not in logical or logical[idx]==group
    logical[idx]=group
assert logical==dict.fromkeys(range(6),3),logical
hwh=W/'_x/link/vivado/vpl/prj/prj.gen/sources_1/bd/MPSoC_ext_platform/hw_handoff/MPSoC_ext_platform.hwh'
hw=ET.parse(hwh);km=next(m for m in hw.iter('MODULE') if m.get('INSTANCE')=='w4a8_linear_v1_1')
apclk=next(p for p in km.iter('PORT') if p.get('NAME')=='ap_clk')
assert apclk.get('CLKFREQUENCY')=='149998500' and apclk.get('SIGNAME')=='clk_wiz_0_clk_out1'
assert re.search(r'clk_out1_MPSoC_ext_platform_clk_wiz_0_0\s+\{[^}]+\}\s+6\.667\s+150\.000',timing)
util=(A/'routed/utilization.rpt').read_text()
rows={}
for n in ['MPSoC_ext_platform_wrapper','w4a8_linear_v1_1']:
    l=next(l for l in util.splitlines() if l.startswith('|') and l.split('|')[1].strip()==n)
    vals=[int(v.strip()) for v in l.split('|')[3:-1]]
    rows[n]=dict(zip(['total_LUT','logic_LUT','LUTRAM','SRL','FF','RAMB36','RAMB18','URAM','DSP'],vals))
info=json.loads((A/'info.json').read_text())['stdout']
uuid=re.search(r'UUID \(xclbin\):\s*([a-f0-9-]+)',info)[1]
bit=W/'_x/link/int/system.bit';assert sha(bit)==sha(W/'_x/link/vivado/vpl/prj/prj.runs/impl_1/MPSoC_ext_platform_wrapper.bit')
save(A/'REVIEW.json',{'status':'PASS_OFFLINE_IMPLEMENTATION_REVIEW','reviewer_role':'A','BOARD':'NOT_TESTED',
    'xclbin_sha256':sha(W/'w4a8.xclbin'),'xclbin_uuid':uuid,'source_xo_sha256':sha(xo),
    'timing':summary,'check_timing':checks,'route':{'fully_routed':fully,'routable':routable,'errors':route_errors},
    'drc':drc,'drc_critical_or_error':0,'drc_disposition':'93 DSP input/output pipeline warnings are performance advisories for frozen B IP; timing is met at original clock. 18 DSP constant-control advisories retained. No severity changed or checks suppressed.',
    'methodology':method,'methodology_disposition':'Two official platform clock-wizard advisories retained, no constraints edited.',
    'CDC':'All paths are Safely Timed (routed static analysis, not BOARD)',
    'kernel_clock_hz':149998500,'kernel_clock_hwh':apclk.attrib,
    'clock_metadata_note':'Generic core kernelClocks lists KERNEL_CLK 299.997 MHz and DATA_CLK 149.9985 MHz; actual integrated ap_clk HWH and routed constraints prove 149.9985 MHz. No scalable CLOCK_FREQ_TOPOLOGY section. Do not claim 300MHz kernel.',
    'resources':rows,'linked_argument_count':17,'linked_arguments':[a.attrib for a in args],
    'ports':ports,'logical_argument_groups':{args[i].get('name'):g for i,g in logical.items()},
    'group_connectivity_rows':len(groups),'duplicate_identical_group_rows':len(groups)-len(logical),
    'memory_topology':json.loads((A/'MEM_TOPOLOGY.json').read_text()),
    'memory_scope':'HP0 2GiB link address window only; Linux/CMA/BO budget, physical reachability and allocation remain null, NOT_TESTED.',
    'matching_files':{'bit':{'path':str(bit),'sha256':sha(bit)},'hwh':{'path':str(hwh),'sha256':sha(hwh)}},
    'boot_package':'NOT_BUILT_OR_VERIFIED; no inferred DT/firmware/rootfs pairing',
    'report_sha256':{p.name:sha(p) for p in (A/'routed').iterdir() if p.is_file()}})
print(json.dumps({'status':'PASS_OFFLINE_IMPLEMENTATION_REVIEW','timing':summary,'BOARD':'NOT_TESTED'}))
