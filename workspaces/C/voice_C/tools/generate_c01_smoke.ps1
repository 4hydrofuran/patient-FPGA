$ErrorActionPreference = 'Stop'
$voiceRoot = Split-Path -Parent $PSScriptRoot
$fixtureRoot = Join-Path $voiceRoot 'data/c01_smoke'
$manifestPath = Join-Path $fixtureRoot 'manifest.jsonl'
if (Test-Path -LiteralPath $manifestPath) { throw 'Existing fixtures are frozen. Do not regenerate silently.' }
$null = New-Item -ItemType Directory -Path $fixtureRoot -Force
$plan = Get-Content -LiteralPath (Join-Path $voiceRoot 'data/recording_plan.jsonl') -Encoding UTF8 | ForEach-Object { $_ | ConvertFrom-Json }
$selected = $plan | Where-Object { $_.split -eq 'dev' -and $_.recording_id -match '\.0[12]$' }
$synth = New-Object -ComObject SAPI.SpVoice
$voices = $synth.GetVoices()
$chosen = $null
for ($i=0; $i -lt $voices.Count; $i++) {
    if ($voices.Item($i).GetDescription() -eq 'Microsoft Huihui Desktop - Chinese (Simplified)') { $chosen = $voices.Item($i) }
}
if ($null -eq $chosen) { throw 'Required locally installed Chinese SAPI voice unavailable' }
$synth.Voice = $chosen
$synth.Rate = 0
$synth.Volume = 100
$manifest = New-Object System.Collections.Generic.List[string]
try {
    foreach ($row in $selected) {
        $id = $row.recording_id.Replace('c00.dev.', 'c01.smoke.')
        $directory = Join-Path $fixtureRoot $id
        $null = New-Item -ItemType Directory -Path $directory -Force
        if (Test-Path -LiteralPath (Join-Path $directory 'in.wav')) { throw 'Existing audio must be preserved before retry' }
        $path = Join-Path $directory 'in.wav'
        $stream = New-Object -ComObject SAPI.SpFileStream
        try {
            $stream.Format.Type = 18 # SAPI 16 kHz PCM16 mono; independently checked by Python WAV reader.
            $stream.Open($path, 3, $false)
            $synth.AudioOutputStream = $stream
            $null = $synth.Speak($row.reference_text, 0)
        } finally { $stream.Close(); $null = [System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($stream) }
        $record = [ordered]@{
            recording_id = $id; audio_path = "$id/in.wav";
            audio_sha256 = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant();
            reference_text = $row.reference_text; key_items = @($row.key_items);
            category = $row.category; source_plan_id = $row.recording_id; split = 'dev';
            source_kind = 'SYNTHETIC_ENGINEERING'; transcript_status = 'SCRIPT_NOT_HUMAN_VERIFIED';
            generator = 'Windows SAPI / Microsoft Huihui Desktop';
            rate = 0; volume = 100; sample_rate = 16000;
            human_recording = $false; speaker_id = $null; consent_reference = $null;
            scope = 'LOCAL_ENGINEERING_ONLY_NOT_C02_TTS_NOT_REAL_STUDENT_QUALITY'
        }
        $manifest.Add(($record | ConvertTo-Json -Depth 8 -Compress))
        Write-Output "Generated synthetic fixture $id"
    }
} finally { $null = [System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($synth) }
[System.IO.File]::WriteAllLines($manifestPath, $manifest, (New-Object System.Text.UTF8Encoding($false)))
