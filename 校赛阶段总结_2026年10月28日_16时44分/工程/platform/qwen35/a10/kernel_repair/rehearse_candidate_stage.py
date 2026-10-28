"""PC-only exercise of the new staging extractor against the real pinned package."""
import json
from pathlib import Path
import platform
import stage_candidate_board as s

WORK = Path("/home/member-a/a10-kernel-full-20261019-v1")


if __name__ == "__main__":
    s.need(platform.machine() == "x86_64", "PC rehearsal only")
    source = WORK / "boot-candidate-v2"
    for name, (size, expected) in s.PINNED.items():
        p = source / name
        s.need(p.stat().st_size == size and s.digest(p) == expected, "Package pin")
    dest = WORK / "pc-stage-rehearsal-20261020-v1"
    result = s.unpack_modules(source / "modules.tar.gz", dest, s.Limiter(rate=10**10))
    s.need(s.digest(dest / "extra/zocl.ko") ==
           "2aa089c3967e8fa72480310fe2cc12aaa7d920135f5322d8596819835ca087cc", "Driver pin")
    result["status"] = "PASS_PC_REAL_PACKAGE_EXTRACT_AND_FULL_READBACK_NOT_BOARD"
    result["board_contact"] = False
    with (WORK / "pc-stage-rehearsal-20261020-v1.json").open("x") as f:
        json.dump(result, f, indent=2)
    print(json.dumps({k: v for k, v in result.items() if k != "readback_sha256"}))
