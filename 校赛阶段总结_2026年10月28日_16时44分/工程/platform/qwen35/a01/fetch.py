"""Fetch only pinned public upstream assets; no login or global cache changes."""
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[3]
REV = "2fc06364715b967f1860aea9cf38778875588b17"
COMMIT = "81e39ad34368329b5db77620721510fd91107e80"
DEST = ROOT / "artifacts/qwen35-0.8b/source"


def digest(p):
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""): h.update(b)
    return h.hexdigest()


def get(url, path):
    if path.exists():
        print("EXISTS", path.name, path.stat().st_size, flush=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_suffix(path.suffix + ".partial")
    # Each attempt preserves a prior incomplete download instead of overwriting it.
    if part.exists(): raise RuntimeError("Preserve partial; inspect before retry: " + str(part))
    req = urllib.request.Request(url, headers={"User-Agent": "KV260-A01-public-audit"})
    with urllib.request.urlopen(req, timeout=120) as response, part.open("xb") as f:
        expected = response.headers.get("Content-Length")
        for b in iter(lambda: response.read(1024 * 1024), b""): f.write(b)
    if expected is not None and part.stat().st_size != int(expected): raise ValueError("Incomplete response")
    part.rename(path)
    print("DOWNLOADED", path.name, path.stat().st_size, flush=True)


def main():
    import argparse
    p = argparse.ArgumentParser(); p.add_argument("part", choices=["metadata", "weight", "runtime"]); a = p.parse_args()
    base = f"https://huggingface.co/Qwen/Qwen3.5-0.8B/resolve/{REV}/"
    if a.part == "runtime":
        get(f"https://codeload.github.com/ggml-org/llama.cpp/tar.gz/{COMMIT}", ROOT / f"platform/local/qwen35/llama-{COMMIT}.tar.gz")
    elif a.part == "metadata":
        for name in ["README.md", "LICENSE", "config.json", "model.safetensors.index.json", "tokenizer.json", "tokenizer_config.json", "chat_template.jinja", "vocab.json", "merges.txt"]:
            get(base + name, DEST / name)
        get(f"https://huggingface.co/api/models/Qwen/Qwen3.5-0.8B/revision/{REV}?blobs=true", DEST / "upstream_api.json")
    else:
        index = json.loads((DEST / "model.safetensors.index.json").read_text())
        api = json.loads((DEST / "upstream_api.json").read_text())
        for name in sorted(set(index["weight_map"].values())):
            get(base + name, DEST / name)
            item = next(s for s in api["siblings"] if s["rfilename"] == name)
            expected = item["lfs"]["sha256"]
            actual = digest(DEST / name)
            if actual != expected: raise ValueError("Upstream LFS SHA mismatch")
            print("LFS_SHA256_VERIFIED", actual, flush=True)


if __name__ == "__main__": main()
