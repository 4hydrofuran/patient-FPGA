"""Read actual safetensors/GGUF inventories and check every trunk MLP value."""
import collections
import hashlib
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "artifacts/qwen35-0.8b/source"
RUNTIME = ROOT / "platform/local/qwen35/llama.cpp-81e39ad34368329b5db77620721510fd91107e80"
sys.path.insert(0,str(RUNTIME / "gguf-py"))
import gguf
import numpy as np


def sha(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""):h.update(b)
    return h.hexdigest()


def save(p, obj):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("x",encoding="utf-8") as f:json.dump(obj,f,ensure_ascii=False,indent=2)


def excluded_tensor(name):
    return name.startswith(("v.", "mm.", "blk.24.")) or "nextn" in name


def trunk_mlp_bias(name):
    return name.startswith("model.language_model.layers.") and ".mlp." in name and name.endswith(".bias")


def main():
    cfg=json.loads((SRC/"config.json").read_text()); t=cfg["text_config"]
    assert (t["num_hidden_layers"],t["hidden_size"],t["intermediate_size"])==(24,1024,3584)
    assert collections.Counter(t["layer_types"])=={"linear_attention":18,"full_attention":6}
    assert t["tie_word_embeddings"] and cfg["tie_word_embeddings"]
    index=json.loads((SRC/"model.safetensors.index.json").read_text())["weight_map"]
    tensors={}; bases={}
    for name in set(index.values()):
        with (SRC/name).open("rb") as f:
            length=struct.unpack("<Q",f.read(8))[0]; header=json.loads(f.read(length))
        bases[name]=length+8
        tensors.update({k:v for k,v in header.items() if k!="__metadata__"})
    assert set(tensors)==set(index),"Index/header mismatch"
    boundary={"text":[],"vision":[],"mtp":[],"unknown":[]}
    for name,meta in sorted(tensors.items()):
        kind="text" if name.startswith("model.language_model.") else "vision" if name.startswith("model.visual.") else "mtp" if name.startswith("mtp.") else "unknown"
        boundary[kind].append({"name":name,**meta,"file":index[name]})
    assert not boundary["unknown"]
    reader=gguf.GGUFReader(str(ROOT/"artifacts/qwen35-0.8b/qwen35-text-f16.gguf"))
    converted={x.name:x for x in reader.tensors}
    # Vision namespaces are prefixes; substring 'v.' also matches text attn_v.
    assert not any(excluded_tensor(n) for n in converted)
    mapping=[];names=gguf.get_tensor_name_map(gguf.MODEL_ARCH.QWEN35,24)
    for layer in range(24):
        for op in ("gate","up","down"):
            name=f"model.language_model.layers.{layer}.mlp.{op}_proj.weight"; meta=tensors[name]
            shape=[1024,3584] if op=="down" else [3584,1024]
            assert meta["shape"]==shape and meta["dtype"]=="BF16"
            normalized=name.replace("language_model.","")
            mapped=names.get_name(normalized,try_suffixes=(".weight",))
            out=converted[mapped]
            assert out.shape.tolist()==shape[::-1]
            offset=bases[index[name]]+meta["data_offsets"][0]
            count=int(np.prod(shape))
            raw=np.memmap(SRC/index[name],mode="r",dtype="<u2",offset=offset,shape=(count,))
            source_f32=(raw.astype(np.uint32)<<16).view(np.float32)
            expected=source_f32.astype(np.float16)
            assert np.array_equal(out.data.reshape(-1),expected),"MLP conversion/layout differs: "+name
            mapping.append({"layer":layer,"op":op,"source":name,"source_file":index[name],
                            "source_shape_NK":shape,"dtype":"BF16","data_offsets":meta["data_offsets"],
                            "absolute_offset":offset,"gguf_name":mapped,"ggml_ne_KN":shape[::-1],
                            "graph_member":"ffn_"+op,"bias":None,"transpose_data":False,
                            "f16_elementwise_source_match":True,"source_tensor_sha256":hashlib.sha256(raw.tobytes()).hexdigest()})
    assert len(mapping)==72 and not any(trunk_mlp_bias(n) for n in tensors)
    assert "lm_head.weight" not in tensors and "token_embd.weight" in converted and "output.weight" not in converted
    paths=[p for p in SRC.iterdir() if p.is_file() and not p.name.endswith((".partial", ".tail", ".recovered"))]
    source_files={str(p.relative_to(ROOT)).replace("\\","/"):{"bytes":p.stat().st_size,"sha256":sha(p)} for p in paths}
    runtime_files=["convert_hf_to_gguf.py","conversion/qwen.py","conversion/base.py","gguf-py/gguf/tensor_mapping.py","src/models/qwen35.cpp","src/llama-memory-hybrid.cpp","src/llama-memory-recurrent.cpp","LICENSE"]
    lock={"model":"Qwen/Qwen3.5-0.8B","revision":"2fc06364715b967f1860aea9cf38778875588b17",
          "license":"Apache-2.0 (actual LICENSE retained)","mode":"text","enable_thinking":False,
          "runtime_commit":"81e39ad34368329b5db77620721510fd91107e80","runtime_license":"MIT",
          "source_files":source_files,"runtime_source_hashes":{p:sha(RUNTIME/p) for p in runtime_files},
          "runtime_archive_sha256":sha(RUNTIME.parent/"llama-81e39ad34368329b5db77620721510fd91107e80.tar.gz"),
          "converted_files":{},"converter_args":["--outtype","f16","--no-mtp"],
          "vision_exported":False,"mtp_exported":False,"board":"NOT_TESTED"}
    for name in ["qwen35-text-f16.gguf","qwen35-text-Q4_K_M.gguf"]:
        p=ROOT/"artifacts/qwen35-0.8b"/name
        if p.exists():lock["converted_files"][name]={"bytes":p.stat().st_size,"sha256":sha(p)}
    save(ROOT/"models/model.lock.json",lock)
    save(ROOT/"quant/qwen35_tensor_map.json",{"model_revision":lock["revision"],"mlp":mapping,"boundaries":boundary,
         "counts":{k:len(v) for k,v in boundary.items()},"shared_embedding_head":{"source":"model.language_model.embed_tokens.weight","dedicated_head_present":False,"runtime":"qwen35.cpp load_arch_tensors output falls back to token_embd TENSOR_DUPLICATED; no physical sharing assertion"},
         "graph":"build_layer_ffn: up, gate, down; SILU, PAR; no MLP bias",
         "gguf_tensor_count":len(converted),"validation":"PC source/header/index + all 72 MLP F16 elementwise matches"})
    print(json.dumps({"mlp":72,"counts":{k:len(v) for k,v in boundary.items()},"f16_layout":"PASS","board":"NOT_TESTED"}))


if __name__=="__main__":main()
