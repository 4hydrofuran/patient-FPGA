"""Real persistent TTS, frozen development texts; retain every run and waveform."""
import argparse,hashlib,json,os,platform,random,shutil,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from voicec.client import Client
from voicec.audio import inspect_wav


def percentile(values,p):
    if not values: return None
    a=sorted(values);position=(len(a)-1)*p;lo=int(position);hi=min(lo+1,len(a)-1)
    return a[lo]+(a[hi]-a[lo])*(position-lo)


def summarize(rows):
    ok=[r for r in rows if r['status']=='SUCCESS']
    result=dict(runs=len(rows),successes=len(ok),failures=len(rows)-len(ok),
        timeouts=sum(r['status']=='TIMEOUT' for r in rows),
        peak_rss_bytes=max((r['response']['memory']['peak_rss_bytes'] for r in ok),default=None),
        silence_count=sum(r['response']['silent'] for r in ok),
        clipped_audio_count=sum(r['response']['clipped_samples']>0 for r in ok),
        float_clipped_samples=sum(r['response']['float_out_of_range_samples'] for r in ok),
        intelligibility=None,naturalness=None,negation_errors=None,number_errors=None,omissions=None,
        human_review='PENDING',audible_ms=None,board='NOT_TESTED')
    measurements={k:[r['response'][k] for r in ok] for k in ('compute_ms','ready_ms','audio_duration_ms','first_internal_chunk_ms')}
    measurements['client_elapsed_ms']=[r['client_elapsed_ms'] for r in ok]
    measurements['rtf']=[r['response']['compute_ms']/r['response']['audio_duration_ms'] for r in ok]
    measurements['single_sentence_client_ready_ms']=[r['client_elapsed_ms'] for r in ok if r['sentence_count']==1]
    for k,values in measurements.items():
        values=[v for v in values if v is not None]
        result[k]=dict(count=len(values),p50=percentile(values,.5),p95=percentile(values,.95),max=max(values,default=None))
    result['first_internal_chunk_is_playable']=False
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'evidence/c02/benchmark_final')
    out=parser.parse_args().output
    out.mkdir(parents=True,exist_ok=True)
    if (out/'raw.jsonl').exists(): raise RuntimeError('Never overwrite previous runs')
    scripts=[json.loads(s) for s in (ROOT/'data/c02_scripts/manifest.jsonl').read_text(encoding='utf-8').splitlines()]
    schedule=[(repeat,i) for repeat in range(3) for i in range(len(scripts))]
    random.Random(20261002).shuffle(schedule)
    (out/'schedule.json').write_text(json.dumps(dict(seed=20261002,primary_config_order=['threads1.batch1','threads2.batch1','threads4.batch1'],
        schedule=[dict(repeat=r,script_id=scripts[i]['script_id']) for r,i in schedule],
        selection_policy='LOWEST_COMPUTE_P95_ZERO_FAILURE; NO_HUMAN_QUALITY_ACCEPTANCE',
        paired_native_batch2='SAME_TWO_SENTENCE_TEXTS_THREE_REPEATS_SELECTED_THREADS; EXPLORATORY',
        warmup='ONE_EXTRA_FULL_SYNTHESIS_PER_FRESH_PROCESS_RETAINED_SEPARATELY',
        platform=platform.platform(),cpu_count=os.cpu_count(),speed=1.0,gain=1.0,waveform_cache=False,
        network='LOCAL_ASSETS_DEFAULT_NETWORK_RESTRICTED_SANDBOX_NOT_PHYSICAL_DISCONNECT'),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    all_rows=[];hellos=[];warmups=[];summaries={}

    def run_config(config_name,chosen_schedule,log):
        rows=[]
        with tempfile.TemporaryDirectory(prefix='c02-bench-') as tmp:
            spool=Path(tmp);startup=time.perf_counter()
            with Client(spool,tts_config=ROOT/f'configs/tts.{config_name}.json',response_timeout=60) as client:
                hello=client.call('hello');hellos.append(dict(config=config_name,startup_ms=(time.perf_counter()-startup)*1000,response=hello))
                if not hello['capabilities']['real_tts']: raise RuntimeError('Real TTS not configured')
                warm=client.call('synthesize',session_id='warm',text=scripts[0]['text'],output_dir='warm/out')
                warmups.append(dict(config=config_name,response=warm))
                if warm['type']!='result': raise RuntimeError('Warmup failed; see response')
                target=out/'audio'/config_name/'warmup.wav';target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(spool/warm['wav_path'],target)
                for n,(repeat,index) in enumerate(chosen_schedule,1):
                    script=scripts[index];start=time.perf_counter()
                    row=dict(config=config_name,repeat=repeat,script_id=script['script_id'],text_sha256=script['text_sha256'],
                        category=script['category'],sentence_count=script['sentence_count'],source_kind=script['source_kind'])
                    try:
                        response=client.call('synthesize',session_id=script['script_id'],text=script['text'],output_dir=script['script_id']+'/out')
                        elapsed=(time.perf_counter()-start)*1000
                        row.update(status='SUCCESS' if response['type']=='result' else 'ERROR',response=response,client_elapsed_ms=elapsed)
                        if response['type']=='result':
                            if response['text_sha256']!=script['text_sha256']: raise RuntimeError('Input text hash changed')
                            info=inspect_wav(spool/response['wav_path'])
                            if info['audio_sha256']!=response['audio_sha256'] or info['sample_rate']!=22050: raise RuntimeError('Output mismatch')
                            target=out/'audio'/config_name/f"{script['script_id']}.repeat{repeat}.wav"
                            shutil.copyfile(spool/response['wav_path'],target)
                            row['audio_path']=target.relative_to(ROOT).as_posix()
                    except Exception as exc:
                        row.update(status='TIMEOUT' if isinstance(exc,TimeoutError) else 'ERROR',
                            error_type=type(exc).__name__,message=str(exc),client_elapsed_ms=(time.perf_counter()-start)*1000)
                    rows.append(row);all_rows.append(row)
                    log.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n');log.flush()
                    if n%7==0: print(config_name,n,'/',len(chosen_schedule),row['status'],flush=True)
                (out/f'{config_name}.stderr.log').write_text(''.join(client.stderr),encoding='utf-8')
        summaries[config_name]=summarize(rows)
        return rows

    with (out/'raw.jsonl').open('w',encoding='utf-8') as log:
        for threads in (1,2,4): run_config(f'threads{threads}.batch1',schedule,log)
        eligible=[k for k,v in summaries.items() if not v['failures']]
        if not eligible: raise RuntimeError('No zero-failure TTS configuration')
        selected=min(eligible,key=lambda k:summaries[k]['compute_ms']['p95'])
        secondary=selected.replace('batch1','batch2')
        run_config(secondary,[(r,i) for r,i in schedule if scripts[i]['sentence_count']==2],log)
    report=dict(status='PC_ENGINEERING_MEASURED_HUMAN_QUALITY_PENDING',selected_config=selected,
        selected_model='MATCHA_BAKER_PLUS_VOCOS_ONLY',secondary_batch_policy='MEASURED_EXPLORATORY_RETAIN_BATCH1_PENDING_LISTENING',
        total_runs=len(all_rows),summaries=summaries,first_sentence_ready_scope='ONE_SENTENCE_WHOLE_WAV_READY_AT_CLIENT_ONLY',
        two_sentence_streaming_ready=None,first_internal_chunk_is_client_ready=False,
        stochastic_model_noise_scale=1.0,identical_waveforms_required=False,
        failures_retained=True,quality_acceptance=False,default_voice_replaced=False,delivery='NOT_SENT',
        source_weights_distribution='REVIEW_PENDING',intelligibility=None,naturalness=None)
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    for name,value in [('hello.json',hellos),('warmups.json',warmups)]:
        (out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    shutil.copyfile(ROOT/f'configs/tts.{selected}.json',ROOT/'configs/tts.selected.json')
    print('Selected',selected,'quality pending; total measured runs',len(all_rows),flush=True)


if __name__=='__main__': main()
