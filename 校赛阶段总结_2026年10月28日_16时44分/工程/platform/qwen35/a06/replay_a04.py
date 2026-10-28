"""No new RTL run: A independent reference on provider-decoded original TV."""
import hashlib,json,subprocess,sys
from pathlib import Path
R=Path('/mnt/c/Patientqwen');E=R/'evidence/A06_acceptance/supplement-v1';B=R/'hw/linear_B_received/B03-supplement-e227297-20261003/payload'
sys.path.insert(0,str(R/'platform/a1'))
from record import run
def main():
 outcome=json.loads((E/'tests/outcome.json').read_text());work=Path(outcome['work']);prov=work/'provider';rtl=prov/'work/supplement_check/rtl'
 out=E/'a04-rtl';out.mkdir(exist_ok=False);exe=work/'replay-a04'
 assert run(['g++','-std=c++17','-O3','-fno-fast-math','-ffp-contract=off','-I'+str(R/'quant/reference'),str(R/'platform/qwen35/a06/replay_a04.cpp'),str(R/'quant/reference/w4a8.cpp'),'-o',str(exe)],out/'compile.json')==0
 results=[]
 for folder in sorted(rtl.glob('*/*')):
  if not (folder/'request.txt').is_file():continue
  code=run([str(exe),str(folder)],out/(folder.parent.name+'-'+folder.name+'.json'))
  if code:raise RuntimeError('independent failure retained: '+str(folder))
  r=json.loads((out/(folder.parent.name+'-'+folder.name+'.json')).read_text())
  results.append(dict(group=folder.parent.name,transaction=folder.name,**json.loads(r['stdout'])))
 assert len(results)==66
 # Report formatting separately; never change B delivered files or claim exact
 # bytes when JSON serialization/newlines differ across compiler platforms.
 manifest=json.loads((B/'B03_package_manifest.json').read_text());vectors=[]
 for original,regenerated in [('vectors/b03_double','vectors/pc_regenerated'),('vectors/b03_double_real','vectors/real_regenerated')]:
  for name,claim in manifest['files'].items():
   if not name.startswith(original+'/'):continue
   actual=prov/regenerated/name[len(original)+1:];received=B/name
   a=actual.read_bytes();b=received.read_bytes()
   exact=a==b;equiv=None
   if name.endswith('.json'):equiv=json.loads(a)==json.loads(b)
   assert exact or equiv is True,name
   vectors.append({'path':name,'byte_exact':exact,'json_semantic_equal':equiv,'actual_sha256':hashlib.sha256(a).hexdigest(),'received_sha256':claim['sha256']})
 assert len(vectors)==382
 report={'status':'PASS_A04_REFERENCE_ARCHIVED_RTL','transactions':results,'vectors':vectors,
         'byte_exact_vectors':sum(v['byte_exact'] for v in vectors),'json_format_only_differences':sum(not v['byte_exact'] for v in vectors),
         'scope':'A04 independent math; reviewed B parser transports TV bytes; no B kernel/golden linked; group partials compared between references, not internal RTL probes','BOARD':'NOT_TESTED'}
 (out/'REPORT.json').write_text(json.dumps(report,indent=2))
 print(json.dumps({'transactions':66,'byte_exact_vectors':report['byte_exact_vectors'],'json_format_only_differences':report['json_format_only_differences']}))
if __name__=='__main__':main()
