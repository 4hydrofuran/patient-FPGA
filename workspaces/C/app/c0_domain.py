"""C0 PC-only domain proof. No ASR, LLM, HTTP, XRT or automatic intent classifier.

IntentMatch objects must be supplied by trusted engineering annotations. Never
deserialize them from student input or accept LLM-generated scoring evidence.
"""
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys
from time import monotonic_ns
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app' / '.deps'))
from jsonschema import Draft202012Validator, FormatChecker

NOTICE = '仅用于教学训练；不用于诊断、治疗、分诊或替代执业人员判断。病例及量表尚需医学教师审核。'


def load_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def validate_json(data, path):
    schema = load_json(ROOT / path)
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(data)


def validate_bundle(case, rubric):
    validate_json(case, 'cases/schemas/case.schema.json')
    validate_json(rubric, 'quality/schemas/rubric.schema.json')
    if case['rubric_ref'] != rubric['rubric_id'] or case['rubric_version'] != rubric['rubric_version']:
        raise ValueError('Case/rubric version mismatch')
    facts = case['facts'] + case['unknowns']
    ids = [f['fact_id'] for f in facts]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate fact id')
    slots = [f['slot'] for f in facts]
    if len(slots) != len(set(slots)):
        raise ValueError('Duplicate fact slot')
    rule_ids = [r['fact_id'] for r in case['disclosure_rules']]
    if sorted(ids) != sorted(rule_ids):
        raise ValueError('Each fact/unknown must have exactly one disclosure rule')
    for rule in case['disclosure_rules']:
        if not set(rule['requires_all_disclosed']) <= set(ids):
            raise ValueError('Unknown disclosure dependency')
    criteria = rubric['criteria']
    cids = [c['criterion_id'] for c in criteria]
    if len(cids) != len(set(cids)):
        raise ValueError('Duplicate criterion id')
    for cat, total in rubric['categories'].items():
        if sum(c['points'] for c in criteria if c['category'] == cat) != total:
            raise ValueError('Category points mismatch')
    if sum(rubric['categories'].values()) != rubric['total_points']:
        raise ValueError('Rubric total mismatch')
    visited, visiting = set(), set()
    by_id = {c['criterion_id']: c for c in criteria}

    def visit(cid):
        if cid not in by_id:
            raise ValueError('Unknown scoring dependency')
        if cid in visiting:
            raise ValueError('Cyclic scoring dependency')
        if cid in visited:
            return
        visiting.add(cid)
        for dependency in by_id[cid]['requires_all']:
            visit(dependency)
        visiting.remove(cid)
        visited.add(cid)

    for cid in cids:
        visit(cid)


@dataclass(frozen=True)
class IntentMatch:
    intent: str
    confidence: float
    start: int
    end: int


