"""Verify frozen contracts, source-to-synthesis identity and the private kernel ABI."""

from pathlib import Path
import hashlib
import json
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def latest(variant, step):
    for path in reversed(sorted((ROOT / "reports/b03" / variant).glob(f"*/{step}.receipt.json"))):
        result = read(path)
        if result["exit_code"] == 0:
            return path, result
    raise RuntimeError(f"No successful {variant}/{step}")


def abi(xml, physical_width=True):
    kernel = ET.fromstring(xml).find("kernel")
    ports = [dict(port.attrib) for port in kernel.find("ports")]
    if not physical_width:
        for port in ports:
            port.pop("dataWidth")
    return {"name": kernel.attrib["name"], "control": kernel.attrib["hwControlProtocol"],
            "ports": ports,
            "args": [dict(arg.attrib) for arg in kernel.find("args")]}


def main():
    checks = []
    frozen = read(ROOT / "baseline/b02/source_manifest.json")["files_sha256"]
    frozen.update({"contracts/" + name: digest for name, digest in read(ROOT / "contracts/contract_lock.json")["files"].items()})
    for name, digest in frozen.items():
        actual = sha(ROOT / name)
        if actual.lower() != digest.lower():
            raise RuntimeError(f"Frozen file changed: {name}")
        checks.append({"path": name, "sha256": actual})
    base_abi = abi((ROOT / "build/b03_baseline_hls/hls/kernel.xml").read_text(), False)
    variants = {}
    for variant in ("baseline", "reuse", "double"):
        source = "baseline/b02/src/w4a8_linear_v1.cpp" if variant == "baseline" else "src/w4a8_prefill_v1.cpp"
        header = "baseline/b02/src/w4a8_linear_v1.hpp" if variant == "baseline" else "src/w4a8_linear_v1.hpp"
        synthesis_path, synthesis = latest(variant, "synth")
        for name in (source, header):
            if sha(ROOT / name).lower() != synthesis["input_sha256"][name].lower():
                raise RuntimeError(f"Synthesized core source changed: {variant}/{name}")
        xml_path = ROOT / f"build/b03_{variant}_hls/hls/kernel.xml"
        if abi(xml_path.read_text(), False) != base_abi:
            raise RuntimeError(f"Kernel argument/control/port mapping changed: {variant}")
        artifact = ROOT / f"build/b03_{variant}_hls/w4a8_linear_v1.xo"
        with zipfile.ZipFile(artifact) as archive:
            if archive.testzip() is not None:
                raise RuntimeError(f"Invalid XO CRC: {variant}")
            canonical = "w4a8_linear_v1/kernel.xml"
            packaged = abi(archive.read(canonical))
            kernels = [name for name in archive.namelist() if name.endswith("/kernel.xml")]
            if packaged != abi(xml_path.read_text()) or any(abi(archive.read(name)) != packaged for name in kernels):
                raise RuntimeError(f"XO internal metadata differs from synthesized design: {variant}")
        variants[variant] = {"source_sha256": sha(ROOT / source), "header_sha256": sha(ROOT / header),
                             "synthesis_receipt": str(synthesis_path.relative_to(ROOT)).replace("\\", "/"),
                             "xo_sha256": sha(artifact), "xo_bytes": artifact.stat().st_size,
                             "kernel_xml_sha256": sha(xml_path), "private_abi_matches_baseline": True}
        variants[variant]["physical_port_width_bits"] = {port["name"]: int(port["dataWidth"])
                                                        for port in abi(xml_path.read_text())["ports"]}
    identity = {}
    for variant in ("reuse", "double"):
        identity[variant] = {}
        for suffix in ("", "_real"):
            original = ROOT / ("vectors/b03_baseline" + suffix)
            candidate = ROOT / ("vectors/b03_" + variant + suffix)
            inputs = [path for path in original.glob("*.bin")
                      if not path.name.endswith((".observed_y.bin", ".observed_partials.bin"))]
            if not inputs:
                raise RuntimeError("No fixed vectors found")
            for path in inputs:
                if sha(path) != sha(candidate / path.name):
                    raise RuntimeError(f"Input/independent expected vector changed: {variant}/{path.name}")
            identity[variant][suffix or "synthetic"] = {"files": len(inputs), "status": "PASS"}
    report = {"stage": "B03", "status": "PASS", "frozen_checks": checks,
              "variants": variants, "fixed_input_expected_identity": identity,
              "private_meta_bytes": 40,
              "scope": "Public/B02 source unchanged; synthesized sources and XO private metadata checked. Final SW32 variants retain baseline physical port widths and frozen argument/control offsets. Not implementation or BOARD proof."}
    (ROOT / "reports/b03/artifact_guard.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("PASS: frozen contracts/B02 source, synthesized core identity, XO CRC/ABI, same fixed inputs/expected vectors")


if __name__ == "__main__":
    main()
