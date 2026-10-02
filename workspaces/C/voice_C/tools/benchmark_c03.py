"""42 unpaced incremental runs plus 14 wall-clock paced public development replays."""
import hashlib,json,random,shutil,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from voicec.audio import read_pcm16
from voicec.client import Client
from voicec.metrics import cer
from tools.benchmark_c02 import percentile


def stats(values):return dict(count=len(values),p50=percentile(values,.5),p95=percentile(values,.95),max=max(values,default=None))


def replay(c,spool,sid,pcm,paced=False,extra_silence_ms=0):
    begin=c.call('asr_begin',session_id=sid,sample_rate=16000,channels=1,format='pcm_s16le')
    if begin['type']!='result':raise RuntimeError(begin)
    stream=begin['stream_id'];chunks=[];partials=[];start=time.perf_counter()
    source_pcm=pcm;pcm+=b'\0\0'*round(16*extra_silence_ms)
    for seq,offset in enumerate(range(0,len(pcm),6400)):
        raw=pcm[offset:offset+6400];target_ms=(offset+len(raw))/32
        if paced:
            remaining=start+target_ms/1000-time.perf_counter()
            if remaining>0:time.sleep(remaining)
        sent=time.perf_counter();path=spool/sid/'chunk.pcm';path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
        ack=c.call('asr_push',stream_id=stream,seq=seq,pcm_path=sid+'/chunk.pcm',final=offset+6400>=len(pcm))
        elapsed=(time.perf_counter()-sent)*1000
        if ack['type']!='result' or not ack['ack']:raise RuntimeError(ack)
        if ack['chunk_sha256']!=hashlib.sha256(raw).hexdigest():raise RuntimeError('Chunk hash mismatch')
        path.unlink() # Only after consumed ACK.
        events=c.drain_events();partials.extend(e for e in events if e.get('event')=='partial')
        chunks.append(dict(seq=seq,frames=len(raw)//2,scheduled_audio_end_ms=target_ms,
            actual_send_ms=(sent-start)*1000,ack_elapsed_ms=elapsed,response=ack))
    input_end=time.perf_counter();final=c.call('asr_finish',stream_id=stream);received=time.perf_counter()
    if final['type']!='result' or not final.get('final'):raise RuntimeError(final)
    if final['pcm_sha256']!=hashlib.sha256(pcm).hexdigest() or final['frames']!=len(pcm)//2:
        raise RuntimeError('Input lost, duplicated or changed')
    return dict(status='SUCCESS',pacing='AUDIO_WALL_CLOCK_200MS' if paced else 'UNPACED_INCREMENTAL_NOT_REALTIME',
        final=final,chunks=chunks,partial_count=len(partials),partials=partials,
        source_pcm_sha256=hashlib.sha256(source_pcm).hexdigest(),submitted_pcm_sha256=hashlib.sha256(pcm).hexdigest(),
        explicit_appended_silence_ms=extra_silence_ms,finish_to_final_ms=(received-input_end)*1000,
        stream_wall_ms=(received-start)*1000,input_end_to_audio_schedule_ms=(input_end-start)*1000-len(pcm)/32,
        rtf=final['stream_compute_ms']/final['audio_duration_ms'],
        max_send_lag_ms=max((r['actual_send_ms']-r['scheduled_audio_end_ms'] for r in chunks),default=0) if paced else None,
        endpoint_advice_audio_ms=[r['response']['audio_duration_ms'] for r in chunks if r['response']['endpoint_detected']],
        quality_acceptance=False,microphone=False)


