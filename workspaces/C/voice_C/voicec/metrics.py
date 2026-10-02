"""Independent speech metrics; fixtures cannot become real quality results."""
import argparse
import hashlib
import json
import math
import unicodedata
from pathlib import Path


def normalize(text):
    if not isinstance(text, str):
        raise ValueError('Reference and hypothesis must be text')
    # Preserve decimals, signs, percentages and times; never rewrite negation or digits.
    return ''.join(c for c in unicodedata.normalize('NFKC', text).lower()
                   if not c.isspace() and (not unicodedata.category(c).startswith('P') or c in '.-+%:'))


def cer(reference, hypothesis):
    a, b = normalize(reference), normalize(hypothesis)
    if len(a) > 4096 or len(b) > 4096:
        raise ValueError('Metric text exceeds bounds')
    # Each tuple stores distance, substitutions, deletions, insertions.
    prev = [(j, 0, 0, j) for j in range(len(b) + 1)]
    for i, ca in enumerate(a, 1):
        cur = [(i, 0, i, 0)]
        for j, cb in enumerate(b, 1):
            old = prev[j - 1]
            sub = (old[0] + (ca != cb), old[1] + (ca != cb), old[2], old[3])
            old = prev[j]
            delete = (old[0] + 1, old[1], old[2] + 1, old[3])
            old = cur[j - 1]
            insert = (old[0] + 1, old[1], old[2], old[3] + 1)
            # Stable ties: substitution, deletion, insertion.
            cur.append(min((sub, delete, insert), key=lambda x: x[0]))
        prev = cur
    distance, s, d, ins = prev[-1]
    return dict(reference_chars=len(a), substitutions=s, deletions=d, insertions=ins,
                errors=distance, cer=distance / len(a) if a else None)


def literal_key_items(reference, hypothesis, items):
    a, b = normalize(reference), normalize(hypothesis)
    findings = []
    for item in items:
        term = normalize(item['text'])
        if not term or term not in a:
            raise ValueError('Key item must occur in reference')
        findings.append(dict(kind=item['kind'], text_sha256=hashlib.sha256(term.encode()).hexdigest(),
                             expected_count=a.count(term), observed_count=b.count(term),
                             count_preserved=a.count(term) == b.count(term)))
    return dict(items=findings, failed_items=sum(not f['count_preserved'] for f in findings),
                semantic_negation_correctness='HUMAN_REVIEW_REQUIRED',
                scope='LITERAL_PHRASE_COUNT_ONLY_NOT_CLINICAL_SEMANTICS')


def number(value, name):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError(f'{name} must be finite and nonnegative')
    return value


def timing(compute_ms, audio_duration_ms, ready_ms=None, peak_rss_bytes=None):
    number(compute_ms, 'compute_ms')
    number(audio_duration_ms, 'audio_duration_ms')
    if audio_duration_ms <= 0:
        raise ValueError('audio_duration_ms must be positive')
    if ready_ms is not None:
        number(ready_ms, 'ready_ms')
    if peak_rss_bytes is not None:
        number(peak_rss_bytes, 'peak_rss_bytes')
    return dict(compute_ms=compute_ms, audio_duration_ms=audio_duration_ms,
                rtf=compute_ms / audio_duration_ms, ready_ms=ready_ms, audible_ms=None,
                peak_rss_bytes=peak_rss_bytes, memory_scope='WORKER_PROCESS_LIFETIME_PEAK',
                ready_is_audible=False)


