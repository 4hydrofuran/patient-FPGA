"""Native CPU integration tests. Each run gets a fresh immutable evidence directory."""
import argparse
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import time
from jinja2.sandbox import ImmutableSandboxedEnvironment

ROOT=Path(__file__).resolve().parents[2]
TEMPLATE=ROOT/"artifacts/qwen35-0.8b/source/chat_template.jinja"


def render(messages):
    env=ImmutableSandboxedEnvironment()
    def fail(message): raise ValueError(message)
    env.globals["raise_exception"]=fail
    text=env.from_string(TEMPLATE.read_text()).render(messages=messages,add_generation_prompt=True,enable_thinking=False)
    assert text.endswith("<think>\n\n</think>\n\n")
    return text


class Native:
    def __init__(self, binary, model, out, name, profile=False):
        self.err=(out/(name+".stderr.txt")).open("x")
        self.raw=(out/(name+".jsonl")).open("x")
        argv=[str(binary),str(model),"4","4096"] + (["--profile-nodes"] if profile else [])
        self.p=subprocess.Popen(argv,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.err,text=True,bufsize=1)
        self.ready=self.read();assert self.ready["type"]=="ready"
    def read(self):
        # Native emits newline-terminated messages; no timer/metrics are inferred from a mock.
        line=self.p.stdout.readline()
        if not line:raise RuntimeError("Native process ended: "+str(self.p.poll()))
        self.raw.write(line);self.raw.flush();return json.loads(line)
    def request(self, req, cancel_after=None):
        self.raw.write(json.dumps({"request":req},ensure_ascii=False)+"\n");self.raw.flush()
        self.p.stdin.write(json.dumps(req,ensure_ascii=False)+"\n");self.p.stdin.flush()
        events=[];sent=None
        while True:
            r=self.read();events.append(r)
            if r["type"]=="token" and cancel_after is not None and r["index"]==cancel_after:
                sent=time.monotonic();os.kill(self.p.pid,signal.SIGUSR1)
            if r["type"] in {"result","tokens","reset","error"}:
                if sent is not None:r["cancel_observed_ms"]=(time.monotonic()-sent)*1000
                return r
    def close(self):
        if self.p.poll() is None:
            self.p.stdin.write('{"op":"shutdown"}\n');self.p.stdin.flush()
            self.p.wait(timeout=30)
        self.raw.close();self.err.close()
        if self.p.returncode!=0:raise RuntimeError("Native exit "+str(self.p.returncode))


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--model",type=Path,required=True);ap.add_argument("--output",type=Path,required=True)
    ap.add_argument("--binary",type=Path,default=Path("/home/member-a/qwen35-a01/native-build/qwen35-cpu"));a=ap.parse_args()
    a.output.mkdir(parents=True,exist_ok=False)
    n=Native(a.binary,a.model,a.output,"main"); results=[];failures=[]
    def check(condition,label):
        if not condition:failures.append(label)
    try:
        simple=[{"role":"user","content":"只回答数字：2加3等于多少？"}]
        prompt=render(simple)
        base=n.request({"id":"tokenize","op":"tokenize","prompt":prompt})["tokens"]
        pad=n.request({"id":"padding","op":"tokenize","prompt":"资料"})["tokens"][-1]
        for length in (256,1024,2048):
            tokens=base[:3]+[pad]*(length-len(base))+base[3:]
            r=n.request({"id":f"context-{length}","op":"generate","tokens":tokens,"max_tokens":32})
            results.append(r);check(r.get("status")=="OK" and r["prompt_tokens"]==length,f"context {length}")
            check("<think>" not in r.get("text","") and "</think>" not in r.get("text",""),f"unexpected generated thinking {length}")
        fresh=n.request({"id":"baseline-probe","prompt":prompt,"max_tokens":32});results.append(fresh)
        secret=[{"role":"user","content":"请记住本次会话的代号是青松。只回答已记住。"}]
        first=n.request({"id":"multi-1","prompt":render(secret),"max_tokens":32});results.append(first)
        secret += [{"role":"assistant","content":first["text"]},{"role":"user","content":"刚才的代号是什么？只回答代号。"}]
        second=n.request({"id":"multi-2","prompt":render(secret),"max_tokens":32});results.append(second)
        check("青松" in second.get("text",""),"multi-turn recall")
        check(n.request({"id":"reset","op":"reset"})["type"]=="reset","explicit reset")
        after=n.request({"id":"after-reset","prompt":prompt,"max_tokens":32});results.append(after)
        check(after.get("output_tokens")==fresh.get("output_tokens") and after.get("last_prompt_logits_fnv64")==fresh.get("last_prompt_logits_fnv64"),"reset isolation")
        cancel=n.request({"id":"cancel","prompt":render([{"role":"user","content":"从1开始按顺序列出所有整数直到10000，不要省略。"}]),"max_tokens":1024},cancel_after=2)
        results.append(cancel);check(cancel.get("status")=="CANCELLED" and cancel.get("partial_output_usable") is False,"real signal cancellation")
        post=n.request({"id":"after-cancel","prompt":prompt,"max_tokens":32});results.append(post)
        check(post.get("output_tokens")==fresh.get("output_tokens") and post.get("last_prompt_logits_fnv64")==fresh.get("last_prompt_logits_fnv64"),"post-cancel isolation")
        bad=n.request({"id":"bad-size","tokens":[pad]*4096,"max_tokens":2});check(bad["type"]=="error","reject overflow")
    finally:n.close()
    m=Native(a.binary,a.model,a.output,"fresh-process")
    try:
        other=m.request({"id":"fresh-process","prompt":prompt,"max_tokens":32});results.append(other)
        check(other.get("output_tokens")==fresh.get("output_tokens") and other.get("last_prompt_logits_fnv64")==fresh.get("last_prompt_logits_fnv64"),"fresh-process repeatability")
    finally:m.close()
    for r in results:
        if r.get("status")=="OK":
            check("<think>" not in r.get("text","") and "</think>" not in r.get("text",""),"no generated thinking "+r["id"])
    summary={"domain":"PC","model":str(a.model),"ready":n.ready,"results":results,"failures":failures,
             "status":"PASS" if not failures else "FAIL","board":"NOT_TESTED","sampling":"greedy, deterministic; not a quality benchmark",
             "context_method":"exact token padding inserted after user role prefix; synthetic load, not medical content",
             "memory_method":"Linux per-process ru_maxrss high-water KiB; cumulative within process; mmap model load, not cold-disk latency",
             "ttft_method":"native prefill start to first greedy sample; does not hide generated tokens; excludes model load, reset and prompt rendering",
             "session_method":"model stays loaded, full memory_clear(true) and history replay each request; no incremental-cache optimization"}
    with (a.output/"summary.json").open("x") as f:json.dump(summary,f,ensure_ascii=False,indent=2)
    print(json.dumps({"status":summary["status"],"failures":failures,"output":str(a.output)}))
    return bool(failures)


if __name__=="__main__":raise SystemExit(main())
