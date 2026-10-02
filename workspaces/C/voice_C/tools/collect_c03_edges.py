"""Endpoint development probes with no automatic cut; synthetic negation clearly labeled."""
import hashlib,json,shutil,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from voicec.client import Client
from voicec.audio import read_pcm16
from tools.collect_c02_aux_asr import convert
from tools.benchmark_c03 import replay


def main():
    out=ROOT/'evidence/c03/edges';out.mkdir(parents=True,exist_ok=True)
    if (out/'report.json').exists():raise RuntimeError('Preserve prior probes')
    sources=[json.loads(s) for s in (ROOT/'data/c01_public/manifest.jsonl').read_text(encoding='utf-8').splitlines()]
    chosen=[r for r in sources if any(k['kind']=='negation' for k in r.get('key_items',[]))][:4]
    if len(chosen)!=4:raise RuntimeError('Expected four predeclared public negation development files')
    plan=dict(endpoint_thresholds=[.8,1.2,1.6],selected_public_ids=[r['recording_id'] for r in chosen],
        explicit_trailing_silence_ms=2000,synthetic_short_texts=['没有。','不是。'],
        continuation='SAME_SYNTHETIC_WORDS_WITH_INSERTED_1600MS_SILENCE',
        no_automatic_finish=True,no_native_reset_on_endpoint=True,human_pronunciation='NOT_TESTED',
        selected_policy='KEEP_1_2S_AS_ADVISORY; DO_NOT_AUTO_COMMIT_ANY_THRESHOLD',microphone='NOT_OPENED')
    (out/'plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    synthetic=[]
    with tempfile.TemporaryDirectory(prefix='c03-words-') as tmp:
        spool=Path(tmp)
        with Client(spool,tts_config=ROOT/'configs/tts.selected.json',response_timeout=60) as c:
            c.call('hello')
            for i,text in enumerate(plan['synthetic_short_texts']):
                result=c.call('synthesize',session_id='short',text=text,output_dir='short/out')
                if result['type']!='result':raise RuntimeError(result)
                target=out/f'negation-{i}.wav';shutil.copyfile(spool/result['wav_path'],target)
                info,pcm=read_pcm16(target);raw=convert(pcm)
                (out/f'negation-{i}.16k.pcm').write_bytes(raw)
                synthetic.append(dict(text=text,pcm=raw,tts_result=result,original_audio_sha256=info['audio_sha256']))
    results=[]
    for label in ('08','12','16'):
        with tempfile.TemporaryDirectory(prefix='c03-endpoint-') as tmp,(out/f'endpoint{label}.trace.jsonl').open('w',encoding='utf-8') as trace:
            spool=Path(tmp)
            def record(item):trace.write(json.dumps(item,ensure_ascii=False)+'\n');trace.flush()
            with Client(spool,asr_config=ROOT/'configs/asr.selected.json',stream_config=ROOT/f'configs/stream.endpoint{label}.json',response_timeout=60,trace_callback=record) as c:
                c.call('hello')
                for source in chosen:
                    info,pcm=read_pcm16(ROOT/'data/c01_public'/source['audio_path'],asr=True)
                    run=replay(c,spool,source['recording_id'],pcm,extra_silence_ms=2000)
                    run.update(kind='PUBLIC_NEGATION_DEV_WITH_EXPLICIT_ADDED_SILENCE',recording_id=source['recording_id'],
                        endpoint_candidate=label,source_audio_sha256=info['audio_sha256'])
                    results.append(run)
                for i,word in enumerate(synthetic):
                    run=replay(c,spool,f'word-{i}',word['pcm'],extra_silence_ms=2000)
                    run.update(kind='SYNTHETIC_SHORT_NEGATION_ENGINEERING',expected_text=word['text'],
                        endpoint_candidate=label,tts_result=word['tts_result'],human_transcription=None)
                    results.append(run)
                combined=synthetic[0]['pcm']+b'\0\0'*25600+synthetic[1]['pcm']
                run=replay(c,spool,'pause',combined,extra_silence_ms=2000)
                run.update(kind='SYNTHETIC_PAUSE_CONTINUATION_ENGINEERING',endpoint_candidate=label,
                    inserted_silence_ms=1600,word_texts=[s['text'] for s in synthetic],human_semantics=None)
                results.append(run)
    # Real protocol lifecycle: idle lease expires and combined worker rejects TTS during ASR.
    lifecycle=[]
    with tempfile.TemporaryDirectory(prefix='c03-life-') as tmp,(out/'lifecycle.trace.jsonl').open('w',encoding='utf-8') as trace:
        spool=Path(tmp);(spool/'s').mkdir();(spool/'s/invalid.pcm').write_bytes(b'x')
        def record(item):trace.write(json.dumps(item,ensure_ascii=False)+'\n');trace.flush()
        with Client(spool,asr_config=ROOT/'configs/asr.selected.json',tts_config=ROOT/'configs/tts.selected.json',stream_config=ROOT/'configs/stream.selected.json',response_timeout=60,trace_callback=record) as c:
            hello=c.call('hello');stream=c.call('asr_begin',session_id='s',sample_rate=16000,channels=1,format='pcm_s16le')['stream_id']
            busy=c.call('synthesize',session_id='s',text='测试。',output_dir='s/out')
            invalid=c.call('asr_push',stream_id=stream,seq=0,pcm_path='s/invalid.pcm')
            if busy.get('code')!='HALF_DUPLEX_BUSY' or invalid.get('code')!='BAD_PCM_CHUNK':raise RuntimeError('Lifecycle did not reject invalid work')
            recovered=c.call('synthesize',session_id='s',text='今天没有头痛。',output_dir='s/out')
            if recovered['type']!='result':raise RuntimeError('Half duplex did not recover')
            shutil.copyfile(spool/recovered['wav_path'],out/'combined-recovered.wav')
            idle=c.call('asr_begin',session_id='s',sample_rate=16000,channels=1,format='pcm_s16le')['stream_id']
            started=time.perf_counter();time.sleep(16)
            expired=c.call('asr_finish',stream_id=idle)
            if expired.get('code')!='STREAM_CLOSED':raise RuntimeError('Idle stream did not expire')
            lifecycle=dict(hello=hello,busy=busy,invalid=invalid,recovered=recovered,idle_elapsed_ms=(time.perf_counter()-started)*1000,
                expired=expired,caller_chunk_preserved=(spool/'s/invalid.pcm').read_bytes()==b'x')
    short=[r for r in results if r['kind']=='SYNTHETIC_SHORT_NEGATION_ENGINEERING']
    report=dict(status='PC_ENDPOINT_AND_LIFECYCLE_ENGINEERING',runs=results,lifecycle=lifecycle,
        successes=len(results),failures=0,synthetic_negation_transcripts=[dict(endpoint=r['endpoint_candidate'],
            text=r['expected_text'],actual=r['final']['text'],human_quality_accepted=False) for r in short],
        final_policy='EXPLICIT_ONLY; NATIVE_ENDPOINT_ADVICE_NOT_A_SAFE_AUTOMATIC_CUT',
        selected_config='endpoint12',selection_scope='PROVISIONAL_ADVISORY_DEFAULT; NO_TUNING_ON_FINAL_TEST',
        microphone='USER_DECLINED_NO_CAPTURE',audible_latency=None,board='NOT_TESTED')
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Endpoint probes',len(results),'all preserved; synthetic negation not human quality; lifecycle and idle timeout passed')


if __name__=='__main__':main()
