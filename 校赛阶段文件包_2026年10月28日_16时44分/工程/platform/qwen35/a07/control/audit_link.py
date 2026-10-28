"""Read actual linked xclbin and routed checkpoint; never open a device."""
import hashlib,json,shutil,subprocess,sys
from pathlib import Path
R=Path('/mnt/c/Patientqwen')
W=Path(sys.argv[1]).resolve()
OUT=Path.cwd()/'audit'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):
    with p.open('x') as f:json.dump(v,f,indent=2)
def run(argv,name):
    q=subprocess.run(list(map(str,argv)),capture_output=True,text=True)
    save(OUT/name,{'argv':list(map(str,argv)),'cwd':str(Path.cwd()),'exit_code':q.returncode,'stdout':q.stdout,'stderr':q.stderr})
    assert q.returncode==0,(name,q.returncode)
    return q.stdout
assert json.loads((W/'link.json').read_text())['exit_code']==0
artifact=json.loads((W/'artifact.json').read_text())
assert sha(W/'w4a8.xclbin')==artifact['xclbin_sha256']
OUT.mkdir(exist_ok=False)
info=run(['xclbinutil','--input',W/'w4a8.xclbin','--info'],'info.json')
for section in ['MEM_TOPOLOGY','CONNECTIVITY','IP_LAYOUT','CLOCK_FREQ_TOPOLOGY','EMBEDDED_METADATA','SYSTEM_METADATA','BUILD_METADATA','GROUP_TOPOLOGY','GROUP_CONNECTIVITY']:
    if section in ['CLOCK_FREQ_TOPOLOGY','GROUP_TOPOLOGY','GROUP_CONNECTIVITY'] and section not in info:
        save(OUT/(section+'-absent.json'),{'status':'SECTION_NOT_PRESENT','section':section,
            'reason':'Read fixed clocks from SYSTEM_METADATA and routed report_clocks; absent scalable clocks are not zero frequency.'})
        continue
    fmt='RAW' if section in ['EMBEDDED_METADATA','SYSTEM_METADATA'] else 'JSON'
    suffix='xml' if section=='EMBEDDED_METADATA' else 'json'
    run(['xclbinutil','--input',W/'w4a8.xclbin','--dump-section',f'{section}:{fmt}:{OUT/section}.{suffix}'],section+'-command.json')
dcp=list((W/'_x/link/vivado').glob('**/impl_1/*_routed.dcp'))
assert len(dcp)==1,dcp
script=OUT/'audit_implementation.tcl';shutil.copyfile(R/'platform/qwen35/a07/control/audit_implementation.tcl',script)
run(['vivado','-mode','batch','-source',script,'-tclargs',dcp[0],OUT/'routed'],'vivado.json')
save(OUT/'INPUTS.json',{'xclbin':str(W/'w4a8.xclbin'),'xclbin_sha256':sha(W/'w4a8.xclbin'),
    'routed_dcp':str(dcp[0]),'routed_dcp_sha256':sha(dcp[0]),'script_sha256':sha(script),
    'status':'REPORTS_PENDING_CONTENT_REVIEW','BOARD':'NOT_TESTED'})
print(json.dumps({'audit':str(OUT),'status':'REPORTS_PENDING_CONTENT_REVIEW','BOARD':'NOT_TESTED'}))
