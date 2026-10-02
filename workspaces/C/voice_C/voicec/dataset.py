"""Validate actual recording provenance before any speech benchmark."""
import hashlib
from pathlib import Path
from .audio import inspect_wav
from .metrics import normalize


def validate_plan(rows, audio_root=None, require_recordings=False):
    seen = set()
    phrases = {'dev': set(), 'test': set()}
    speakers = {'dev': set(), 'test': set()}
    sources = {'dev': set(), 'test': set()}
    collected = 0
    for r in rows:
        rid, split = r['recording_id'], r['split']
        if rid in seen or split not in phrases:
            raise ValueError('Duplicate ID or invalid split')
        seen.add(rid)
        text = normalize(r['reference_text'])
        if not text:
            raise ValueError('Empty recording reference')
        phrases[split].add(text)
        sources[split].add(r['source_family'])
        if r['speaker_id']:
            speakers[split].add(r['speaker_id'])
        if r['recording_status'] == 'NOT_COLLECTED':
            if require_recordings:
                raise ValueError('Actual recording missing')
            if r['audio_sha256'] is not None or r['authorization_status'] != 'PENDING':
                raise ValueError('Uncollected plan cannot claim authorized audio')
            continue
        if r['recording_status'] != 'COLLECTED' or audio_root is None:
            raise ValueError('Unknown recording state or missing audio root')
        if (not r['speaker_id'] or r['authorization_status'] != 'AUTHORIZED' or
                not r['consent_reference'] or r['transcript_status'] != 'HUMAN_VERIFIED' or
                not r['transcript_reviewer_id']):
            raise ValueError('Missing speaker, authorization or transcript review')
        from .spool import Spool
        # Use the recording ID as the own directory name under controlled root.
        path = Spool(audio_root).resolve(r['audio_path'], rid)
        info = inspect_wav(path, asr=True)
        if info['audio_sha256'] != r['audio_sha256']:
            raise ValueError('Recording hash mismatch')
        collected += 1
    for kind, groups in [('phrases', phrases), ('speakers', speakers), ('sources', sources)]:
        if groups['dev'] & groups['test']:
            raise ValueError('Development/final-test overlap: ' + kind)
    return dict(planned=len(rows), collected=collected, authorized_recordings=collected,
                dev=len([r for r in rows if r['split'] == 'dev']),
                test=len([r for r in rows if r['split'] == 'test']),
                actual_speaker_isolation='VERIFIED' if collected else 'PENDING_NO_RECORDINGS',
                source_and_exact_phrase_overlap=False,
                semantic_template_independence='MANUAL_AUDIT_REQUIRED',
                clinical_claim=False)
