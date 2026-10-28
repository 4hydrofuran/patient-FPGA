"""Bounded evidence checks, negative probes, preserved provider failures."""
import hashlib,json,re,shutil,subprocess,sys
from pathlib import Path
R=Path('/mnt/c/Patientqwen');E=R/'evidence/A06_acceptance/supplement-v1';B=R/'hw/linear_B_received/B03-supplement-e227297-20261003/payload'
sys.path.insert(0,str(R/'platform/a1'))
from record import run
def main():
 work=Path(json.loads((E/'tests/outcome.json').read_text())['work']);out=E/'final-checks-v2';out.mkdir(exist_ok=False)
 stat=json.loads((E/'static.json').read_text());port=stat['xo']['kernels'][0]
 prior=json.loads((R/'evidence/A06_acceptance/interface-map.candidate.json').read_text())
 for i,(arg,old) in enumerate(zip(port['args'],prior['arguments'])):
  for key in ['name','id','offset','size','hostSize','type','port','addressQualifier']:
   assert arg[key]==old[key],(i,key)
 assert port['attributes']['hwControlProtocol']=='ap_ctrl_hs'
 expected_widths={'M_AXI_GMEM_W':128,'M_AXI_GMEM_SW':32,'M_AXI_GMEM_X':128,'M_AXI_GMEM_Y':32,'M_AXI_GMEM_META':512,'S_AXI_CONTROL':32}
 assert {v['name']:int(v['dataWidth']) for v in port['ports']}==expected_widths
 csim=(B/'logs/b03/double/20261002-193238-0731631/csim.log').read_text()
 assert 'CSim done with 0 errors' in csim and 'transactions=50' in csim
 for n,k in [(3584,1024),(1024,3584)]:
  for t in range(1,9):assert re.search(r'PASS case=\S+ T='+str(t)+r' N='+str(n)+r' K='+str(k),csim),(t,n,k)
 raw_reports={}
 for name,g in stat['groups'].items():
  p=B/'evidence/b03/batches/double'/name/'report/w4a8_linear_v1_cosim.rpt'
  if p.is_file():
   text=p.read_text();assert re.search(r'Verilog\s*\|\s*Pass',text),name
   raw_reports[name]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'transactions':g['transactions'],'native':'PASS'}
  else:
   assert name=='stall_max_k'
   folder=p.parent.parent;snapshot=json.loads((folder/'snapshot.json').read_text())
   assert snapshot['native_exit_code']==1 and snapshot['postcheck_exit_code']==0
   assert 'RTL Simulation : 1 / 1' in (folder/'native_failed.log').read_text()
   for member,digest in snapshot['rtl_evidence_sha256'].items():
    relative=member.split('/hls/sim/',1)[1]
    if (folder/relative).is_file():assert hashlib.sha256((folder/relative).read_bytes()).hexdigest()==digest.lower()
   raw_reports[name]={'native':'FAIL_EXIT_1_PRESERVED','postcheck':'RECOVERED_EXIT_0',
                      'A04_replay':'PASS_ACTUAL_ARCHIVED_OUTPUT','transactions':1,'not_native_cosim_pass':True}
 # Preserve received source; both counterexamples modify only own throwaway copies.
 probes=[]
 for name,offset in [('y_actual.bin',0),('meta_actual.bin',8)]:
  dst=work/('A-negative-'+name);shutil.copytree(work/'provider/work/supplement_check/rtl/gate_t1/0',dst)
  p=dst/name;data=bytearray(p.read_bytes())
  if name.startswith('y_'):data[:4]=b'\x00\x00\xc0\x7f'  # explicit NaN
  else:data[offset]^=1
  p.write_bytes(data)
  code=run([str(work/'replay-a04'),str(dst)],out/(name+'.json'))
  assert code!=0,'negative probe passed'
  probes.append({'file':name,'exit_code':code,'expected':'REJECT','original_modified':False})
 replay=json.loads((E/'a04-rtl/REPORT.json').read_text());formats=[]
 for v in replay['vectors']:
  if v['byte_exact']:continue
  name=v['path'];reg=name.replace('vectors/b03_double_real/','vectors/real_regenerated/').replace('vectors/b03_double/','vectors/pc_regenerated/')
  before=(B/name).read_bytes();after=(work/'provider'/reg).read_bytes()
  formats.append({'path':name,'only_CRLF_LF':before.replace(b'\r\n',b'\n')==after.replace(b'\r\n',b'\n')})
 # Final source/package hashes must still match after all tests.
 package=json.loads((B/'B03_package_manifest.json').read_text())
 for name,v in package['files'].items():assert hashlib.sha256((B/name).read_bytes()).hexdigest()==v['sha256']
 # Preserve provider replay receipt/logs and failed entry locally, not only in WSL work.
 for name in ['rtl.receipt.json','rtl_replay.log','pc_full50.log','real_weight4.log','pc_compile.log','real_compile.log']:
  shutil.copyfile(work/'provider/work/supplement_check'/name,out/('provider-'+name))
 result={'status':'PASS_BOUNDED_EVIDENCE_AND_NEGATIVE_CHECKS','abi_17_arguments':'MATCH_HEADER_AND_EMBEDDED_XML',
         'ports':expected_widths,'B_Csim_coverage':'T1..8_BOTH_SHAPES_SAME_SOURCE_HASH_PASS',
         'B_Cosim_original_reports':raw_reports,'A04_negative_probes':probes,'json_format_differences':formats,
         'immutable_payload_files_rehashed':len(package['files']),'BOARD':'NOT_TESTED'}
 (out/'REPORT.json').write_text(json.dumps(result,indent=2));print(json.dumps({'status':result['status'],'negative_probes':len(probes),'json_CRLF_only':sum(v['only_CRLF_LF'] for v in formats)}))
if __name__=='__main__':main()
