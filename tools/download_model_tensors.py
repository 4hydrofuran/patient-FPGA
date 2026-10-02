# 固定官方revision的两份MLP权重切片下载，严格核对HTTP范围、dtype和尺寸。
from pathlib import Path
from urllib.request import Request, urlopen
import json
import struct
import hashlib
import array
import sys

# 默认写入本模块的向量目录，不依赖开发机器绝对路径。
root=Path(__file__).resolve().parents[1]/'vectors/model_source'
root.mkdir(parents=True,exist_ok=True)
revision='2fc06364715b967f1860aea9cf38778875588b17'
base=f'https://huggingface.co/Qwen/Qwen3.5-0.8B/resolve/{revision}/'
filename='model.safetensors-00001-of-00001.safetensors'

def fetch_range(first,last):
    req=Request(base+filename+f'?b01_range={first}-{last}',headers={'Range':f'bytes={first}-{last}','Cache-Control':'no-cache'})
    with urlopen(req,timeout=45) as response:
        expected=f'bytes {first}-{last}/1746942600'
        if response.status!=206 or response.headers.get('Content-Range')!=expected:
            raise RuntimeError(f'Range not honored: {response.status}, {response.headers.get("Content-Range")}')
        data=response.read(last-first+2)
        if len(data)!=last-first+1: raise RuntimeError('Wrong payload length')
        return data

prefix=fetch_range(0,7)
header_length=struct.unpack('<Q',prefix)[0]
if header_length>2_000_000: raise RuntimeError('Invalid safetensors header length')
header=fetch_range(8,header_length+7)
(root/'safetensors_header.json').write_bytes(header)
descriptors=json.loads(header)
records=[]
for kind,shape in [('gate_proj',[3584,1024]),('down_proj',[1024,3584])]:
    name=f'model.language_model.layers.0.mlp.{kind}.weight'
    descriptor=descriptors[name]
    if descriptor['shape']!=shape or descriptor['dtype']!='BF16': raise RuntimeError(f'Tensor mismatch: {descriptor}')
    first,last=descriptor['data_offsets']
    data=fetch_range(8+header_length+first,8+header_length+last-1)
    if len(data)!=shape[0]*shape[1]*2: raise RuntimeError('Tensor size mismatch')
    raw_path=root/f'{kind}.bf16.bin';raw_path.write_bytes(data)
    words=array.array('H');words.frombytes(data)
    if sys.byteorder!='little': words.byteswap()
    floats=array.array('I',(value<<16 for value in words))
    if sys.byteorder!='little': floats.byteswap()
    fp_path=root/f'{kind}.fp32.bin';fp_path.write_bytes(floats.tobytes())
    records.append({'tensor':name,'shape':shape,'dtype':'BF16','source_file':filename,'source_file_bytes':1746942600,'full_source_file_sha256':None,'data_offsets':descriptor['data_offsets'],'tensor_sha256':hashlib.sha256(data).hexdigest(),'raw_file':raw_path.name,'fp32_file':fp_path.name,'fp32_sha256':hashlib.sha256(fp_path.read_bytes()).hexdigest(),'conversion':'BF16 bits shifted left 16, no numeric approximation','activation_source':'synthetic_seeded_not_real_layer_activation'})
    print('Fetched',name,len(data),'bytes',flush=True)
for name in ['config.json','model.safetensors.index.json','LICENSE']:
    with urlopen(base+name,timeout=30) as response: data=response.read(2_000_001)
    if len(data)>2_000_000: raise RuntimeError('Metadata unexpectedly large')
    (root/name).write_bytes(data)
manifest={'model':'Qwen/Qwen3.5-0.8B','revision':revision,'method':'HTTP Range, exact Content-Range and length checked; no full model download','tensors':records,'scope':'Two layer-0 MLP tensors only; not 72 tensors, whole-model inference or teacher-forced activations.'}
(root/'source_manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print('Pinned source manifest written.',flush=True)
