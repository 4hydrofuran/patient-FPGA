"""Snapshot passive UART files; preserve raw bytes and mark live capture as partial."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path


def snapshot(source, output):
    source, output = Path(source), Path(output)
    # Reserve a fresh output. Never replace earlier observations.
    output.mkdir(parents=True, exist_ok=False)
    manifest = {
        "captured_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source": str(source.resolve()),
        "scope": "Host snapshot, files read sequentially; not an atomic capture seal",
        "files": [],
        "board_compute_status": "NOT_TESTED",
    }
    for name in ("COM4.bin", "COM3.bin", "events.jsonl"):
        data = (source / name).read_bytes()
        destination = output / name
        with destination.open("xb") as stream:
            stream.write(data)
        digest = hashlib.sha256(data).hexdigest()
        assert hashlib.sha256(destination.read_bytes()).hexdigest() == digest
        manifest["files"].append({"name": name, "bytes": len(data), "sha256": digest})
        if name.endswith(".bin"):
            with (output / (name + ".txt")).open("x", encoding="utf-8", newline="") as stream:
                stream.write(data.decode("utf-8", errors="replace"))
    events_data = (output / "events.jsonl").read_bytes()
    lines = events_data.splitlines(keepends=True)
    records = [json.loads(line) for line in lines if line.endswith(b"\n")]
    manifest["incomplete_event_tail_preserved"] = bool(lines and not lines[-1].endswith(b"\n"))
    manifest["capture_end_observed"] = any(row.get("event") == "end" for row in records)
    manifest["complete_event_records"] = len(records)
    with (output / "SNAPSHOT.json").open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("output")
    args = parser.parse_args()
    snapshot(args.source, args.output)
