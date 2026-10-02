"""Anonymous original WAVs and genuinely blank human listening forms."""
import hashlib,json,random,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from voicec.metrics import listening_report


def main():
    benchmark=ROOT/'evidence/c02/benchmark_final'
    report=json.loads((benchmark/'report.json').read_text(encoding='utf-8'))
    scripts={r['script_id']:r for r in map(json.loads,(ROOT/'data/c02_scripts/manifest.jsonl').read_text(encoding='utf-8').splitlines())}
    records=[r for r in map(json.loads,(benchmark/'raw.jsonl').read_text(encoding='utf-8').splitlines())
             if r['config']==report['selected_config'] and r['repeat']==0]
    if len(records)!=14 or any(r['status']!='SUCCESS' for r in records):
        raise RuntimeError('Blind packet requires every selected first-repeat audio; never omit failures')
    random.Random(20261003).shuffle(records)
    out=ROOT/'listening/c02';out.mkdir(parents=True,exist_ok=True)
    if (out/'blank_forms.jsonl').exists():raise RuntimeError('Preserve human forms; never overwrite')
    forms=[];key=[]
    for i,row in enumerate(records,1):
        item=f'listen-{i:03}';path=out/'audio'/f'{item}.wav';path.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/row['audio_path'],path)
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        if digest!=row['response']['audio_sha256']: raise RuntimeError('Blind audio hash mismatch')
        forms.append(dict(listening_item_id=item,anonymized_condition_id='condition-A',engine_version='C02_EVAL_V1',
            audio_path=path.relative_to(ROOT).as_posix(),audio_sha256=digest,text_sha256=row['text_sha256'],
            status='PENDING',listener_id=None,consent_reference=None,reviewed_at=None,review_reference=None,
            heard_transcript=None,intelligibility_score=None,naturalness_score=None,
            negation_error=None,number_error=None,omission=None,polyphone_error=None,time_error=None,
            symptom_or_term_error=None,comments=None,playback_gain=1.0,
            human_test_environment=None,playback_hardware=None,device_volume=None))
        key.append(dict(listening_item_id=item,script_id=row['script_id'],text=scripts[row['script_id']]['text'],
            category=row['category'],engine='MATCHA_BAKER_VOCOS',configuration=report['selected_config'],
            response=row['response'],audio_source=row['audio_path'],review_policy='ONLY_REVEAL_AFTER_UNPROMPTED_TRANSCRIPTION'))
    (out/'blank_forms.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in forms),encoding='utf-8')
    (out/'reviewer_key.json').write_text(json.dumps(key,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (out/'listening_report.json').write_text(json.dumps(listening_report(forms),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    intro='''# C02 待填写盲听表

当前共 14 条合成音频，真人试听 0 条；所有评分、转写和错误判断均待填写。
这是开发集发音检查，不是学生 ASR 录音、最终测试或临床审核。

听者先不要打开 `reviewer_key.json`。按随机顺序听匿名 WAV，写下自己实际听到的文字，再给可懂度和自然度评分。
每位听者复制一份 `blank_forms.jsonl`，填写匿名编号、本人同意记录、时间和审核记录路径；不以 AI 转写代填听到的内容。
所有音频保持原始 22050 Hz、固定增益 1.0，无音量归一化或加速。使用同一播放设备与固定音量，记录设备、音量和环境；如需调整音量，整轮重新按相同设置听取。
可懂度与自然度分别 1—5 分：1 很难懂/很不自然，3 需要注意才能懂/一般，5 清楚易懂/自然。
评分后由审核者揭示参考文字，分别核对漏读、否定、整数/小数、时间、症状/术语和多音字。
错误字段必须由真人填写 true/false；未经核对保持 null，状态保持 PENDING。评分完成再写 HUMAN_REVIEWED，保留不同听者的意见。
模型身份和参考文字在审核者文件中；本表音频链接仅显示匿名编号。

| 编号 | 音频 | 实际听到的文字 | 可懂度 1—5 | 自然度 1—5 | 核对后的错误/备注 |
|---|---|---|---|---|---|
'''
    intro+=''.join(f"| {r['listening_item_id']} | [播放](audio/{r['listening_item_id']}.wav) | 待填写 | 待填写 | 待填写 | 待核对 |\n" for r in forms)
    (out/'待填写盲听表.md').write_text(intro,encoding='utf-8')
    print('Prepared 14 anonymous native WAVs; human judgments pending, no ratings invented')


if __name__=='__main__':main()
