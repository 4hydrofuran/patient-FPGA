"""Generate visibly synthetic policies only inside each control-test directory."""
import hashlib,json,subprocess,sys
from pathlib import Path
binary=Path(sys.argv[1]).resolve();out=Path(sys.argv[2]);out.mkdir(exist_ok=False)
cases=['gates','open_device_open','open_load_xclbin','open_kernel_open','open_group_id','open_allocate','open_bad_address',
       'normal','load_failure','concurrency','timeout','start','state','set_arg','to_7','from_11','from_9',
       'stale','bad_job','bad_build','bad_count','bad_done','bad_bytes','private_error','nan_y','tail_y',
       'device_error','device_abort','device_noresponse']
results=[]
for mode in cases:
    p=out/mode;p.mkdir()
    payload=b'CONTROL TEST ONLY. NOT AN XCLBIN. NOT FOR DEVICES.\n'
    (p/'not-a-bitstream.txt').write_bytes(payload);digest=hashlib.sha256(payload).hexdigest()
    docs={
        'source.json':{'provider':'B','accepted':True,'frozen':True,'production_or_A07_link_allowed':True,'selected_build_id':'0xB3030002','xo_sha256':'CONTROL_ONLY'},
        'profile.json':{'status':'CONTROL_TEST_ONLY_NOT_BOARD','source_xo_sha256':'CONTROL_ONLY','xclbin_sha256':digest,'xclbin_uuid':'CONTROL_ONLY_UUID',
            'verified_bo_budget_bytes':10000000,'bo_charge_alignment':4096,'kernel_build_id':0xB3030002,'device_index':0,'device_name':'CONTROL_ONLY_DEVICE',
            'argument_groups':[5,3,7,7,9,11],'argument_address_windows':[{'base':0,'span':10000000} for _ in range(6)]},
        'config.json':{'api_version':1,'contract_sha256':'83bd402b39350710d8689d50f79296e9625e9c75ccb0ecee145f08067c4ee3b6','backend_id':'A_XRT_B_KERNEL_V1',
            'fallback':'disabled','kernel_source':'source.json','deployment_profile':'profile.json','allow_device_access':True,'xclbin_path':'not-a-bitstream.txt','xclbin_sha256':digest}}
    for name,value in docs.items():(p/name).write_text(json.dumps(value)+'\n')
    r=subprocess.run([str(binary),mode,'config.json'],cwd=p,capture_output=True,text=True,timeout=30)
    result={'argv':[str(binary),mode,'config.json'],'cwd':str(p.resolve()),'exit_code':r.returncode,'stdout':r.stdout,'stderr':r.stderr}
    (p/'command.json').write_text(json.dumps(result,indent=2)+'\n');results.append(result)
    if r.returncode:
        (out/'FAILED.json').write_text(json.dumps(result,indent=2)+'\n');raise SystemExit(r.returncode)
summary={'domain':'PC_CONTROL_DOUBLE_NOT_FPGA','cases':len(results),'checks':sum(json.loads(r['stdout'])['checks'] for r in results),
    'mathematical_verification':False,'hardware_performance':None,'BOARD':'NOT_TESTED'}
(out/'SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))
