"""Versioned deterministic topic-coverage rubric; no clinical/personality inference."""
import re
from .domain import digest

RUBRIC={'version':'coverage-v1-draft','review_status':'PENDING_TEACHER_REVIEW',
        'items':{s:10 for s in ('location','quality','onset','duration','severity','radiation','trigger','relief','dyspnea','allergy')}}

def evidence(transcript,p,turn_id):
    neg=[{'span':[m.start(),m.end()],'quote':m.group()} for m in re.finditer('不是没有|没有不|没有|不是|不|无',transcript.text)]
    times=[{'span':[m.start(),m.end()],'quote':m.group()} for m in re.finditer(r'[0-9一二两三四五六七八九十]+(?:分钟|小时|天|周)(?:前)?',transcript.text)]
    review=transcript.source=='asr_final' and (transcript.confidence is None or transcript.confidence<0.8)
    review=review or p.reason=='double_negation_ambiguous'
    return {'turn_id':turn_id,'request_id':transcript.request_id,'transcript':transcript.text,'source':transcript.source,
            'confidence':transcript.confidence,'start_ms':transcript.start_ms,'end_ms':transcript.end_ms,
            'slot_spans':list(p.evidence),'negation_spans':neg,'time_spans':times,'requires_review':review,
            'accepted_slots':list(p.intent_ids) if p.route=='answer' and not review else [],'route_reason':p.reason,
            'rule_version':p.rule_version,'rubric_version':RUBRIC['version']}

def score(events):
    covered=set();review=[]
    for e in events:
        if e['requires_review']:review.append(e['turn_id']);continue
        covered.update(e['accepted_slots'])
    items={s:{'points':w if s in covered else 0,'max_points':w,
              'evidence_turns':[e['turn_id'] for e in events if s in e['accepted_slots'] and not e['requires_review']]}
           for s,w in RUBRIC['items'].items()}
    return {'rubric_version':RUBRIC['version'],'rubric_sha256':digest(RUBRIC),'score':sum(x['points'] for x in items.values()),
            'max_score':100,'items':items,'review_turns':review,'meaning':'draft_question_topic_coverage_only',
            'review_status':'PENDING_TEACHER_REVIEW','clinical_validity':None,
            'personality_or_real_emotion_inference':False}
