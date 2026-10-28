"""Independent archive integrity and ARM64 ELF checks; never executes board code."""
import hashlib
import json
from pathlib import Path
import struct
import zipfile

root = Path(__file__).resolve().parents[4]
release = root / "release/kv260_user_acceptance_20261016_v1"
evidence = root / "evidence/board_platform/newboard_short_20261016_v1"
archive = release / "KV260_用户短时基础验收.zip"
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    names = z.namelist()
    assert len(names) == len(set(names))
    assert all(n.startswith("user_check/") and ".." not in Path(n).parts for n in names)
    manifest = json.loads(z.read("user_check/SHA256.json"))
    assert set(names) == {"user_check/" + n for n in manifest} | {"user_check/SHA256.json"}
    for name, expected in manifest.items():
        data = z.read("user_check/" + name)
        assert hashlib.sha256(data).hexdigest() == expected, name
        assert data == (release / "user_check" / name).read_bytes(), name
    elf = z.read("user_check/cpu_smoke_a53")
    assert elf[:6] == b"\x7fELF\x02\x01"
    assert struct.unpack_from("<H", elf, 18)[0] == 183, "Not AArch64"
    status = json.loads(z.read("user_check/BUILD_STATUS.json"))
    assert status["BOARD"] == status["FPGA"] == "NOT_TESTED"
result = {"domain": "PC_ARCHIVE_INSPECTION", "status": "PASS", "files": len(names),
          "elf": "ELF64_LITTLE_ENDIAN_AARCH64", "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
          "BOARD": "NOT_TESTED", "exit_code": 0}
(evidence / "package-verification.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps(result))
