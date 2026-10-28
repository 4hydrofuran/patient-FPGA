param([Parameter(Mandatory=$true)][ValidateSet('network','stage')][string]$Action)
$ErrorActionPreference='Stop'
$boot='bf3796f0-9785-4afd-a617-3ad578a24d10'
$guard='set -e; test "$(cat /proc/sys/kernel/random/boot_id)" = '+$boot+'; test "$(uname -r)" = 6.8.0-1015-xilinx; test "$(sha256sum /etc/machine-id | cut -d '' '' -f1)" = ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec; test ! -d /sys/module/zocl; test -d /sys/kernel/config/device-tree/overlays/k26-starter-kits_image_1; '
if($Action -eq 'network'){
    $old=& "$PSScriptRoot/driver_board_step.ps1" -Step temporary_nm_connection -ValidateOnly -OutputPath ([IO.Path]::Combine([IO.Path]::GetTempPath(),[guid]::NewGuid().ToString()+'.json')) | ConvertFrom-Json
    $command=$guard+$old.command.Replace('31582feb-665b-49ad-a289-1cfe8e2ee4f1',$boot).Replace('a10-temp-20261019','a10-irq2-stage-20261021').Replace('60000','55000')
    # Preserve the observed timeout receipt; do not rerun activation. Future
    # plans use the independently successful bounded D-Bus readback instead of
    # enumerating every NM profile, which exceeded its 3-second read deadline.
    $marker='; /usr/bin/timeout 3 nmcli -f NAME,UUID,FILENAME connection show'
    $pos=$command.IndexOf($marker)
    if($pos -lt 0){throw 'Expected historical diagnostic tail changed'}
    $readback='a10_path=$(busctl --timeout=3 call org.freedesktop.NetworkManager /org/freedesktop/NetworkManager/Settings org.freedesktop.NetworkManager.Settings GetConnectionByUuid s 7423b8d4-31b0-4f1f-ae1b-4c265047a101 | sed -n ''s/^o "\(\/org\/freedesktop\/NetworkManager\/Settings\/[0-9]\+\)"$/\1/p''); test -n "$a10_path"; busctl --timeout=3 get-property org.freedesktop.NetworkManager "$a10_path" org.freedesktop.NetworkManager.Settings.Connection Unsaved'
    $command=$command.Substring(0,$pos)+'; '+$readback
}else{
    $upload=Get-Content -Raw "$PSScriptRoot/../../local/a10-irq2-transfer-20261021-v1/upload-readback.json"|ConvertFrom-Json
    if($upload.status -ne 'UPLOADED_HASH_VERIFIED_NOT_INSTALLED'){throw 'Verified irq2 upload required'}
    $checks=@()
    foreach($name in @('stage_irq2_board.py','stage_candidate_board.py','original_module_backup.py','original-backup-proof.json')){
        $hash=$upload.hashes.$name
        if($hash -notmatch '^[a-f0-9]{64}$'){throw 'Invalid source pin'}
        $checks+=('test "$(sha256sum '+$name+' | cut -d '' '' -f1)" = '+$hash)
    }
    $command=$guard+'cd /home/ubuntu/a10-irq2-stage-20261021-v1; '+($checks -join '; ')+'; sudo -n /usr/bin/python3 -B stage_irq2_board.py --execute-authorized-stage'
}
[ordered]@{step=('irq2_'+$Action);command=$command;board_contact=$false}|ConvertTo-Json
