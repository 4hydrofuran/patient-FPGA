import base64
from common import ROOT,sha,save
from step08_common import OUT

if __name__=='__main__':
    src=ROOT/'platform/qwen35/a10/boot_candidate_once.ps1';s=src.read_text(encoding='utf-8')
    s=s.replace('6.8.0-1015-xilinx','6.8.0-1036-xilinx')
    s=s.replace('b007246e409140c73485a057a0e7ccc1fac7116c14699837e4066e74be7532a9','23a0ad7516d6f67f248f952653324c18a9c7d1db31fdf27a003f021adf0ca61e')
    s=s.replace('690fe1225a017a63796df1517b8b203fe9b7500597b2c5a61a0f524875ea2efc','f1eb9e841e100a64f59eed77bccd73396297ce93bbcb6ce4916a7b516793c685')
    guard=ROOT/'platform/qwen35/a12/step08_reboot_guard.py';blob=base64.b64encode(guard.read_bytes()).decode();pin=sha(guard)
    remote='sudo -n /usr/bin/python3 -B -I -c "import base64,hashlib; b=base64.b64decode(\''+blob+'\'); assert hashlib.sha256(b).hexdigest()==\''+pin+'\'; exec(compile(b,\'a12_reboot_guard\',\'exec\'))"'
    old="$wire='( '+$preflight+' ) && sudo -n /usr/bin/systemctl reboot'"
    assert s.count(old)==1
    s=s.replace(old,"$wire='( '+$preflight+' ) && "+remote.replace("'","''")+"'")
    target=ROOT/'platform/qwen35/a12/step08_restore_once.ps1'
    with target.open('x',encoding='utf-8',newline='\n') as f:f.write(s)
    save(OUT/'RESTORE_SCRIPT_PINS.json',dict(source_sha256=sha(src),derived_script_sha256=sha(target),
       root_reboot_guard_sha256=pin,source_boot='76c8aef5-8266-4404-a6e5-e17005103da6',
       explicit_user_authorization=True,reboot_limit=1,temporary_candidate='irq2',default_boot_change=False))
    print('REVIEWED_ONE_REBOOT_RESTORE_SCRIPT_READY')
