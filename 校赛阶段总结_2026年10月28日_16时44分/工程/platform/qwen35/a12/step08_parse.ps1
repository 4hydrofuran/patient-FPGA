$ErrorActionPreference='Stop'
$errorsFound=@();$files=@()
Get-ChildItem -LiteralPath $PSScriptRoot -Filter 'step08*.ps1' | ForEach-Object {
    $parseTokens=$null;$parseErrors=$null
    [void][System.Management.Automation.Language.Parser]::ParseFile($_.FullName,[ref]$parseTokens,[ref]$parseErrors)
    if($parseErrors){$errorsFound+=@($parseErrors)}
    $hasher=[Security.Cryptography.SHA256]::Create()
    try{$pin=([BitConverter]::ToString($hasher.ComputeHash([IO.File]::ReadAllBytes($_.FullName)))).Replace('-','').ToLowerInvariant()}
    finally{$hasher.Dispose()}
    $files+=@{path=$_.Name;sha256=$pin}
}
if($errorsFound.Count){$errorsFound;exit 1}
@{status='PASS_PARSE_ONLY_NO_BOARD_CONTACT';files=$files}|ConvertTo-Json -Depth 4
