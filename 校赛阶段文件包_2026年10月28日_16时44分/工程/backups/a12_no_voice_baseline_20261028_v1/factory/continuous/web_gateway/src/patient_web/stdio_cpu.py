"""CPU mode for the board's existing Qwen executable, without a PL route."""

import json
import os
from pathlib import Path
import queue
import subprocess
import threading
import time

from jinja2.sandbox import ImmutableSandboxedEnvironment

from .engine import TextEngine


class BoardCPUModel:
    def __init__(self, bundle, output, asset_root="/opt/patient-qwen"):
        bundle, output, assets = Path(bundle), Path(output), Path(asset_root)
        output.mkdir(parents=True, exist_ok=False)
        self.broken = False
        self.trace_context = None
        self.count = 0
        self.messages = queue.Queue()
        self.template = (assets / "artifacts/qwen35-0.8b/source/chat_template.jinja").read_text(encoding="utf-8")
        self.env = ImmutableSandboxedEnvironment()
        def fail(message):
            raise ValueError(message)
        self.env.globals["raise_exception"] = fail
        environment = {k: v for k, v in os.environ.items()
                       if not k.startswith(("SP_A12", "SP_TT10", "GGML_", "OMP_"))}
        environment.update(LD_LIBRARY_PATH=str(bundle / "bin"), OMP_NUM_THREADS="2",
                           OPENBLAS_NUM_THREADS="1")
        self.stderr = (output / "stderr.txt").open("x", encoding="utf-8")
        self.log = (output / "stdout.jsonl").open("x", encoding="utf-8")
        self.p = subprocess.Popen([
            str(bundle / "bin/qwen35-a12"),
            str(assets / "artifacts/qwen35-0.8b/qwen35-text-Q4_K_M.gguf"),
            "2", "1024", "all", "TILED", "2", "8",
        ], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.stderr,
            text=True, encoding="utf-8", bufsize=1, env=environment)
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()
        self.ready = self._next(120)
        bridge = self.ready.get("bridge", {})
        if (self.ready.get("type") != "ready"
                or self.ready.get("execution_kind") != "CPU_REFERENCE"
                or bridge.get("execution_kind") != "CPU_REFERENCE"
                or bridge.get("weight_load_count") != 72):
            self.close()
            raise RuntimeError("Board CPU worker identity differs")

    def _read(self):
        try:
            for line in self.p.stdout:
                self.log.write(line)
                self.log.flush()
                self.messages.put(json.loads(line))
        finally:
            self.messages.put(None)

    def _next(self, timeout):
        try:
            result = self.messages.get(timeout=timeout)
        except queue.Empty:
            self.broken = True
            raise TimeoutError("CPU answer deadline exceeded")
        if result is None:
            self.broken = True
            raise RuntimeError("CPU worker exited")
        return result

    def generate(self, messages, timeout_s=180):
        if self.broken or self.p.poll() is not None:
            raise RuntimeError("CPU worker unavailable")
        self.count += 1
        context = self.trace_context
        rid = context["session_id"] + ":" + context["request_id"]
        prompt = self.env.from_string(self.template).render(
            messages=messages, add_generation_prompt=True, enable_thinking=False)
        request = dict(id=rid, prompt=prompt, max_tokens=24, logits_mode="final",
                       cache_policy="R0", prefill_chunk=256, profile=False,
                       diagnostic_report=False, session_id=context["session_id"],
                       session_epoch=context["epoch"])
        self.p.stdin.write(json.dumps(request, ensure_ascii=False) + "\n")
        self.p.stdin.flush()
        deadline = time.monotonic() + timeout_s
        while True:
            result = self._next(max(.001, deadline - time.monotonic()))
            if result.get("id") != rid:
                self.broken = True
                raise RuntimeError("CPU response identity differs")
            if result.get("type") == "error":
                raise RuntimeError(result.get("message", "CPU generation failed"))
            if result.get("type") == "result":
                if (result.get("bridge", {}).get("execution_kind") != "CPU_REFERENCE"
                        or result.get("state_cleared_before_response") is not True
                        or result.get("state_position_after_clear") != -1):
                    self.broken = True
                    raise RuntimeError("CPU response backend/state differs")
                return dict(result, actual_backend="CPU_REFERENCE")

    def close(self):
        if self.p.poll() is None:
            self.p.stdin.write('{"op":"shutdown"}\n')
            self.p.stdin.flush()
            self.p.wait(timeout=10)
        self.reader.join(timeout=2)
        self.p.stdin.close()
        self.p.stdout.close()
        self.stderr.close()
        self.log.close()


class BoardCPUEngine(TextEngine):
    def __init__(self, bundle, output, *, asset_root="/opt/patient-qwen", generation_timeout_s=180):
        super().__init__("demo", generation_timeout_s=generation_timeout_s)
        self.backend = "native"
        self.execution_kind = "CPU_REFERENCE"
        self.can_cancel = False
        self.model = BoardCPUModel(bundle, output, asset_root)

    # TextEngine's native health and normal close apply to this CPU-owned child.
