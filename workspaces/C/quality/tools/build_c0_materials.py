"""Build C0 engineering drafts and review tables. Never approve medical content."""
from pathlib import Path
import hashlib
import json
import re
from zipfile import ZipFile
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
WORKSPACE = ROOT.parents[1]
PACKAGE = WORKSPACE / 'KV260_三人协作执行包_20260926'
OLD = WORKSPACE / 'patient-qwen'


def write(path, value):
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False, indent=2) + '\n'
    target.write_text(value, encoding='utf-8')


def obj(properties, required=None):
    return {'type': 'object', 'properties': properties,
            'required': list(properties) if required is None else required,
            'additionalProperties': False}


def arr(item, **kw):
    return {'type': 'array', 'items': item, **kw}


TEXT = {'type': 'string', 'minLength': 1}
NULLTEXT = {'type': ['string', 'null']}
ID = {'type': 'string', 'pattern': '^[a-z][a-z0-9_.-]*$'}
VERSION = {'type': 'string', 'pattern': '^0\\.1\\.0-draft$'}
REVIEW = obj({'status': {'const': 'DRAFT'}, 'reviewer': {'type': 'null'},
              'reviewed_at': {'type': 'null'}, 'approval_reference': {'type': 'null'},
              'needs_medical_teacher': {'const': True}})
REVIEW_VALUE = dict(status='DRAFT', reviewer=None, reviewed_at=None,
                    approval_reference=None, needs_medical_teacher=True)
NOTICE = '仅用于教学训练；不用于诊断、治疗、分诊或替代执业人员判断。病例及量表尚需医学教师审核。'


def schema(name, body):
    return {'$schema': 'https://json-schema.org/draft/2020-12/schema',
            '$id': f'urn:kv260:c0:{name}:0.1.0-draft', **body}