class SessionStore:
    def __init__(self):
        self._sessions = {}
        self._bundles = {}

    def create(self, case, rubric, mode='assessment'):
        validate_bundle(case, rubric)
        if mode not in {'teaching', 'assessment'}:
            raise ValueError('Unknown teaching mode')
        sid = str(uuid4())
        self._bundles[sid] = (deepcopy(case), deepcopy(rubric))
        self._sessions[sid] = dict(
            schema_version='0.1.0-draft', session_id=sid,
            case_id=case['case_id'], case_version=case['case_version'],
            rubric_id=rubric['rubric_id'], rubric_version=rubric['rubric_version'],
            mode=mode, execution_kind='PC_ENGINEERING_ONLY', notice=NOTICE,
            closed=False, turns=[], evidence=[], mappings=[], disclosed_fact_ids=[], history_summary='')
        return sid

    def _get(self, sid, active=False):
        if sid not in self._sessions:
            raise KeyError('Unknown session_id')
        state = self._sessions[sid]
        if active and state['closed']:
            raise ValueError('Session is closed')
        return state

    def snapshot(self, sid):
        return deepcopy(self._get(sid))

    def record_question(self, sid, request_id, question, matches):
        state = self._get(sid, active=True)
        case, rubric = self._bundles[sid]
        if not isinstance(request_id, str) or not request_id.strip():
            raise ValueError('request_id must be nonempty')
        if not isinstance(question, str) or not question.strip() or len(question) > 4096:
            raise ValueError('Question must be nonempty and at most 4096 characters')
        if request_id in self._requests(sid):
            raise ValueError('Duplicate request_id; retry is not a new scoring event')
        if not isinstance(matches, (list, tuple)) or len(matches) > 64:
            raise ValueError('Expected bounded trusted annotations')
        allowed = {i for c in rubric['criteria'] for i in c['accepted_intents']}
        allowed |= {i for r in case['disclosure_rules'] for i in r['trigger_intents']}
        # Validate the whole batch before mutating state.
        for match in matches:
            if not isinstance(match, IntentMatch) or match.intent not in allowed:
                raise ValueError('Unknown or untrusted intent')
            if isinstance(match.confidence, bool) or not isinstance(match.confidence, (int, float)) or not math.isfinite(match.confidence) or not 0 <= match.confidence <= 1:
                raise ValueError('Invalid confidence')
            if type(match.start) is not int or type(match.end) is not int or not 0 <= match.start < match.end <= len(question):
                raise ValueError('Invalid evidence span')
            if not question[match.start:match.end].strip():
                raise ValueError('Empty quote')
        timestamp = datetime.now(timezone.utc).isoformat()
        tick = monotonic_ns()
        records = []
        for match in matches:
            cids = [c['criterion_id'] for c in rubric['criteria'] if match.intent in c['accepted_intents']]
            item = dict(evidence_id='ev.'+str(len(state['evidence'])+len(records)+1),
                        request_id=request_id, question=question, timestamp_utc=timestamp,
                        monotonic_ns=tick, intent=match.intent, confidence=float(match.confidence),
                        quote=question[match.start:match.end], span_start=match.start,
                        span_end=match.end, criterion_ids=cids,
                        annotation_source='trusted_engineering_annotation')
            records.append(item)
        state['evidence'].extend(records)
        state['turns'].append(dict(request_id=request_id, question=question,
                                   timestamp_utc=timestamp, monotonic_ns=tick,
                                   evidence_ids=[e['evidence_id'] for e in records]))
        for item in records:
            state['mappings'].extend(dict(criterion_id=cid, evidence_id=item['evidence_id'], intent=item['intent']) for cid in item['criterion_ids'])
        # Separate request registry also remembers questions with zero recognized intent.
        self._requests(sid).add(request_id)
        state['history_summary'] = '已采集槽位：' + ','.join(sorted({e['intent'] for e in state['evidence'] if e['confidence'] >= rubric['confidence_threshold']}))
        return deepcopy(records)

    def _requests(self, sid):
        # Private per-session registry; IDs never become global conversational history.
        if not hasattr(self, '_request_ids'):
            self._request_ids = {}
        return self._request_ids.setdefault(sid, set())

    def score(self, sid):
        state = self._get(sid)
        _, rubric = self._bundles[sid]
        threshold = rubric['confidence_threshold']
        candidates = {c['criterion_id']: [e for e in state['evidence'] if e['intent'] in c['accepted_intents']] for c in rubric['criteria']}
        earned = set()
        # Least fixed point on validated DAG, independent of criterion declaration order.
        for _ in rubric['criteria']:
            for c in rubric['criteria']:
                if any(e['confidence'] >= threshold for e in candidates[c['criterion_id']]) and set(c['requires_all']) <= earned:
                    earned.add(c['criterion_id'])
        results = []
        for c in rubric['criteria']:
            cid = c['criterion_id']
            evidence = candidates[cid]
            good = [e for e in evidence if e['confidence'] >= threshold]
            status = 'earned' if cid in earned else ('needs_review' if evidence and not good else ('prerequisite_missing' if good else 'missing'))
            results.append(dict(criterion_id=cid, category=c['category'], label=c['label'],
                                max_points=c['points'], points=c['points'] if cid in earned else 0,
                                status=status, evidence=deepcopy(evidence),
                                reason='missing' if not evidence else status))
        return dict(session_id=sid, case_id=state['case_id'], case_version=state['case_version'],
                    rubric_version=state['rubric_version'], review_status='DRAFT',
                    execution_kind='PC_ENGINEERING_ONLY', notice=NOTICE,
                    scoring_authority='deterministic_rules', runtime_executed=False,
                    total=sum(r['points'] for r in results), max_total=rubric['total_points'],
                    criteria=results)

    def disclose_for_request(self, sid, request_id):
        state = self._get(sid, active=True)
        if request_id not in self._requests(sid):
            raise KeyError('Question has not been recorded')
        case, rubric = self._bundles[sid]
        intents = {e['intent'] for e in state['evidence'] if e['request_id'] == request_id and e['confidence'] >= rubric['confidence_threshold']}
        known = {f['fact_id']: f for f in case['facts']}
        unknown = {f['fact_id']: f for f in case['unknowns']}
        result = []
        for rule in case['disclosure_rules']:
            if not intents.intersection(rule['trigger_intents']) or not set(rule['requires_all_disclosed']) <= set(state['disclosed_fact_ids']):
                continue
            fid = rule['fact_id']
            if fid in known:
                result.append(dict(fact_id=fid, slot=known[fid]['slot'], value=known[fid]['value'], status='known'))
            else:
                result.append(dict(fact_id=fid, slot=unknown[fid]['slot'], value=None, status='unknown', answer=case['role_policy']['unknown_answer']))
            if fid not in state['disclosed_fact_ids']:
                state['disclosed_fact_ids'].append(fid)
        return result

    def ongoing_feedback(self, sid):
        state = self._get(sid, active=True)
        if state['mode'] == 'assessment':
            return {'session_id': sid, 'notice': NOTICE, 'feedback_available': False}
        return {'session_id': sid, 'notice': NOTICE, 'feedback_available': True,
                'missing_slot_labels': [r['label'] for r in self.score(sid)['criteria'] if r['status'] == 'missing']}

    def end(self, sid):
        state = self._get(sid, active=True)
        state['closed'] = True
        return self.score(sid)

    def delete(self, sid):
        self._get(sid)
        del self._sessions[sid]
        del self._bundles[sid]
        if hasattr(self, '_request_ids'):
            self._request_ids.pop(sid, None)


if __name__ == '__main__':
    case = load_json(ROOT/'cases/drafts/sp_chest_01.json')
    rubric = load_json(ROOT/'quality/rubrics/chest_pain_history_draft.json')
    store = SessionStore()
    sid = store.create(case, rubric)
    question = '胸痛在什么位置？'
    store.record_question(sid, 'demo-1', question, [IntentMatch('ask.location', 1.0, 0, len(question))])
    print(json.dumps(store.end(sid), ensure_ascii=False, indent=2))
