"""Copy three exact boot files over existing pinned SSH; never upload/write board."""
import hashlib,json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'platform/qwen35/a10'))
from fetch_single_result import plan
DEST=ROOT/'evidence/model_pl_A/20261024-ttft10-01-v1/recovery-authorized-20261025-v1/boot-backup-01'
PINS={'image.fit':(67701612,'23a0ad7516d6f67f248f952653324c18a9c7d1db31fdf27a003f021adf0ca61e'),
      'boot.scr.uimg':(8000,'f1eb9e841e100a64f59eed77bccd73396297ce93bbcb6ce4916a7b516793c685'),
      'a10-candidate-irq2-20261021.fit':(65555004,'e60d7f49033ef8efbd2396fafbe94a3bc684a478d5f5e31676626d1bc5f6ae2b')}
DEST.mkdir(exist_ok=False)
ssh,_=plan()
argv=['C:/Windows/System32/OpenSSH/scp.exe',*ssh[2:-2],
      *['ubuntu@192.168.2.2:/boot/firmware/'+n for n in PINS],str(DEST)]
(DEST/'reservation.json').write_text(json.dumps(dict(argv=argv,expected=PINS),indent=2))
auth=ROOT/'evidence/model_pl_A/20261024-ttft10-01-v1/tt10_01_askpass.exe'
env=dict(os.environ,SSH_ASKPASS=str(auth),SSH_ASKPASS_REQUIRE='force',DISPLAY='tt10-hidden-auth')
started=time.monotonic()
p=subprocess.run(argv,env=env,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
r=dict(exit_code=p.returncode,elapsed_s=time.monotonic()-started,stderr=p.stderr.decode(errors='replace'),files={},board_files_written=False)
for name,(size,pin) in PINS.items():
    f=DEST/name
    if f.is_file():
        h=hashlib.sha256()
        with f.open('rb') as s:
            for b in iter(lambda:s.read(1048576),b''):h.update(b)
        r['files'][name]=dict(bytes=f.stat().st_size,sha256=h.hexdigest(),equal=f.stat().st_size==size and h.hexdigest()==pin)
r['status']='PASS_PINNED_BOOT_BACKUP' if p.returncode==0 and len(r['files'])==3 and all(v['equal'] for v in r['files'].values()) else 'FAILED_KEEP_PARTIAL_BACKUP'
(DEST/'receipt.json').write_text(json.dumps(r,indent=2))
print(json.dumps(r),flush=True)
raise SystemExit(0 if r['status']=='PASS_PINNED_BOOT_BACKUP' else 1)
