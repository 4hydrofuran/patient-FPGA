"""Recompute engineering comparisons and lexicon gaps without rewriting raw runs."""
import hashlib,json,random,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.benchmark_c02 import percentile


def main():
    bench=ROOT/'evidence/c02/benchmark_final'
    rows=[json.loads(s) for s in (bench/'raw.jsonl').read_text(encoding='utf-8').splitlines()]
    report=json.loads((bench/'report.json').read_text())
    selected=report['selected_config']
    by={(r['config'],r['script_id'],r['repeat']):r for r in rows}
    comparisons=[]
    for alternative in ('threads1.batch1','threads4.batch1',selected.replace('batch1','batch2')):
        pairs=[(r,by[(selected,r['script_id'],r['repeat'])]) for r in rows if r['config']==alternative]
        scripts=sorted({a['script_id'] for a,b in pairs});groups={s:[(a,b) for a,b in pairs if a['script_id']==s] for s in scripts}
        paired=list(groups.values());deltas=[];rng=random.Random(20261004)
        for _ in range(2000):
            sampled=[p for _ in paired for p in rng.choice(paired)]
            deltas.append(percentile([a['response']['compute_ms'] for a,b in sampled],.95)-
                          percentile([b['response']['compute_ms'] for a,b in sampled],.95))
        comparisons.append(dict(alternative=alternative,baseline_selected=selected,paired_runs=len(pairs),script_groups=len(scripts),
            alternative_compute_p95=percentile([a['response']['compute_ms'] for a,b in pairs],.95),
            selected_same_subset_compute_p95=percentile([b['response']['compute_ms'] for a,b in pairs],.95),
            p95_difference_ms_interval_95=[percentile(deltas,.025),percentile(deltas,.975)],
            bootstrap='2000_SCRIPT_GROUP_RESAMPLES; THREE_REPEATS_PER_SCRIPT_RETAINED_TOGETHER',
            alternative_frame_counts_same_as_selected=sum(a['response']['frames']==b['response']['frames'] for a,b in pairs),
            quality_comparable='NOT_HUMAN_VERIFIED',exploratory=alternative.endswith('batch2')))
    d=ROOT/'assets/tts/matcha-icefall-zh-baker'
    tokens={s.split()[0] for s in (d/'tokens.txt').read_text(encoding='utf-8').splitlines() if s.strip()}
    missing=[]
    for line in (d/'lexicon.txt').read_text(encoding='utf-8').splitlines():
        parts=line.split()
        if parts:
            unknown=[t for t in parts[1:] if t not in tokens]
            if unknown:missing.append(dict(word=parts[0],unknown_tokens=unknown))
    hello=json.loads((bench/'hello.json').read_text())
    warmups=json.loads((bench/'warmups.json').read_text())
    analysis=dict(status='DEVELOPMENT_ENGINEERING_COMPARISON_ONLY',comparisons=comparisons,
        lexicon_unknown_tokens=missing,lexicon_not_modified=True,
        warning='Native loader warns Unknown token: shei2 for four lexicon entries. These words need a separate human pronunciation check.',
        residency_comparison=[dict(config=h['config'],cold_process_startup_ms=h['startup_ms'],
            first_native_call_ms=next(w['response']['compute_ms'] for w in warmups if w['config']==h['config']),
            resident_compute_p95=report['summaries'][h['config']]['compute_ms']['p95']) for h in hello],
        limits=['Configuration order fixed; time/thermal effects not independently controlled.',
                'Secondary native batch comparison has 12 trials and changed waveform duration: exploratory, no quality equivalence claim.',
                'No default A voice provided; no replacement threshold or board speed claim.',
                'Warmups and startup stored separately; RTF excludes model load and physical playback.',
                'Noise scale fixed 1.0; waveform identity neither required nor assumed.'])
    (ROOT/'evidence/c02/comparison_analysis.json').write_text(json.dumps(analysis,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Paired development comparisons, cold/resident measurements, four lexicon gaps recorded')


if __name__=='__main__':main()
