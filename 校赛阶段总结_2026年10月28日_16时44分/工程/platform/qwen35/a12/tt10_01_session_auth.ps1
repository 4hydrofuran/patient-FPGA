# Session-only same-user credential broker; no credential in files/argv/env.
$ErrorActionPreference='Stop'
Write-Host 'SESSION_AUTH_WAITING_PRIVATE_INPUT'
$secret=[Security.SecureString]::new()
while($true){
    $key=[Console]::ReadKey($true)
    if($key.Key -eq [ConsoleKey]::Enter){break}
    if($key.Key -eq [ConsoleKey]::Backspace){if($secret.Length){$secret.RemoveAt($secret.Length-1)};continue}
    if(-not [char]::IsControl($key.KeyChar)){$secret.AppendChar($key.KeyChar)}
}
if(-not $secret.Length){throw 'Empty session credential'}
$secret.MakeReadOnly()
$watch=[Diagnostics.Stopwatch]::StartNew();$count=0
Write-Host 'SESSION_AUTH_READY_NO_CREDENTIAL_LOGGED'
try{
    while($watch.Elapsed.TotalSeconds -lt 3600){
        $pipe=[IO.Pipes.NamedPipeServerStream]::new('PatientQwenTT10Window02Auth',[IO.Pipes.PipeDirection]::Out,1,[IO.Pipes.PipeTransmissionMode]::Byte,([IO.Pipes.PipeOptions]::Asynchronous -bor [IO.Pipes.PipeOptions]::CurrentUserOnly))
        try{
            $pending=$pipe.WaitForConnectionAsync()
            while(-not $pending.Wait(1000)){if($watch.Elapsed.TotalSeconds -ge 3600){break}}
            if(-not $pipe.IsConnected){break}
            $ptr=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
            try{
                $value=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
                $writer=[IO.StreamWriter]::new($pipe,[Text.UTF8Encoding]::new($false));$writer.WriteLine($value);$writer.Flush()
                $value=$null;$count++
            }finally{[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)}
        }finally{$pipe.Dispose()}
    }
}finally{$secret.Dispose();Write-Host ('SESSION_AUTH_CLOSED_REQUESTS='+$count)}
