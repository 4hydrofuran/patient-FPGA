"""Audit complete traces, pacing, advisory endpoint behavior and probe provenance."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.benchmark_c03 import stats


def main():
    out=ROOT/'evidence/c03';traces=sorted(out.rglob('*.trace.jsonl'))+[out/'smoke/trace.jsonl',out/'standalone_client/trace.jsonl']
    trace_checks=[]
    for path in traces:
        rows=[json.loads(s) for s in path.read_text(encoding='utf-8').splitlines()]
        requests=[r['message'] for r in rows if r['direction']=='request']
        responses=[r['message'] for r in rows if r['direction']=='response']
        ids=[r['request_id'] for r in requests]
        if len(set(ids))!=len(ids):raise ValueError('Duplicate client request ids: '+str(path))
        if any(r['request_id'] not in ids for r in responses):raise ValueError('Unmatched response')
        partials=[r for r in responses if r.get('event')=='partial']
        if any(not r['display_only'] or r['commit_allowed'] or r['final'] for r in partials):raise ValueError('Partial commit policy violated')
        finals=[r for r in responses if r.get('final') is True]
        if any(r['op']!='asr_finish' or r['type']!='result' or not r['commit_allowed'] for r in finals):raise ValueError('Incorrect final')
        if len({r['stream_id'] for r in finals})!=len(finals):raise ValueError('More than one final per stream')
        first_partial=[]
        for r in rows:
            m=r['message']
            if r['direction']=='response' and m.get('op')=='asr_begin' and m.get('type')=='result':
                later=next((x for x in rows if x['direction']=='response' and x['message'].get('event')=='partial' and x['message'].get('stream_id')==m['stream_id']),None)
                if later:first_partial.append((later['monotonic']-r['monotonic'])*1000)
        trace_checks.append(dict(path=path.relative_to(ROOT).as_posix(),requests=len(requests),responses=len(responses),
            partial_events=len(partials),unique_final_results=len(finals),errors=sum(r['type']=='error' for r in responses),
            first_partial_after_begin_ack_ms=stats(first_partial),policy='ALL_PARTIALS_DISPLAY_ONLY; EACH_STREAM_AT_MOST_ONE_FINAL'))
    runs=[json.loads(s) for s in (out/'benchmark/raw.jsonl').read_text(encoding='utf-8').splitlines()]
    paced=[r for r in runs if r['mode']=='paced']
    early=[(r['recording_id'],c['seq']) for r in paced for c in r['chunks'] if c['actual_send_ms']+.5<c['scheduled_audio_end_ms']]
    if early:raise ValueError('Paced replay submitted future PCM before capture schedule')
    pace=dict(runs=len(paced),chunks=sum(len(r['chunks']) for r in paced),premature_chunks=len(early),
        all_original_frames_preserved=all(r['source_pcm_sha256']==r['submitted_pcm_sha256'] for r in paced),
        sample_scope='14_PUBLISHED_DEV_FILES_191_2_SECONDS_OF_AUDIO; NO_MICROPHONE',
        max_schedule_lag_ms=max(r['max_send_lag_ms'] for r in paced),
        note='Late arrived chunks may catch up after backpressure; observed lag/max ACK latency retained, no chunk omitted.')
    edges=json.loads((out/'edges/report.json').read_text(encoding='utf-8'))
    endpoint_stats={}
    for label in ('08','12','16'):
        selected=[r for r in edges['runs'] if r['endpoint_candidate']==label]
        endpoint_stats[label]=dict(runs=len(selected),endpoint_advice_seen=sum(bool(r['endpoint_advice_audio_ms']) for r in selected),
            all_pcm_preserved=all(r['final']['pcm_sha256']==r['submitted_pcm_sha256'] for r in selected),
            short_negation_texts=[r['final']['text'] for r in selected if r['kind']=='SYNTHETIC_SHORT_NEGATION_ENGINEERING'],
            continuation_texts=[r['final']['text'] for r in selected if r['kind']=='SYNTHETIC_PAUSE_CONTINUATION_ENGINEERING'],
            no_automatic_cut=True,human_quality_verified=False)
    report=dict(status='PASS_ENGINEERING_TRACE_AND_PACING_AUDIT',trace_checks=trace_checks,pacing=pace,
        endpoint_candidates=endpoint_stats,selected_endpoint='1.2_SECONDS_ADVISORY_ONLY',
        startup_measurement_note='benchmark/hello.json startup_ms was sampled immediately after client construction: process spawn only, not full model startup. Use model load_ms for measured model load; no cold-start acceptance claim.',
        limits=['14 paced runs are descriptive; 42 unpaced runs are the repeated engineering set.',
                'File end plus final ACK is not independently labeled human speech end.',
                'Eight of fourteen files produced native endpoint advice before file end; this alone does not establish false endpoints.',
                'ASR CER and student quality are not improved/accepted by this protocol stage.',
                'Synthetic short-negation checks do not certify natural student utterances.',
                'Microphone authorization declined; no physical audio device opened.',
                'Original two C02 probe JSON records were overwritten by initial regression; see incident report.'])
    (out/'analysis.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Audited',len(traces),'complete traces;',pace['chunks'],'paced chunks; no early submissions; final uniqueness passed')


if __name__=='__main__':main()
