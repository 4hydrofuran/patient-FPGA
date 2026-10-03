"""Seal actual A-local Csim plus previously reviewed exact-version evidence."""
import hashlib, json, re, subprocess
from pathlib import Path
R=Path(__file__).resolve().parents[4]
E=R/'evidence/A07_closeout/20261004-v1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
source=json.loads((R/'hw/linear_A/KERNEL_SOURCE.json').read_text())
runroot=R/'evidence/A06_acceptance/a-owned-closeout-v1/license-20261004-29e7'
receipt=json.loads((runroot/'csim.json').read_text())
result=json.loads((runroot/'result.json').read_text())
host=json.loads((runroot/'host.json').read_text())
assert receipt['exit_code']==0 and result['numerical_Csim_pass'] is True
text=receipt['stdout']+receipt['stderr']
summaries=[json.loads(x) for x in re.findall(r'^SUMMARY (\{.*\})\s*$',text,re.M)]
assert len(summaries)==1 and summaries[0]['status']=='PASS'
assert summaries[0]['cases']==61 and summaries[0]['checks']==2800022
assert 'CSim done with 0 errors' in text
for path,digest in host['input_sha256'].items():
    if path.startswith('/mnt/c/Patientqwen/'):
        assert sha(R/path.removeprefix('/mnt/c/Patientqwen/'))==digest,path
b=R/source['received_directory']
assert sha(b/'src/w4a8_prefill_v1.cpp')==source['selected_source_sha256']
assert sha(b/'src/w4a8_linear_v1.hpp')==source['selected_header_sha256']
assert sha(R/source['xo_path'])==source['xo_sha256']
old=R/'evidence/A06_acceptance/a-owned-closeout-v1/REPORT.json'
previous=json.loads(old.read_text())
assert previous['vectors_exact_sha']==382 and previous['PC_A_independent']['status']=='PASS'
assert previous['archived_RTL']['transactions']==66
rev=subprocess.check_output(['git','rev-parse','origin/b/qwen35-compute'],cwd=R,text=True).strip()
assert rev=='9a75600e0df8816f4b9134b5c39d67965310dcd3'
received=R/'hw/linear_B_received/B04-scope-9a75600-20261003'
intake=json.loads((received/'RECEIPT.json').read_text())
for name,meta in intake['files'].items():
    raw=subprocess.check_output(['git','show',rev+':'+name],cwd=R)
    assert hashlib.sha256(raw).hexdigest()==meta['sha256']==sha(received/name),name
report={'status':'PASS_A06_PREBOARD_ACCEPTED_BY_A','provider':'B','acceptance_owner':'A',
        'B_signature':'NOT_CLAIMED','A_local_Csim':summaries[0],
        'reused_exact_version_evidence':previous['matrix'],
        'prior_report_sha256':sha(old),'B04_remote_commit':rev,'B04_files_reverified':len(intake['files']),
        'Csim_evidence':{p.name:sha(p) for p in runroot.iterdir() if p.is_file()},
        'source_sha256':source['selected_source_sha256'],'xo_sha256':source['xo_sha256'],
        'limitations':previous['residual_notes'], 'BOARD':'NOT_TESTED',
        'note':'Prior matrix records historical blocked states; new local Csim supersedes only that blocker. P&R remains A07.'}
with (E/'A06_ACCEPTED.json').open('x') as f:json.dump(report,f,indent=2)
print(json.dumps({'status':report['status'],'cases':61,'checks':2800022,'B04_files':len(intake['files'])}))
