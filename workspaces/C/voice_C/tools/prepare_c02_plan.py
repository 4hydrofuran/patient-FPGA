"""Freeze independent authored engineering scripts before timing; never use QA answers."""
import hashlib
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]


def main():
    rows = [
        ('negation', '我没有发热，也没有咳嗽。'),
        ('negation', '我不是每天都头痛。今天没有胸痛。'),
        ('number', '这份练习有12个问题。'),
        ('number', '编号是103，人数是20人。'),
        ('decimal', '练习记录的数值是3.5。'),
        ('decimal', '体温记录为37.2摄氏度。这里是虚构的录音练习。'),
        ('time', '练习从上午9点30分开始。'),
        ('time', '我昨天晚上头痛。今天早上已经不痛了。'),
        ('symptom', '我感觉恶心，偶尔有心悸。'),
        ('symptom', '我有头晕，没有呼吸困难。'),
        ('term', '这是关于支气管炎的发音练习。'),
        ('term', '请读出心电图和血常规。'),
        ('polyphone', '银行的行长重新检查了记录。'),
        ('polyphone', '请重复这句话。不要读漏重要的字。'),
    ]
    target = ROOT/'data/c02_scripts/manifest.jsonl'
    if target.exists():
        raise RuntimeError('Existing frozen scripts must be preserved')
    target.parent.mkdir(parents=True, exist_ok=True)
    records = [dict(script_id=f'tts-dev-{i:02}', text=text, category=kind,
        text_sha256=hashlib.sha256(text.encode('utf-8')).hexdigest(),
        sentence_count=text.count('。'), split='DEVELOPMENT_ONLY',
        source_kind='AUTHORED_SYNTHETIC_ENGINEERING_SCRIPT', human_pronunciation_review='PENDING',
        clinical_use='NOT_PATIENT_DATA_NOT_APPROVED_CLINICAL_ANSWER') for i,(kind,text) in enumerate(rows,1)]
    target.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in records),encoding='utf-8')
    cfg=dict(api_version=1,provider='cpu',speed=1.0,noise_scale=1.0,length_scale=1.0,silence_scale=1.0)
    for threads in (1,2,4):
        for batch in (1,2):
            path=ROOT/f'configs/tts.threads{threads}.batch{batch}.json'
            if path.exists(): raise RuntimeError('Do not overwrite existing experiment config')
            path.write_text(json.dumps(cfg|dict(num_threads=threads,max_num_sentences=batch),indent=2)+'\n',encoding='utf-8')
    (target.parent/'plan.json').write_text(json.dumps(dict(frozen_before_timing=True,
        script_count=len(records),repeats=3,runs_per_configuration=len(records)*3,
        seed=20261002,primary_configs=['threads1.batch1','threads2.batch1','threads4.batch1'],
        secondary_config='selected_threads.batch2: paired two-sentence development texts only',
        selection_policy='ZERO_FAILURE_CONFIG_WITH_LOWEST_PC_COMPUTE_P95; QUALITY_PROVISIONAL_UNTIL_HUMAN_REVIEW',
        first_sentence_ready='ONE_SENTENCE_COMPLETE_WAV_CLIENT_READY; TWO_SENTENCE_INTERNAL_CHUNK_NOT_CLIENT_READY',
        model_residency=True,waveform_cache=False,speed=1.0,amplitude_gain=1.0,
        human_review='BLANK_FORMS_ONLY_REQUESTED_BY_USER', board='NOT_TESTED',
        final_test_used=False, old_qa_questions_used=False),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Frozen 14 independent short texts; normal speed; no waveform cache')


if __name__=='__main__': main()
