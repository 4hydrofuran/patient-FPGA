from pathlib import Path
import json,hashlib
root=Path(__file__).resolve().parents[3]
source=root/'platform/qwen35/a10/boot_candidate_once.ps1'
raw=source.read_text(encoding='utf-8');text=raw
changes=[('6.8.0-1015-xilinx','6.8.0-1036-xilinx'),
('b007246e409140c73485a057a0e7ccc1fac7116c14699837e4066e74be7532a9','23a0ad7516d6f67f248f952653324c18a9c7d1db31fdf27a003f021adf0ca61e'),
('690fe1225a017a63796df1517b8b203fe9b7500597b2c5a61a0f524875ea2efc','f1eb9e841e100a64f59eed77bccd73396297ce93bbcb6ce4916a7b516793c685')]
for before,after in changes:
    assert text.count(before)==1;text=text.replace(before,after)
before='''        $secure=Read-Host 'Transient board sudo credential (not logged)' -AsSecureString
        $ptr=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
        try{$secret=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)}
        finally{[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr);$secure.Dispose()}'''
after='''        $info=[Diagnostics.ProcessStartInfo]::new()
        $info.FileName='C:/Patientqwen/evidence/model_pl_A/20261024-ttft10-01-v1/tt10_01_askpass.exe'
        $info.Arguments='KV260 authorized single reboot (hidden input)'
        $info.UseShellExecute=$false;$info.CreateNoWindow=$true;$info.RedirectStandardOutput=$true
        $authChild=[Diagnostics.Process]::Start($info)
        $secret=$authChild.StandardOutput.ReadToEnd().TrimEnd("`r","`n");$authChild.WaitForExit()
        if($authChild.ExitCode -ne 0){throw 'Authentication cancelled'}'''
assert text.count(before)==1;text=text.replace(before,after)
out=Path(__file__).parent
(out/'boot_once.ps1').write_text(text,encoding='utf-8')
with (out/'BOOT_AUTHORIZATION.json').open('x',encoding='utf-8') as f:
    json.dump(dict(user_answer='允许一次重启和临时引导',source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                   changes=changes,auth_ui_only_changed=True,max_normal_reboots=1,max_RAM_boots=1,
                   flash=False,saveenv=False,default_boot_file_changes=False),f,ensure_ascii=False,indent=2)
