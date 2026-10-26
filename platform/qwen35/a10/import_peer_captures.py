"""Fixed offline import of four inspected UART files, verified before any write."""
import argparse
import hashlib
import json
from pathlib import Path
from peer_capture import payload


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--package", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads((args.package / "evidence/02_repaired_trial/consumed_bundle_manifest.json").read_text())
    received = []
    definitions = (
        ("uart_peer_executor_source_01.json", "run_refcount_step5.py", "run_refcount_step5.py", True),
        ("uart_peer_executor_source_01.json", "single_xrt_call.py", "single_xrt_call.py", True),
        ("uart_peer_results_01.json", "peer_actual_output", "actual_output.json", False),
        ("uart_peer_results_01.json", "peer_actual_golden", "golden.json", False),
    )
    for log, record_name, name, encoded in definitions:
        report = json.loads((args.evidence / log).read_text(encoding="utf-8-sig"))
        matches = [r for r in report["records"] if r["name"] == record_name]
        if len(matches) != 1 or report["closed"] is not True:
            raise ValueError("unexpected capture or port not released")
        if name == "actual_output.json":
            peer = (args.package / "evidence/02_repaired_trial/actual_output.json").read_bytes()
            size, sha = len(peer), hashlib.sha256(peer).hexdigest()
        else:
            entry = manifest["files"][name]
            size, sha = entry["bytes"], entry["sha256"]
        recovered = payload(matches[0], size, sha, encoded=encoded)
        received.append((name, recovered, log, sha))
    output = args.evidence / "received_board_files"
    output.mkdir(exist_ok=False)
    for name, data, _, _ in received:
        with (output / name).open("xb") as stream:
            stream.write(data)
    print(json.dumps(dict(domain="PC_CAPTURE_IMPORT_NOT_NEW_BOARD_TEST", board_access=False,
                          files=[dict(name=n, bytes=len(b), source_log=s, sha256=h)
                                 for n, b, s, h in received]), indent=2))


if __name__ == "__main__":
    main()
