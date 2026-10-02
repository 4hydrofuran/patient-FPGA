"""Render blank Markdown reviewer copies from existing fixed inputs, without gold."""
import json
from pathlib import Path
from validate_c1 import load_frozen, read_jsonl

HERE = Path(__file__).resolve().parent
REVIEW = HERE / 'review'


def cell(value):
    return str(value).replace('|', '\\|').replace('\n', '<br>')


def main():
    manifest, *_ = load_frozen()
    questions = read_jsonl(REVIEW / 'reviewer_1_questions.template.jsonl')
    sessions = read_jsonl(REVIEW / 'session_transcripts.jsonl')
    rubric = json.loads((HERE / 'frozen/rubric_snapshot.json').read_text(encoding='utf-8'))
    if len(questions) != 72 or len(sessions) != 6:
        raise ValueError('Unexpected review pack size')
    cases = [json.loads(p.read_text(encoding='utf-8')) for p in sorted((HERE / 'frozen/cases').glob('*.json'))]
    for rater in (1, 2):
        lines = [f'# 教师{rater}独立审核表（空白副本）', '',
            '状态：PENDING；材料尚未发送。本表没有AI问题目标标签；病例事实与量表本身也是待审工程草案。请独立填写，先不互看另一人的意见。', '',
            '审核人：________　资质/课程依据：________　审核日期与时区：________　意见文件引用：________', '',
            f'冻结测试 SHA256：`{manifest["testset_sha256"]}`', '',
            '请在自己的副本中填写，不覆盖模板。每题填写允许/禁止事实ID、未知项ID、槽位、行为及参考短答；无项请明确写“无”。行为可用answer_known/state_unknown/refuse_control。意见需回填对应JSONL副本以运行分歧比较；保留原表和人工转换记录。', '',
            '## 三病例待审事实底稿', '',
            '以下事实仅用于核对合成病例，不是医学批准意见。禁止根据症状补诊断；未知不等于阴性。', '']
        for case in cases:
            lines += [f'### {case["case_id"]} / {case["case_version"]}', '', '| ID | 槽位 | 合成设定 |', '|---|---|---|']
            lines += [f'| {cell(f["fact_id"])} | {cell(f["slot"])} | {cell(f["value"])} |' for f in case['facts']]
            lines += [f'| {cell(u["fact_id"])} | {cell(u["slot"])} | 未提供；不推断阴性/正常 |' for u in case['unknowns']]
            lines += ['']
        lines += ['## 72题独立标注', '']
        for index, q in enumerate(questions, 1):
            lines += [f'### {index}. {q["test_id"]}', '', f'病例：{q["case_id"]}；版本：{q["case_version"]}', '',
                f'当前学生输入：{q["input"]["text"]}', '']
            context = q['input']['context_setup']
            if context['active_turns'] or context['foreign_sessions']:
                lines += ['前置上下文（foreign_sessions属于其他会话，仅供串扰审核，不能作为当前患者事实）：', '',
                    '```json', json.dumps(context, ensure_ascii=False, indent=2), '```', '']
            lines += ['| 审核项 | 教师填写 |', '|---|---|',
                '| 允许事实ID |  |', '| 禁止事实ID |  |', '| 未知项ID |  |', '| 应覆盖槽位 |  |',
                '| 预期行为 |  |', '| 参考短答 |  |', '| REVIEWED / NEEDS_REVISION及理由 |  |', '']
        lines += ['## 6份合成会话评分', '',
            '全部为SYNTHETIC_ENGINEERING_NOT_EXECUTED，未由真实学生或模型执行。审核22项各得分和原句/遗漏依据，总分应为各项之和；重复提问不重复计分。量表若不合适请提出版本修改。', '']
        for session in sessions:
            lines += [f'### {session["session_id"]}', '', f'病例：{session["case_id"]}；版本：{session["case_version"]}', '', '| 轮次 | 角色 | 原句 |', '|---|---|---|']
            lines += [f'| {i} | {t["role"]} | {cell(t["text"])} |' for i, t in enumerate(session['turns'], 1)]
            lines += ['', '| 量表项 | 草案上限 | 教师得分 | 原句/遗漏依据 |', '|---|---:|---:|---|']
            lines += [f'| {cell(c["criterion_id"])}：{cell(c["label"])} | {c["points"]} |  |  |' for c in rubric['criteria']]
            lines += ['', '总分：________ / 100　状态：________　意见/修改依据：________', '']
        (REVIEW / f'教师{rater}_独立审核表.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('Prepared 2 blank Markdown reviewer copies; each 72 questions and 6 synthetic sessions. No invitations sent.')


if __name__ == '__main__':
    main()
