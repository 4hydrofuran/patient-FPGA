"""Record subprocess argv, cwd, exit code and complete output. Never shell=True."""
import argparse
import datetime
import json
import os
from pathlib import Path
import subprocess
import time

def run(argv, log, cwd=None, env=None):
    log = Path(log)
    if not argv:
        raise ValueError("Missing executable")
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    t = time.monotonic()
    log.parent.mkdir(parents=True, exist_ok=True)
    # Reserve BEFORE executing: O_EXCL via 'x' also rejects dangling symlinks.
    # A crash leaves a non-success reservation, never permission to run twice.
    with log.open("x", encoding="utf-8", newline="\n") as stream:
        base = dict(argv=argv, cwd=str(Path(cwd or os.getcwd()).resolve()), started_utc=started)
        stream.write(json.dumps(dict(base, status="RESERVED_NOT_COMPLETED", exit_code=None))+"\n")
        stream.flush()
        os.fsync(stream.fileno())
        try:
            p = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
            result = dict(base, elapsed_s=time.monotonic()-t,
                          exit_code=p.returncode, stdout=p.stdout, stderr=p.stderr)
        except OSError as exc:
            result = dict(base, elapsed_s=time.monotonic()-t, exit_code=127, error=str(exc))
        stream.seek(0)
        stream.write(json.dumps(result, indent=2, ensure_ascii=False)+"\n")
        stream.truncate()
        stream.flush()
        os.fsync(stream.fileno())
    print(json.dumps({"log":str(log), "exit_code":result["exit_code"]}))
    return result["exit_code"]

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", required=True)
    ap.add_argument("argv", nargs=argparse.REMAINDER)
    a = ap.parse_args()
    raise SystemExit(run(a.argv[1:] if a.argv[:1] == ["--"] else a.argv, a.log))
