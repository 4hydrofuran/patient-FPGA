"""Offline real ASR: fixed public development slice; preserve all results/errors."""
import argparse
import hashlib
import json
import os
import platform
import random
import statistics
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from voicec.client import Client
from voicec.metrics import cer,literal_key_items


def percentile(values,p):
    if not values: return None
    a=sorted(values); position=(len(a)-1)*p
    low=int(position); high=min(low+1,len(a)-1)
    return a[low]+(a[high]-a[low])*(position-low)


def summarize(rows):
    ok=[r for r in rows if r['status']=='SUCCESS']
    timings=[r['response']['compute_ms'] for r in ok]
    rtfs=[r['response']['compute_ms']/r['response']['audio_duration_ms'] for r in ok]
    first={r['recording_id']:r for r in ok if r['repeat']==0}
    quality=list(first.values())
    errors=sum(r['cer']['errors'] for r in quality)
    chars=sum(r['cer']['reference_chars'] for r in quality)
    key_summary={}
    for r in quality:
        for item in r['key_items']['items']:
            result=key_summary.setdefault(item['kind'],dict(items=0,failed=0))
            result['items']+=1;result['failed']+=not item['count_preserved']
    return dict(runs=len(rows),successes=len(ok),failures=len(rows)-len(ok),
        compute_ms_p50=percentile(timings,.5),compute_ms_p95=percentile(timings,.95),
        client_elapsed_ms_p95=percentile([r['client_elapsed_ms'] for r in ok],.95),
        rtf_p50=percentile(rtfs,.5),rtf_p95=percentile(rtfs,.95),
        peak_rss_bytes=max((r['response']['memory']['peak_rss_bytes'] for r in ok),default=None),
        observed_public_slice_cer=errors/chars if chars else None,reference_chars=chars,errors=errors,
        quality_distinct_audio_count=len(quality),key_items=key_summary,
        per_repeat_text_stable=all(len({r['response'].get('text') for r in ok if r['recording_id']==rid})==1 for rid in first),
        failure_policy='ALL_RUNS_RETAINED; CER_REPORTED_FOR_FIRST_REPEAT_SUCCESSFUL_AUDIO_WITH_COVERAGE',
        student_cer=None,human_semantic_critical_item_review='PENDING',
        scope='PRESELECTED_PUBLISHED_DEV_TRANSCRIPTS_NOT_LOCALLY_HUMAN_VERIFIED')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=ROOT/'evidence/c01/thread_comparison')
    args=p.parse_args()
    out=args.output;out.mkdir(parents=True,exist_ok=True)
    if (out/'raw.jsonl').exists(): raise RuntimeError('Preserve previous run; use a different output directory')
    audio_root=ROOT/'data/c01_public'
    manifest=[json.loads(s) for s in (audio_root/'manifest.jsonl').read_text(encoding='utf-8').splitlines()]
    schedule=[(repeat,i) for repeat in range(3) for i in range(len(manifest))]
    random.Random(20261002).shuffle(schedule)
    (out/'schedule.json').write_text(json.dumps(dict(seed=20261002,thread_order=[1,2,4],
        runs_per_thread=len(schedule),schedule=[dict(repeat=r,recording_id=manifest[i]['recording_id']) for r,i in schedule],
        warmup='ONE_FULL_DECODE_OF_FIRST_AUDIO_PER_FRESH_PROCESS_RECORDED_SEPARATELY',
        selection_policy='LOWEST_PC_P95_AMONG_ZERO_FAILURE_IDENTICAL_TRANSCRIPT_CANDIDATES; OTHERWISE_1_THREAD_PROVISIONAL',
        original_audio_sha256s={r['recording_id']:r['audio_sha256'] for r in manifest},
        platform=platform.platform(),cpu_count=os.cpu_count(),
        network='RUNTIME_DEFAULT_NETWORK_RESTRICTED_SANDBOX_LOCAL_ASSETS_NO_NETWORK_API; NOT_PHYSICAL_DISCONNECT'),indent=2)+'\n',encoding='utf-8')
    all_rows=[];warmups=[];hellos=[]
    with (out/'raw.jsonl').open('w',encoding='utf-8') as log:
        for threads in [1,2,4]:
            startup=time.perf_counter()
            with Client(audio_root,asr_config=ROOT/f'configs/asr.threads{threads}.json',response_timeout=60) as client:
                hello=client.call('hello')
                hellos.append(dict(threads=threads,client_startup_ms=(time.perf_counter()-startup)*1000,response=hello))
                if not hello['capabilities']['real_asr']: raise RuntimeError('Actual ASR not configured')
                first=manifest[0]
                warmups.append(dict(threads=threads,response=client.call('transcribe',session_id=first['recording_id'],
                    language='zh',wav_path=first['audio_path'])))
                for count,(repeat,i) in enumerate(schedule,1):
                    row=manifest[i];start=time.perf_counter()
                    record=dict(threads=threads,repeat=repeat,recording_id=row['recording_id'],
                        audio_sha256=row['audio_sha256'],reference_text=row['reference_text'],
                        source_kind=row['source_kind'],reference_status=row['transcript_status'])
                    try:
                        response=client.call('transcribe',session_id=row['recording_id'],language='zh',wav_path=row['audio_path'])
                        record.update(status='SUCCESS' if response['type']=='result' else 'ERROR',response=response)
                        if response['type']=='result':
                            if response['audio_sha256']!=row['audio_sha256']: raise RuntimeError('Input hash changed')
                            record.update(cer=cer(row['reference_text'],response['text']),
                                key_items=literal_key_items(row['reference_text'],response['text'],row['key_items']))
                    except Exception as exc:
                        record.update(status='TIMEOUT' if isinstance(exc,TimeoutError) else 'ERROR',
                            exception_type=type(exc).__name__,exception_message=str(exc),stderr=list(client.stderr))
                    record['client_elapsed_ms']=(time.perf_counter()-start)*1000
                    all_rows.append(record);log.write(json.dumps(record,ensure_ascii=False,allow_nan=False)+'\n');log.flush()
                    if count%5==0 or count==len(schedule): print('Thread',threads,'runs',count,'/',len(schedule),flush=True)
                if client.stderr:
                    (out/f'worker_threads{threads}.stderr.log').write_text(''.join(client.stderr),encoding='utf-8')
    write=lambda name,data:(out/name).write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    write('hello.json',hellos);write('warmups.json',warmups)
    summaries={str(t):summarize([r for r in all_rows if r['threads']==t]) for t in [1,2,4]}
    output_sets={t:{(r['repeat'],r['recording_id']):r.get('response',{}).get('text') for r in all_rows if r['threads']==t} for t in [1,2,4]}
    identical=output_sets[1]==output_sets[2]==output_sets[4]
    valid=[t for t in [1,2,4] if summaries[str(t)]['failures']==0]
    chosen=min(valid,key=lambda t:summaries[str(t)]['compute_ms_p95']) if identical and valid else 1
    write('report.json',dict(execution_kind='PC_REAL',input_kind='LICENSED_PUBLIC_RESTORED_SPEECH',
        synthetic_fixtures=0,own_student_recordings=0,models_compared=1,threads_compared=[1,2,4],
        runs_per_thread=len(schedule),summaries=summaries,identical_transcripts_across_threads=identical,
        selected_pc_threads=chosen,selection_scope='LOCAL_PC_DEVELOPMENT_PROVISIONAL_NOT_A53_OR_FINAL_QUALITY_ACCEPTANCE',
        student_quality='NOT_TESTED',student_cer=None,board='NOT_TESTED',
        onnx_export_license='REVIEW_PENDING',model_acceptance='NOT_GRANTED_BY_THIS_BENCHMARK',
        limitations=['Small preselected dev slice; no full dataset score',
            'Published transcripts not locally human verified; no medical semantic review',
            'Sequential thread blocks, shared host CPU and three repeats; exploratory PC timing only',
            'No student speakers/clinical conversation/noise/final test; own C00 plan remains uncollected',
            'No inverse text normalization: Arabic and Chinese numerals count as literal differences']))
    config=(ROOT/f'configs/asr.threads{chosen}.json').read_text(encoding='utf-8')
    (ROOT/'configs/asr.selected.json').write_text(config,encoding='utf-8')
    print('Selected PC threads:',chosen,'identical outputs:',identical,'failures:',sum(s['failures'] for s in summaries.values()),flush=True)
    if any(s['failures'] for s in summaries.values()): raise SystemExit(1)


if __name__=='__main__': main()