def build():
    # Snapshot only: never import or run the legacy application.
    names = ['README.md', 'run.py', 'frontend/frontend.py', 'backend/backend_api.py',
             'backend/backend_ollama.py', 'backend/iat_ws_python3.py', 'backend/audio.py',
             'backend/prompt.txt', 'backend/short_prompt.txt', 'backend/requirements.txt',
             'frontend/requirements.txt', 'environment.yaml', 'excluded_modules.list']
    baseline = {
        'root': str(OLD), 'git_commit': None, 'verification': 'READ_ONLY_SOURCE_AUDIT',
        'files': [{'path': n, 'sha256': hashlib.sha256((OLD/n).read_bytes()).hexdigest(),
                   'bytes': (OLD/n).stat().st_size} for n in names]}
    baseline_path = ROOT/'quality/audit/legacy_source_hashes.json'
    if baseline_path.exists():
        if json.loads(baseline_path.read_text(encoding='utf-8')) != baseline:
            raise RuntimeError('Legacy sources changed; do not overwrite baseline')
    else:
        write('quality/audit/legacy_source_hashes.json', baseline)
    listed = []
    for line in (PACKAGE/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
        expected, name = line.split('  ', 1)
        actual = hashlib.sha256((PACKAGE/name).read_bytes()).hexdigest()
        listed.append({'path': name, 'expected': expected, 'actual': actual,
                       'status': 'PASS' if actual == expected else 'FAIL'})
    manual = (PACKAGE/'KV260_三人完整执行手册_20260926.md').read_text(encoding='utf-8')
    sections = []
    for m in re.finditer(r'<!-- 原文件：(.*?) -->\n\n(.*?)(?=\n\n---\n\n<!-- 原文件：|\Z)', manual, re.S):
        name, text = m.groups()
        sections.append({'file': name, 'matches': text.strip() == (PACKAGE/name).read_text(encoding='utf-8').strip()})
    task_data = json.loads((PACKAGE/'tasks.json').read_text(encoding='utf-8'))
    task_checks = []
    for role in task_data.values():
        text = (PACKAGE/role['file']).read_text(encoding='utf-8')
        for task in role['tasks']:
            task_checks.append({'task_id': task['id'], 'matches': all(str(v) in text for v in task.values())})
    docx_reads = []
    for name in ['KV260_三人协作执行总览.docx', 'references/原始策划书.docx']:
        with ZipFile(PACKAGE/name) as z:
            parts = []
            for part in z.namelist():
                if part.startswith('word/') and part.endswith('.xml') and any(k in part for k in ['document', 'header', 'footer', 'footnotes', 'endnotes', 'comments']):
                    element = ET.fromstring(z.read(part))
                    lines = [''.join(t.text or '' for t in p.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t'))
                             for p in element.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p')]
                    parts.append(part + '\n' + '\n'.join(lines))
            # Planning documents contain no legacy credential values.
            outfile = 'quality/audit/' + Path(name).stem + '.extracted.txt'
            write(outfile, '\n\n'.join(parts))
            docx_reads.append({'file': name, 'extracted': outfile, 'method': 'OOXML_TEXT_NO_LAYOUT_REVIEW'})
    write('quality/audit/package_read_report.json', {
        'execution_date': '2026-10-01', 'timezone': 'Asia/Shanghai',
        'files': listed, 'manual_section_checks': sections, 'task_checks': task_checks,
        'docx_reads': docx_reads, 'sha256_file': {'path': 'SHA256SUMS.txt', 'sha256': hashlib.sha256((PACKAGE/'SHA256SUMS.txt').read_bytes()).hexdigest()},
        'boundary': '文本阅读和一致性检查，不是安装、板测、医学审核或官方规则确认。'})

    fact = obj({'fact_id': ID, 'slot': ID, 'value': TEXT})
    unknown = obj({'fact_id': ID, 'slot': ID, 'value': {'type': 'null'}, 'reason': TEXT})
    disclosure = obj({'fact_id': ID, 'trigger_intents': arr(ID, minItems=1, uniqueItems=True),
                      'requires_all_disclosed': arr(ID, uniqueItems=True)})
    write('cases/schemas/case.schema.json', schema('case', obj({
        'schema_version': VERSION, 'case_id': ID, 'case_version': VERSION,
        'synthetic': {'const': True}, 'review': REVIEW, 'notice': {'const': NOTICE},
        'title': TEXT, 'chief_complaint': {'const': '胸痛'},
        'facts': arr(fact, minItems=1), 'unknowns': arr(unknown, minItems=1),
        'disclosure_rules': arr(disclosure, minItems=1),
        'role_policy': obj({'answer_only_asked': {'const': True}, 'unknown_answer': TEXT,
                            'diagnostic_inference': {'const': False},
                            'assessment_hints': {'const': False}, 'teaching_hints': {'const': 'slot_labels_only'}}),
        'rubric_ref': {'const': 'chest_pain_history_draft'}, 'rubric_version': VERSION,
        'teacher_only': obj({'diagnosis': {'type': 'null'}, 'review_questions': arr(TEXT, minItems=1)}),
    })))
    categories = {'coverage': 40, 'logic': 25, 'clarity': 15, 'care': 10, 'summary': 10}
    coverage = [('onset', '起病与时间'), ('location', '部位'), ('quality', '性质'),
                ('severity', '程度'), ('duration', '持续时间与频次'), ('radiation', '放射'),
                ('provocation', '诱发或加重因素'), ('relief', '缓解因素'),
                ('associated', '伴随表现'), ('background', '既往、用药、过敏及个人/家族背景')]
    criteria = []
    for intent, label in coverage:
        criteria.append(dict(criterion_id='coverage.'+intent, category='coverage', label=label,
                             points=4, accepted_intents=['ask.'+intent], requires_all=[]))
    for intent, label, deps in [
        ('clarify_timeline', '澄清时间线', ['coverage.onset']),
        ('clarify_frequency', '澄清发作频次', ['coverage.duration']),
        ('compare_factors', '比较诱发/缓解因素', ['coverage.provocation', 'coverage.relief']),
        ('follow_associated', '对伴随表现追问', ['coverage.associated']),
        ('confirm_background', '确认相关病史背景', ['coverage.background'])]:
        criteria.append(dict(criterion_id='logic.'+intent, category='logic', label=label,
                             points=5, accepted_intents=['observe.'+intent], requires_all=deps))
    for category, entries in [('clarity', [('plain_language', '使用可理解的表述'), ('clarify_ambiguity', '澄清歧义'), ('confirm_understanding', '确认理解')]),
                              ('care', [('permission', '说明教学角色并征得模拟问诊同意'), ('acknowledge', '回应病人表达的担忧')]),
                              ('summary', [('recap', '总结已采集信息'), ('invite_correction', '邀请更正或补充')])]:
        for intent, label in entries:
            criteria.append(dict(criterion_id=category+'.'+intent, category=category, label=label,
                                 points=5, accepted_intents=['observe.'+intent], requires_all=[]))
    write('quality/schemas/rubric.schema.json', schema('rubric', obj({
        'schema_version': VERSION, 'rubric_id': ID, 'rubric_version': VERSION,
        'review': REVIEW, 'categories': obj({k: {'const': v} for k,v in categories.items()}),
        'total_points': {'const': 100}, 'confidence_threshold': {'type': 'number', 'minimum': 0, 'maximum': 1},
        'annotation_policy': {'const': 'trusted_engineering_annotations_only_C0'},
        'criteria': arr(obj({'criterion_id': ID, 'category': {'enum': list(categories)}, 'label': TEXT,
                              'points': {'type': 'integer', 'minimum': 1}, 'accepted_intents': arr(ID, minItems=1, uniqueItems=True),
                              'requires_all': arr(ID, uniqueItems=True)}), minItems=1),
    })))
    write('quality/rubrics/chest_pain_history_draft.json', dict(
        schema_version='0.1.0-draft', rubric_id='chest_pain_history_draft', rubric_version='0.1.0-draft',
        review=REVIEW_VALUE, categories=categories, total_points=100, confidence_threshold=0.8,
        annotation_policy='trusted_engineering_annotations_only_C0', criteria=criteria))

    # Fictional authored history values, not sourced patient records or clinical diagnoses.
    cases = [
        ('sp_chest_01', '活动后胸部压迫感（合成草案）', ['52岁，合成人物甲', '今天上午约两小时前第一次出现，逐渐开始', '胸口中间', '像被东西压着', '自己估计六分，满分十分', '每次约五分钟，今天两次', '有时左肩也不舒服', '快走和上楼时出现', '停下来坐着几分钟会减轻', '不舒服时有些出汗；没有咳嗽，也没有自觉发热', '以前被告知血压偏高；平时用药名字记不清；没有记得的药物过敏；不吸烟；父亲有血压偏高', '今天两次都在活动后，停下后逐渐减轻', '之前没这样痛过', '这次还没去医院检查', '担心影响日常活动']),
        ('sp_chest_02', '吸气时局部刺痛（合成草案）', ['31岁，合成人物乙', '昨天晚上开始，能记清刚出现的时间', '右侧胸口一小块地方', '一阵一阵像针扎', '自己估计四分，满分十分', '每阵不到一分钟，今天多次', '没感觉到其他地方也痛', '深吸气和咳嗽时明显', '安静坐着、不深吸气时轻些', '有干咳；没有出汗，也没有自觉发热', '没记得长期疾病；没有长期用药；药物过敏情况不清楚；不吸烟；家里类似情况不清楚', '昨晚到今天感觉差不多', '以前没出现过这种感觉', '这次没有检查或自行服药', '担心疼痛会持续']),
        ('sp_chest_03', '进食后胸部烧灼感（合成草案）', ['44岁，合成人物丙', '三天前晚饭后慢慢出现', '胸口中间偏下', '有些烧灼感', '自己估计三分，满分十分', '每次约十分钟，这三天每天一两次', '没感觉放射到肩膀或手臂', '吃得多和饭后马上躺下时明显', '坐起来会逐渐舒服些', '有时口里感觉酸；没有出汗或明显气短', '没记得长期疾病；没有长期用药；没有记得的药物过敏；偶尔饮酒；家里类似情况不清楚', '三天来没有明显加重', '以前偶尔有过口酸，但没有这种胸部感觉', '没有做过这次相关检查，也没自行服药', '担心反复发生'])]
    slots = ['identity', 'onset', 'location', 'quality', 'severity', 'duration', 'radiation', 'provocation', 'relief', 'associated', 'background', 'timeline', 'previous_episode', 'care_received', 'concern']
    rubric_intents = {'timeline': 'observe.clarify_timeline', 'previous_episode': 'ask.previous_episode',
                     'care_received': 'ask.care_received', 'concern': 'ask.concern', 'identity': 'ask.identity'}
    for case_id, title, values in cases:
        facts = [dict(fact_id='fact.'+slot, slot=slot, value=value) for slot,value in zip(slots,values)]
        unknowns = [dict(fact_id='unknown.'+s, slot=s, value=None, reason='合成设定未提供；不推断阴性或正常结果')
                    for s in ['diagnosis', 'ecg', 'troponin', 'vital_signs', 'drug_dose', 'contact_details']]
        rules = [dict(fact_id=f['fact_id'], trigger_intents=[rubric_intents.get(f['slot'], 'ask.'+f['slot'])],
                      requires_all_disclosed=[]) for f in facts]
        rules += [dict(fact_id=f['fact_id'], trigger_intents=['ask.'+f['slot']], requires_all_disclosed=[]) for f in unknowns]
        write(f'cases/drafts/{case_id}.json', dict(
            schema_version='0.1.0-draft', case_id=case_id, case_version='0.1.0-draft', synthetic=True,
            review=REVIEW_VALUE, notice=NOTICE, title=title, chief_complaint='胸痛', facts=facts, unknowns=unknowns,
            disclosure_rules=rules, role_policy=dict(answer_only_asked=True, unknown_answer='这项我不清楚，设定里没有提供。',
                                                     diagnostic_inference=False, assessment_hints=False, teaching_hints='slot_labels_only'),
            rubric_ref='chest_pain_history_draft', rubric_version='0.1.0-draft',
            teacher_only=dict(diagnosis=None, review_questions=['合成病史是否自洽、适合指定教学层级？', '哪些追问和表述应改写？', '哪些未知信息需要补充，哪些应继续保留未知？'])))

    mapping = obj({'criterion_id': ID, 'evidence_id': ID, 'intent': ID})
    evidence = obj({'evidence_id': ID, 'request_id': TEXT, 'question': TEXT,
                    'timestamp_utc': {'type': 'string', 'format': 'date-time'},
                    'monotonic_ns': {'type': 'integer', 'minimum': 0},
                    'intent': ID, 'confidence': {'type': 'number', 'minimum': 0, 'maximum': 1},
                    'quote': TEXT, 'span_start': {'type': 'integer', 'minimum': 0},
                    'span_end': {'type': 'integer', 'minimum': 1},
                    'criterion_ids': arr(ID, uniqueItems=True),
                    'annotation_source': {'const': 'trusted_engineering_annotation'}})
    write('app/schemas/session.schema.json', schema('session', obj({
        'schema_version': VERSION, 'session_id': TEXT, 'case_id': ID, 'case_version': VERSION,
        'rubric_id': ID, 'rubric_version': VERSION, 'mode': {'enum': ['teaching', 'assessment']},
        'execution_kind': {'const': 'PC_ENGINEERING_ONLY'}, 'notice': {'const': NOTICE},
        'closed': {'type': 'boolean'},
        'turns': arr(obj({'request_id': TEXT, 'question': TEXT,
                          'timestamp_utc': {'type': 'string', 'format': 'date-time'},
                          'monotonic_ns': {'type': 'integer', 'minimum': 0},
                          'evidence_ids': arr(ID, uniqueItems=True)})),
        'evidence': arr(evidence), 'mappings': arr(mapping),
        'disclosed_fact_ids': arr(ID, uniqueItems=True), 'history_summary': {'type': 'string'},
    })))
    # Human-readable review packet generated from exactly the JSON values being reviewed.
    lines = ['# C0 医学教师审核材料', '', '状态：DRAFT / 待分配审核教师。尚未发送，尚未审核；无签名或医学正确性结论。', '', NOTICE, '',
             '三份都是工程编写的虚构病史，不表示确定病种。请按行确认、修改或拒绝；变更后递增版本并重跑测试。', '',
             '| 字段 | 病例甲 | 病例乙 | 病例丙 | 教师意见/依据 |', '|---|---|---|---|---|']
    for i,slot in enumerate(slots):
        lines.append('| '+slot+' | '+' | '.join(c[2][i] for c in cases)+' | 待填写 |')
    lines += ['', '共同未知：诊断、心电图、肌钙蛋白、生命体征、具体药物剂量、联系方式。未知不等于阴性。', '',
              '披露：只回答当前问题对应字段；考核过程中不提示遗漏；教学提示只显示槽位名称，不泄露字段值。', '',
              '| 量表项 | 类别 | 分值 | 前置条件 | 审核意见 |', '|---|---|---:|---|---|']
    for c in criteria:
        lines.append(f"| {c['criterion_id']}：{c['label']} | {c['category']} | {c['points']} | {', '.join(c['requires_all']) or '无'} | 待填写 |")
    lines += ['', '## 需要教师裁定的争议项', '',
              '- 40/25/15/10/10 仅继承原策划书建议，是否符合你们课程量表？',
              '- coverage.background 合并多个病史领域是否过粗？目前规则为二值工程草案，不代表全面采集。',
              '- “逻辑”依赖目前按结束时整体覆盖检查，可同轮完成，不判断采集先后；不要求唯一提问顺序。是否应加入合理时序、部分分或更细粒度？',
              '- 表达、关怀、总结需人工可观察标签。C0 不用关键词或 LLM 自动判定人格、情感或教学能力。',
              '- 0.8 是工程置信度阈值，尚未校准；低置信度待复核，不能直接视为正确或医学错误。',
              '- 三份病史的时间线、阳性/阴性、药物与过敏表述是否一致？是否应增加独立事实槽位？',
              '- 哪些信息可以在病例开始时显示，哪些只能问到再披露？',
              '- 真实症状求助退出角色扮演流程；C0 没有实现真实症状识别器。', '',
              '## 回填与签核', '',
              '| 材料 | 审核教师/资质 | 日期 | 修改/批准/拒绝 | 依据路径 |', '|---|---|---|---|---|',
              '| 三病例与量表 0.1.0-draft | 待指定 | 待填写 | 未审核 | 待填写 |', '',
              '请保留两位教师的独立意见和分歧（建议）；AI 不代填姓名、意见或批准状态。', '',
              '参考只用于字段范围：原策划书第九节；[ACC 胸痛指南执行摘要](https://www.jacc.org/doi/10.1016/j.jacc.2021.07.052) 检索摘要支持记录症状特征、时长、伴随表现和风险背景，全文访问403，未作完整指南核验；[NICE CG95](https://www.nice.org.uk/guidance/CG95/chapter/recommendations) 检索摘要支持疼痛属性字段，全文403。二者不审核本包个体病史，也不定义这里的评分权重。', '']
    write('quality/review/C0_医学审核表.md', '\n'.join(lines))

    equipment = []
    for item, required, need in [
        ('USB麦克风/声卡及扬声器', 'C2/C4', '提供型号、接口、持有/借用情况；板端枚举/录放音待测'),
        ('本机开始/结束控制按键', 'C4', '优先USB HID候选；实际设备及控制方式待确认'),
        ('有风道外壳与固定件', 'C7', '尺寸、散热器空间和装配人员待确认'),
        ('成品电池电源', 'C7', 'Wh、保护、接口、供电能力由A/现场核验后决定'),
        ('Jetson对照设备', 'E10，可选', '是否已有/能借用、具体型号及测试权限待确认'),
        ('直流功率计', 'E09', '型号、采样率、精度、借用/采购方案待确认'),
        ('KV260及电源、散热、存储', 'A1/C2', '目录名不能证明设备持有；身份和租约由A提供')]:
        equipment.append(dict(item=item, needed_by=required, availability='UNKNOWN', allocation='UNDECIDED',
                              model=None, owner=None, evidence=None, price=None, action=need))
    write('quality/review/equipment_inventory.json', {'status': 'PENDING_USER_FACTS', 'items': equipment})
    write('quality/review/人工确认与设备清单.md', '# C0 人工资料与设备清单\n\n实际执行：2026-10-01（北京时间），已晚于C0建议窗口9/27—9/29。未倒填任何审核/交付日期。\n\n'+
          '| 设备 | 需要阶段 | 已有/借用/待采购 | 下一步 |\n|---|---|---|---|\n'+
          '\n'.join(f"| {i['item']} | {i['needed_by']} | 未确认，非已购买 | {i['action']} |" for i in equipment)+
          '\n\n所有报价/实测参数均未知；现有、借用、拟采购分类待用户提供证据后回填。未购买、未接电池。\n\n'+
          '| 人工项 | 所需引用或材料 | 当前状态 |\n|---|---|---|\n'+
          '| 医学审核教师 | 教师/课程量表参考及送审渠道 | 审核包已备齐，尚未发送，待指定 |\n'+
          '| A0目录与公共契约 | A0交接、runtime_api_v1、rootfs/ABI候选 | 当前授权工作区未找到；用户已授权旧工程只读 |\n'+
          '| 已报名状态 | 本团队报名成功凭证 | 未取得，不依据公共赛程推断 |\n'+
          '| 校赛提交与个人考核 | 学校通知及完整比赛/AMD指南 | 未取得 |\n'+
          '| AI辅助声明 | 当届完整条款、学校声明模板、签字要求 | 未取得，不推定获准 |\n\n'+
          '给A的请求已写入 app/proposals/runtime_api_v1.C0.md，尚无A/B/C评审。请由队长依据真实文件回复，保留出处。\n')


if __name__ == '__main__':
    build()
    print('C0 draft materials generated; medical review remains pending.')
