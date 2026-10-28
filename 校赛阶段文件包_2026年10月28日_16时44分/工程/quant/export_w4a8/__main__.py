"""Export all 72 matrices from pinned raw BF16, one matrix in memory at a time."""
import argparse,hashlib,json,resource,struct,time
from pathlib import Path
import numpy as np
from .core import weights
ROOT=Path(__file__).resolve().parents[2]


def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()


def source_tensor(t):
    p=ROOT/'artifacts/qwen35-0.8b/source'/t['source_file']
    with p.open('rb') as f:
        hl=struct.unpack('<Q',f.read(8))[0];h=json.loads(f.read(hl))[t['source']]
        if h['shape']!=t['source_shape_NK'] or h['dtype']!='BF16' or h['data_offsets']!=t['data_offsets']:
            raise ValueError('Source header/map mismatch')
        if t['transpose_data'] or t['bias'] is not None or t['ggml_ne_KN']!=h['shape'][::-1]:
            raise ValueError('Unsupported orientation/bias')
        if 8+hl+h['data_offsets'][0]!=t['absolute_offset']:raise ValueError('Offset mismatch')
        f.seek(t['absolute_offset']);raw=f.read(h['data_offsets'][1]-h['data_offsets'][0])
    if hashlib.sha256(raw).hexdigest()!=t['source_tensor_sha256']:raise ValueError('Tensor source hash mismatch')
    return (np.frombuffer(raw,dtype='<u2').astype('<u4')<<16).view('<f4').reshape(t['source_shape_NK'])


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False)
    start=time.monotonic();lock=json.loads((ROOT/'models/model.lock.json').read_text());mapping=json.loads((ROOT/'quant/qwen35_tensor_map.json').read_text())
    if lock['revision']!=mapping['model_revision']:raise ValueError('Revision mismatch')
    source_names={t['source_file'] for t in mapping['mlp']}
    for name in source_names:
        rel='artifacts/qwen35-0.8b/source/'+name
        if sha(ROOT/rel)!=lock['source_files'][rel]['sha256']:raise ValueError('Original source file changed')
    if len(mapping['mlp'])!=72:raise ValueError('Expected 72 matrices')
    entries=[]
    for t in mapping['mlp']:
        w=source_tensor(t);packed,scales=weights(w);prefix=f"l{t['layer']:02d}_{t['op']}"
        files={}
        for suffix,raw,dtype in [('w.bin',packed,'uint8_packed_signed4'),('sw.bin',scales,'float32_le')]:
            name=prefix+'.'+suffix
            with (a.output/name).open('xb') as f:f.write(raw)
            files[suffix]={'file':name,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'dtype':dtype}
        n,k=t['source_shape_NK']
        entries.append({'id':prefix,'layer':t['layer'],'op':t['op'],'N':n,'K':k,'Np':n,'Kp':k,
            'G':k//128,'source_tensor':t['source'],'source_tensor_sha256':t['source_tensor_sha256'],
            'source_file':t['source_file'],'source_file_sha256':lock['source_files']['artifacts/qwen35-0.8b/source/'+t['source_file']]['sha256'],
            'source_dtype':'BF16','source_shape_NK':[n,k],'orientation':'Y=X@W.T; contiguous source [N,K]; no transpose',
            'bias':None,'padding_weight_code':0,'padding_scale':1,'files':files})
        del w,packed,scales
    total=sum(f['bytes'] for t in entries for f in t['files'].values())
    if total!=140378112:raise ValueError('Unexpected model byte count')
    manifest={'schema':'A_W4A8_SIDECAR_V1','contract':'SP_W4A8_128x32_V1','contract_sha256':json.loads((ROOT/'contracts/qwen35/contracts.lock').read_text())['contract_sha256'],
        'model':lock['model'],'source_revision':lock['revision'],'model_lock_sha256':sha(ROOT/'models/model.lock.json'),
        'tensor_map_sha256':sha(ROOT/'quant/qwen35_tensor_map.json'),'endian':'little',
        'weight_layout':'[N_tile32][K_group128][k_in_group][16_lane_pairs]; even_lane_low_nibble',
        'scale_layout':'[N_tile32][K_group128][lane32]',
        'precision':'BF16 losslessly promoted FP32; FP32 absmax/7 and w/scale; ties-to-even; FP32 scale underflow/nonfinite rejected; no epsilon/FTZ',
        'W_range':[-7,7],'A_range':[-127,127],'group_K':128,'tile_N':32,'zero_group_scale':1,
        'payload_bytes':total,'binary_header_bytes':0,'binary_alignment_bytes':0,'entries':entries,
        'producer':{x:sha(ROOT/x) for x in ['quant/export_w4a8/core.py','quant/export_w4a8/__main__.py']},
        'numpy':np.__version__,'license':lock['license'],'license_file':'artifacts/qwen35-0.8b/source/LICENSE',
        'vision_included':False,'MTP_included':False,'embedding_head':'Not exported; original shared embedding/head preserved in runtime',
        'runtime_download':False,'BOARD':'NOT_TESTED'}
    with (a.output/'manifest.json').open('x',encoding='utf-8') as f:json.dump(manifest,f,ensure_ascii=False,indent=2)
    print(json.dumps({'matrices':len(entries),'payload_bytes':total,'manifest_bytes':(a.output/'manifest.json').stat().st_size,
        'manifest_sha256':sha(a.output/'manifest.json'),'elapsed_s':time.monotonic()-start,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        'threads':1,'scope':'PC export not inference or board'}))
if __name__=='__main__':main()
