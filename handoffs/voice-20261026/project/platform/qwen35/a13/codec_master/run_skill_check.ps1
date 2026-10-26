$ErrorActionPreference = 'Stop'
$a13SkillOriginal = 'C:/Users/Fang/.codex/skills/verilog-generator'
$a13SkillCopy = 'C:/Patientqwen/local/vg'
if (Test-Path -LiteralPath $a13SkillCopy) { throw 'Isolated skill copy already exists' }
Copy-Item -LiteralPath $a13SkillOriginal -Destination $a13SkillCopy -Recurse -ErrorAction Stop
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PATH = 'C:/Patientqwen/local/a13-doc-runtime/node-v22.16.0-win-x64;C:/Patientqwen/local/a13-doc-runtime/npm-global;' + $env:PATH
$env:NPM_CONFIG_PREFIX = 'C:/Patientqwen/local/a13-doc-runtime/npm-global'
& 'D:/Python/Python314/python.exe' -B "$a13SkillCopy/scripts/python/validation/validate_verilog_skill.py" --settings "$a13SkillCopy/config/defaults.json" --no-require-remote
exit $LASTEXITCODE
