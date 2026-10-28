param([string]$Port = 'COM5',[switch]$UseExistingShell)
$ErrorActionPreference = 'Stop'
$repo = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$expected = 'FTDIBUS\VID_0403+PID_6011+XFL1CYYPZ52YB\0000'
$device = @(Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -eq $expected -and $_.FriendlyName -eq ('USB Serial Port (' + $Port + ')') })
if ($device.Count -ne 1 -or $device[0].Status -ne 'OK') { throw 'Exact user-connected FTDI UART channel B differs' }
$auth = Join-Path $repo 'evidence/model_pl_A/20261024-ttft10-01-v1/tt10_01_askpass.exe'
$code = [System.IO.File]::ReadAllBytes((Join-Path $PSScriptRoot 'tt10_01_uart_identity.py'))
$encoded = [Convert]::ToBase64String($code)
$command = 'python3 -B -I -c "import base64;exec(compile(base64.b64decode(''' + $encoded + '''),''tt10_uart_read_only_identity'',''exec''))"'
$serial = [System.IO.Ports.SerialPort]::new($Port,115200,[System.IO.Ports.Parity]::None,8,[System.IO.Ports.StopBits]::One)
$serial.Handshake = [System.IO.Ports.Handshake]::None
$serial.DtrEnable = $false
$serial.RtsEnable = $false
$serial.WriteTimeout = 3000
$serial.NewLine = "`r"
function Read-Until([string]$pattern,[int]$seconds) {
    $buffer=[System.Text.StringBuilder]::new()
    $watch=[Diagnostics.Stopwatch]::StartNew()
    while ($watch.Elapsed.TotalSeconds -lt $seconds) {
        [void]$buffer.Append($serial.ReadExisting())
        if ($buffer.Length -gt 262144) { throw 'UART byte budget exceeded' }
        if ($buffer.ToString() -match $pattern) { return $buffer.ToString() }
        Start-Sleep -Milliseconds 100
    }
    throw 'UART expected prompt timed out; no retry, no configuration action'
}
$password=$null
$phase='OPEN_UART'
try {
    $serial.Open()
    $serial.Write("`r")
    if ($UseExistingShell) {
        $phase='VERIFY_EXISTING_SHELL'
        $null=Read-Until 'ubuntu@kria:[^\r\n]*\$\s*$' 5
    } else {
    $phase='VERIFY_LOGIN_PROMPT'
    $null=Read-Until 'kria login:\s*$' 5
    $serial.WriteLine('ubuntu')
    $phase='VERIFY_PASSWORD_PROMPT'
    $null=Read-Until 'Password:\s*$' 8
    $info=[Diagnostics.ProcessStartInfo]::new()
    $info.FileName=$auth
    $info.Arguments='Verified KV260 UART login'
    $info.UseShellExecute=$false
    $info.CreateNoWindow=$true
    $info.RedirectStandardOutput=$true
    $inputProcess=[Diagnostics.Process]::Start($info)
    $password=$inputProcess.StandardOutput.ReadToEnd().TrimEnd("`r","`n")
    $inputProcess.WaitForExit()
    if ($inputProcess.ExitCode -ne 0 -or [string]::IsNullOrEmpty($password) -or $password.Contains("`n") -or $password.Contains("`r")) { throw 'User authentication cancelled or invalid; no retry' }
    # Input stays in memory and is only sent while getty is at Password:.
    # No authentication transcript or user-entered text is written or emitted.
    $phase='AUTHENTICATE_USER_HIDDEN_INPUT'
    $serial.WriteLine($password)
    $null=Read-Until 'ubuntu@kria:[^\r\n]*\$\s*$' 15
    $password=$null
    }
    $phase='READ_STRUCTURED_IDENTITY'
    $serial.WriteLine($command)
    $output=Read-Until '__TT10_UART_IDENTITY_END__' 20
    $match=[regex]::Match($output,'(?s)__TT10_UART_IDENTITY_BEGIN__\s*(\{[^\r\n]+\})\s*__TT10_UART_IDENTITY_END__')
    if (-not $match.Success) { throw 'Structured UART identity response missing; no state-changing action' }
    $value=$match.Groups[1].Value | ConvertFrom-Json
    if ($value.machine_sha256 -ne 'ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec') { throw 'Registered machine identity differs; no recovery action' }
    [pscustomobject]@{Scope='AUTHENTICATED_UART_READ_ONLY_IDENTITY';Port=$Port;Device=$expected;CredentialsLogged=$false;UsedExistingShell=$UseExistingShell.IsPresent;Identity=$value} | ConvertTo-Json -Depth 5
} catch {
    [pscustomobject]@{Scope='UART_IDENTITY_REFUSED_NO_MUTATION';Phase=$phase;CredentialsLogged=$false} | ConvertTo-Json
    throw
} finally {
    $password=$null
    if ($serial.IsOpen) { $serial.Close() }
    $serial.Dispose()
}