def main():
    out=ROOT/'evidence/c03/benchmark';out.mkdir(parents=True,exist_ok=True)
    if (out/'raw.jsonl').exists():raise RuntimeError('Preserve previous evidence')
    sources=[json.loads(s) for s in (ROOT/'data/c01_public/manifest.jsonl').read_text(encoding='utf-8').splitlines()]
    historical=[json.loads(s) for s in (ROOT/'evidence/c01/thread_comparison/raw.jsonl').read_text(encoding='utf-8').splitlines()]
    expected={r['recording_id']:r['response']['text'] for r in historical if r['status']=='SUCCESS'}
    schedule=[(r,i) for r in range(3) for i in range(14)];random.Random(20261003).shuffle(schedule)
    paced=list(range(14));random.Random(20261004).shuffle(paced)
    (out/'schedule.json').write_text(json.dumps(dict(seed=20261003,unpaced_schedule=schedule,paced_order=paced,
        input_source='C01_PRESELECTED_PUBLISHED_DEV_NOT_LOCALLY_HUMAN_VERIFIED',chunks_ms=200,
        paced_policy='FIRST_CHUNK_AFTER_200MS_OF_CAPTURE_TIME; NO_FASTER_THAN_AUDIO_WALL_CLOCK',
        final_trigger='EXPLICIT_AFTER_INPUT_END',microphone='NOT_AUTHORIZED_NOT_OPENED',
        limits='Paced 14-run descriptive sample, not 30-run final acceptance; end latency starts after supplied file end, not labeled speech end.',
        endpoint_policy='ADVISORY_NO_AUTOFINAL_NO_RESET_NO_TRIM',final_dataset_used=False),indent=2)+'\n',encoding='utf-8')
    all_rows=[];hellos=[]
    for mode,order in [('unpaced',schedule),('paced',[(0,i) for i in paced])]:
        with tempfile.TemporaryDirectory(prefix='c03-bench-') as tmp,(out/f'{mode}.trace.jsonl').open('w',encoding='utf-8') as trace,(out/'raw.jsonl').open('a',encoding='utf-8') as log:
            spool=Path(tmp)
            def record(item):trace.write(json.dumps(item,ensure_ascii=False)+'\n');trace.flush()
            startup=time.perf_counter()
            with Client(spool,asr_config=ROOT/'configs/asr.selected.json',stream_config=ROOT/'configs/stream.selected.json',response_timeout=60,trace_callback=record) as c:
                hellos.append(dict(mode=mode,startup_ms=(time.perf_counter()-startup)*1000,response=c.call('hello')))
                first=sources[0];(spool/'warm').mkdir();shutil.copyfile(ROOT/'data/c01_public'/first['audio_path'],spool/'warm/in.wav')
                warm=c.call('transcribe',session_id='warm',language='zh',wav_path='warm/in.wav')
                (out/f'{mode}.warmup.json').write_text(json.dumps(warm,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
                for n,(repeat,i) in enumerate(order,1):
                    source=sources[i];info,pcm=read_pcm16(ROOT/'data/c01_public'/source['audio_path'],asr=True)
                    sid=source['recording_id'];row=dict(mode=mode,repeat=repeat,recording_id=sid,source_audio_sha256=info['audio_sha256'])
                    try:
                        row.update(replay(c,spool,sid,pcm,paced=mode=='paced'))
                        row.update(reference_text=source['reference_text'],reference_status=source['transcript_status'],
                            c01_whole_wav_text=expected[sid],same_as_c01=row['final']['text']==expected[sid],
                            diagnostic_cer=cer(source['reference_text'],row['final']['text']))
                    except Exception as exc:
                        row.update(status='TIMEOUT' if isinstance(exc,TimeoutError) else 'ERROR',error_type=type(exc).__name__,message=str(exc))
                        c.call('reset',session_id=sid)
                    all_rows.append(row);log.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n');log.flush()
                    print(mode,n,'/',len(order),sid,row['status'],flush=True)
                (out/f'{mode}.stderr.log').write_text(''.join(c.stderr),encoding='utf-8')
    summaries={}
    for mode in ('unpaced','paced'):
        runs=[r for r in all_rows if r['mode']==mode];ok=[r for r in runs if r['status']=='SUCCESS']
        summaries[mode]=dict(runs=len(runs),successes=len(ok),failures=len(runs)-len(ok),same_as_c01=sum(r['same_as_c01'] for r in ok),
            rtf=stats([r['rtf'] for r in ok]),finish_to_final_ms=stats([r['finish_to_final_ms'] for r in ok]),
            chunk_ack_ms=stats([a['ack_elapsed_ms'] for r in ok for a in r['chunks']]),
            peak_rss_bytes=max((r['final']['memory']['peak_rss_bytes'] for r in ok),default=None),
            total_pcm_chunks=sum(len(r['chunks']) for r in ok),partial_events=sum(r['partial_count'] for r in ok),
            max_send_lag_ms=max((r['max_send_lag_ms'] for r in ok if r['max_send_lag_ms'] is not None),default=None),
            native_endpoint_before_input_end=sum(any(ms<r['final']['audio_duration_ms']-200 for ms in r['endpoint_advice_audio_ms']) for r in ok),
            final_quality_acceptance=False,student_cer=None,microphone=False)
    (out/'report.json').write_text(json.dumps(dict(status='PC_STREAMING_ENGINEERING_MEASURED',summaries=summaries,
        total_runs=len(all_rows),endpoint_policy='EARLY_ADVICE_NEVER_FINALIZES_OR_DISCARDS_INPUT',
        physical_audio_devices='NOT_OPENED',human_speech_end_labels=None,actual_audible_latency=None,
        board='NOT_TESTED',license='REVIEW_PENDING'),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (out/'hello.json').write_text(json.dumps(hellos,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('C03 replay completed',len(all_rows),'runs',flush=True)


if __name__=='__main__':main()
