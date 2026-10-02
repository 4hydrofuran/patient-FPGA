"""Prepare fresh speech scripts and blank authorization/transcript records."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Separate manually written source pools, independent of historical frozen QA.
SCRIPTS = {
    'dev': {
        'mandarin': ['请把桌上的蓝色书本放到窗边。', '我们明天下午在图书馆门口见面。', '这段录音只用于语音程序测试。', '今天的练习结束后请关闭麦克风。'],
        'negation': ['我没有喝咖啡，也不想喝茶。', '不是星期一，是星期三。', '请不要删除刚才保存的文件。', '我并没有说要取消这次录音。'],
        'numbers': ['这个数字是零点五，不是五。', '请依次读出二、七、十四。', '总共有二十一页，少了三页。', '百分之十二和百分之二十不能混淆。'],
        'time': ['上午九点半开始，十点十分结束。', '过去两个小时里一共响了三次。', '每次间隔十分钟，持续半分钟。', '从前天晚上到今天早上都没有变化。'],
        'questions': ['你希望先听哪一段录音？', '刚才那句话最后一个字是什么？', '需要把这句话再念一遍吗？', '为什么这次播放比上次慢一些？'],
        'terms': ['请清楚读出心电图和呼吸这两个词。', '录音词表包括胸痛、咳嗽和发热。', '这个练习只区分过敏与不过敏的发音。', '请把收缩压和舒张压分开读。'],
    },
    'test': {
        'mandarin': ['小路旁的树叶在风里轻轻摇动。', '列车到站以后请带好随身物品。', '工作人员正在检查房间里的灯光。', '播报完毕后，设备应回到等待状态。'],
        'negation': ['没有接通电话，请勿重复拨号。', '这不是新的消息，暂时不用处理。', '我不否认听到了声音，但没有听清。', '不能把未知的信息写成正常。'],
        'numbers': ['核对金额：三十八元六角。', '读数为一点二五，单位在下一行。', '房间编号是一零八，座位号是六。', '负二与正二之间相差四。'],
        'time': ['预约改到周五傍晚六点四十五分。', '昨天中午之前只出现过一次提醒。', '等待四十秒后再开始下一轮。', '这一周每隔两天做一次记录。'],
        'questions': ['能否说明你刚才提到的那个地点？', '哪一种设置适合安静的房间？', '什么时候可以重新开始测试？', '是否已经听完第二个短句？'],
        'terms': ['词语听写：恶心、头晕、气短。', '请辨别心悸和心率的读音差异。', '“既往史”三个字要完整朗读。', '朗读“放射”和“吞咽”，不要省略任何字。'],
    }
}


def main():
    rows = []
    for split, categories in SCRIPTS.items():
        for category, sentences in categories.items():
            for i, text in enumerate(sentences, 1):
                rows.append(dict(recording_id=f'c00.{split}.{category}.{i:02d}', split=split,
                    category=category, source_family=f'c00.{split}.{category}.authored',
                    reference_text=text, prompt_sha256=hashlib.sha256(text.encode()).hexdigest(),
                    planned_speaker_group=f'{split.upper()}_GROUP_{1 + (i % 2)}',
                    speaker_id=None, source_kind='PLANNED_AUTHORIZED_HUMAN_RECORDING',
                    recording_status='NOT_COLLECTED', audio_path=None, audio_sha256=None,
                    authorization_status='PENDING', consent_reference=None, license_reference=None,
                    captured_at=None, transcript_status='PENDING_HUMAN_VERIFICATION',
                    transcript_reviewer_id=None, key_items=[]))
    assert len(rows) == 48 and len({r['reference_text'] for r in rows}) == 48
    out = ROOT / 'data'
    out.mkdir(parents=True, exist_ok=True)
    path = out / 'recording_plan.jsonl'
    contents = '\n'.join(json.dumps(r, ensure_ascii=False, sort_keys=True) for r in rows) + '\n'
    if path.exists() and path.read_text(encoding='utf-8') != contents:
        raise RuntimeError('Refusing to overwrite edited recording plan; create a new version')
    path.write_text(contents, encoding='utf-8')
    # Blank human review inputs, not artificial listener scores.
    forms = []
    for i in range(1, 13):
        forms.append(dict(listening_item_id=f'c00.tts.listen.{i:02d}', text=None, wav_path=None,
            audio_sha256=None, text_sha256=None, engine_version=None, anonymized_condition_id=None,
            listener_id=None, consent_reference=None, heard_transcript=None, intelligibility_score=None,
            naturalness_score=None, negation_error=None, number_error=None, omission=None,
            reviewed_at=None, review_reference=None, status='PENDING'))
    form_path = out / 'tts_listening.template.jsonl'
    form_text = '\n'.join(json.dumps(r, ensure_ascii=False, sort_keys=True) for r in forms) + '\n'
    if form_path.exists() and form_path.read_text(encoding='utf-8') != form_text:
        raise RuntimeError('Refusing to overwrite edited listening template')
    form_path.write_text(form_text, encoding='utf-8')
    lines = ['# C00录音清单（尚未采集）', '',
        '用户确认当前没有录音；以下仅为48条录音脚本，开发24条、最终测试24条。不是音频数据集，也不是已授权记录。', '',
        '每组预留两组说话人代号；由本人将实际匿名说话人编号填入独立副本。开发与最终测试说话人、句型来源必须不交叉；同一人的补录也留在原split。实际转录须逐字核对，不能直接把朗读脚本当作他说出的内容。', '',
        '普通话、否定、数字、时间、问句、术语各类每split四条。先录安静环境，再按独立条件补噪声/距离样本，不调整最终测试来配合模型。', '',
        '| ID | 分组 | 类别 | 计划朗读文字 |', '|---|---|---|---|']
    lines += [f'| {r["recording_id"]} | {r["split"]} | {r["category"]} | {r["reference_text"]} |' for r in rows]
    lines += ['', '## 采集与授权待办', '',
        '- 由本人确认参与者同意录音及使用范围，并保存可引用的授权记录；不自动录音、不代签。',
        '- 使用匿名说话人编号，填写采集日期、设备、环境、距离、音频hash、许可/授权引用。',
        '- ASR输入mono PCM16 WAV、16000 Hz；不得把上采样的低质量源当高质量录音。',
        '- 独立人工转录实际音频，记录审核人；标注否定/数字/时间等关键片段及允许的文字规范化。',
        '- 原音频放受控目录，不默认长期留存；最终候选包不附未授权音频。',
        '- 公开录音须逐项核查其实际许可和说话人分组；本次没有下载公开音频，也没有许可已核验资产。', '']
    (out / '录音计划.md').write_text('\n'.join(lines), encoding='utf-8')
    print('48 planned scripts: dev 24, test 24. Actual recordings 0; authorizations PENDING. 12 blank listening records.')


if __name__ == '__main__':
    main()
