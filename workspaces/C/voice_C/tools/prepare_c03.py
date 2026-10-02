"""Create endpoint development configs; keep source/final-test boundaries explicit."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
base=dict(api_version=1,chunk_ms=200,max_audio_seconds=60,max_chunks=1024,max_streams_per_process=64,
    idle_timeout_seconds=15,endpoint_policy='ADVISORY_UNTIL_EXPLICIT_FINISH',tail_padding_ms=660,
    rule1_min_trailing_silence=2.4,rule3_min_utterance_length=20.0)
for label,value in [('08',.8),('12',1.2),('16',1.6)]:
    p=ROOT/f'configs/stream.endpoint{label}.json'
    if p.exists():raise RuntimeError('Preserve existing development configuration')
    p.write_text(json.dumps(base|dict(rule2_min_trailing_silence=value),indent=2)+'\n',encoding='utf-8')
(ROOT/'configs/stream.selected.json').write_bytes((ROOT/'configs/stream.endpoint12.json').read_bytes())
out=ROOT/'evidence/c03/plan.json'
out.write_text(json.dumps(dict(chunk_ms=200,primary_runs=42,source='C01_PRESELECTED_PUBLIC_DEV_AUDIO_14_X_3',
    paced_runs='ONE_PASS_ALL_14_DEV_FILES_AT_AUDIO_WALL_CLOCK_RATE',
    endpoint_candidates=[.8,1.2,1.6],selected_policy='START_1_2_SECONDS_ADVISORY; NO_AUTOMATIC_FINAL_OR_TRIMMING',
    final_submission='EXPLICIT_FINISH_ONCE',microphone='AUTHORIZATION_PENDING_NO_CAPTURE',
    own_final_recording_plan_used=False,old_qa_answers_used=False,default_voice_replaced=False,
    license='STILL_PENDING',board='NOT_TESTED'),indent=2)+'\n',encoding='utf-8')
print('C03 streaming configs prepared: 200 ms raw PCM, explicit final, no truncation')