def aggregate(manifest, results, allow_contract=False):
    if len({r['execution_kind'] for r in results}) > 1:
        raise ValueError('Do not merge PC, board or contract runs')
    by_id = {}
    targets = {r['recording_id']: r for r in manifest}
    if len(targets) != len(manifest):
        raise ValueError('Duplicate recording IDs')
    for r in results:
        if r['recording_id'] in by_id or r['recording_id'] not in targets:
            raise ValueError('Duplicate or unknown result ID')
        if r['execution_kind'] == 'CONTRACT_TEST' and not allow_contract:
            raise ValueError('Contract results are not speech quality evidence')
        if r['execution_kind'] not in {'CONTRACT_TEST', 'PC_REAL', 'BOARD_REAL'}:
            raise ValueError('Unknown execution kind')
        target = targets[r['recording_id']]
        if r['audio_sha256'] != target['audio_sha256']:
            raise ValueError('Recording hash mismatch')
        if r['execution_kind'] != 'CONTRACT_TEST' and (
                target['authorization_status'] != 'AUTHORIZED' or not target['consent_reference'] or
                target['transcript_status'] != 'HUMAN_VERIFIED' or not target['transcript_reviewer_id']):
            raise ValueError('Real evaluation requires authorized recording and verified transcript')
        if r['status'] not in {'SUCCESS', 'ERROR', 'TIMEOUT'}:
            raise ValueError('Unknown result status')
        by_id[r['recording_id']] = r
    totals = dict(reference_chars=0, errors=0, substitutions=0, deletions=0, insertions=0)
    details = []
    keys_failed = keys_total = succeeded = 0
    for rid, target in targets.items():
        r = by_id.get(rid)
        if r is None or r['status'] != 'SUCCESS':
            details.append(dict(recording_id=rid, status='MISSING' if r is None else r['status']))
            continue
        row = cer(target['reference_text'], r['text'])
        key = literal_key_items(target['reference_text'], r['text'], target.get('key_items', []))
        succeeded += 1
        for k in totals:
            totals[k] += row[k]
        keys_failed += key['failed_items']
        keys_total += len(key['items'])
        measurement = timing(r['compute_ms'], r['audio_duration_ms'], r.get('ready_ms'), r.get('peak_rss_bytes'))
        details.append(dict(recording_id=rid, status='SUCCESS', cer=row, key_items=key, timing=measurement))
    complete = bool(targets) and succeeded == len(targets)
    fixture = bool(results) and any(r['execution_kind'] == 'CONTRACT_TEST' for r in results)
    return dict(status='CONTRACT_METRIC_TEST_ONLY' if fixture else 'REAL_INPUT_REPORT' if results else 'NOT_TESTED',
                collected_recordings=sum(r.get('recording_status') == 'COLLECTED' for r in manifest),
                input_scope='PLANNED_OR_COLLECTED_MANIFEST_NOT_PROOF_OF_AUTHORIZATION',
                expected=len(targets), received=len(by_id), succeeded=succeeded, missing=len(targets) - len(by_id),
                full_set_cer=totals['errors'] / totals['reference_chars'] if complete and totals['reference_chars'] else None,
                observed_cer=totals['errors'] / totals['reference_chars'] if totals['reference_chars'] else None,
                observed_coverage=succeeded / len(targets) if targets else None,
                literal_key_item_error_rate=keys_failed / keys_total if keys_total else None,
                human_semantic_critical_item_review='REQUIRED', tts_intelligibility='NOT_TESTED',
                tts_naturalness='NOT_TESTED', totals=totals, details=details,
                model_quality_claim=False,
                report_is='MEASUREMENTS_NOT_AUTOMATIC_ACCEPTANCE',
                execution_label_is_not_board_proof=True)


def listening_report(rows):
    """Collect independent human ratings without making up absent judgments."""
    seen = set()
    per_listener = {}
    reviewed = 0
    for r in rows:
        identity = (r['listening_item_id'], r.get('listener_id'))
        if identity in seen:
            raise ValueError('Duplicate listener/item judgment')
        seen.add(identity)
        if r['status'] == 'PENDING':
            if r.get('intelligibility_score') is not None or r.get('naturalness_score') is not None:
                raise ValueError('Pending listening form cannot contain scores')
            continue
        if r['status'] != 'HUMAN_REVIEWED':
            raise ValueError('Invalid human listening status')
        for field in ['listener_id', 'consent_reference', 'reviewed_at', 'review_reference',
                      'audio_sha256', 'text_sha256', 'engine_version', 'anonymized_condition_id']:
            if not isinstance(r.get(field), str) or not r[field].strip():
                raise ValueError('Missing listening provenance: ' + field)
        for field in ['intelligibility_score', 'naturalness_score']:
            if type(r.get(field)) is not int or not 1 <= r[field] <= 5:
                raise ValueError('Human rating must be an integer from 1 to 5')
        for field in ['negation_error', 'number_error', 'omission']:
            if type(r.get(field)) is not bool:
                raise ValueError('Require explicit human error flags')
        if not isinstance(r.get('heard_transcript'), str):
            raise ValueError('Require actual listener transcript; empty is allowed')
        reviewed += 1
        per_listener.setdefault(r['listener_id'], []).append(dict(
            listening_item_id=r['listening_item_id'], intelligibility=r['intelligibility_score'],
            naturalness=r['naturalness_score'], negation_error=r['negation_error'],
            number_error=r['number_error'], omission=r['omission'], review_reference=r['review_reference']))
    return dict(status='HUMAN_INPUT_RECORDED' if reviewed else 'NOT_TESTED',
                reviewed=reviewed, pending=len(rows)-reviewed, ratings_by_listener=per_listener,
                disagreements_preserved=True, ai_ratings=False,
                intelligibility=None if not reviewed else 'SEE_INDEPENDENT_HUMAN_RATINGS',
                naturalness=None if not reviewed else 'SEE_INDEPENDENT_HUMAN_RATINGS')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--results', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--allow-contract-fixtures', action='store_true')
    parser.add_argument('--listening', type=Path)
    args = parser.parse_args()
    read = lambda p: [json.loads(s) for s in p.read_text(encoding='utf-8').splitlines() if s.strip()] if p else []
    report = aggregate(read(args.manifest), read(args.results), args.allow_contract_fixtures)
    report['listening'] = listening_report(read(args.listening))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print(report['status'])


if __name__ == '__main__':
    main()
