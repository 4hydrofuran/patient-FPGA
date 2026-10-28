"""Concrete host profiles shared by preparation, transport and admission."""
import hashlib
import json
from pathlib import Path


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


LEGACY = dict(profile_id='legacy70-threads2', prompt_policy='legacy', prefix_tokens=70,
              cache_id='neutral', context_tokens=1024, output_tokens=24, threads=2,
              kernel_threads=2, warm_request_id='warm_prefix')


def load_profile(path):
    p=json.loads(Path(path).read_text(encoding='utf-8'))
    validate_profile(p)
    return p


def validate_profile(p):
    if p.get('schema')!='A12_FAST_RESPONSE_PROFILE_V1':raise ValueError('profile schema differs')
    natural=p.get('prompt_policy')=='patient-natural-short-v1'
    if p.get('prompt_policy') not in ('legacy','facts-only-02','patient-natural-short-v1'):raise ValueError('unknown prompt policy')
    if not natural and p.get('prefix_tokens') != (34 if p['prompt_policy']=='facts-only-02' else 70):
        raise ValueError('profile prefix differs')
    if natural:
        from natural_patient_prompt import POLICY,policy_sha256
        if (p.get('natural_patient_policy')!=POLICY or not 1<=p['prefix_tokens']<=128
                or p['prefix_identity'].get('natural_patient_policy_sha256')!=policy_sha256()):
            raise ValueError('natural prompt identity differs')
    output=32 if p.get('realtime_draft_strategy') else 24
    for k,v in (('context_tokens',1024),('output_tokens',output)):
        if type(p.get(k)) is not int or p[k]!=v:raise ValueError('profile bound differs: '+k)
    if p.get('threads') not in (2,3,4) or p.get('kernel_threads')!=p['threads']:raise ValueError('threads differ')
    tokens=p.get('prefix_token_ids')
    if not isinstance(tokens,list) or len(tokens)!=p['prefix_tokens'] or digest(tokens)!=p.get('prefix_sha256'):
        raise ValueError('prefix token digest differs')
    if not all(type(t) is int and 0<=t<248320 for t in tokens):raise ValueError('invalid prefix token')
    if p.get('authorization_included') is not False:raise ValueError('profile cannot carry authority')
    expected_cache=('natural-t'+str(p['threads'])) if natural else ('short34-t'+str(p['threads']) if p['prompt_policy']=='facts-only-02' else 'neutral')
    if p.get('cache_id') != expected_cache:
        raise ValueError('profile cache namespace differs')
    if p.get('realtime_draft_strategy') is not None:
        from realtime_draft import STRATEGY
        if p['realtime_draft_strategy']!=STRATEGY or p['prompt_policy'] not in ('facts-only-02','patient-natural-short-v1'):
            raise ValueError('realtime draft profile differs')
    if p.get('live_miss_prompt_policy') is not None:
        from compact_fact_prompt import POLICY,policy_sha256
        if p['live_miss_prompt_policy']=='allowed-severity-scale-first-02':
            from severity_scale_prompt import POLICY,policy_sha256
        if (p['live_miss_prompt_policy']!=POLICY or not p.get('realtime_draft_strategy')
                or p['prefix_identity'].get('live_miss_prompt_policy_sha256')!=policy_sha256()):
            raise ValueError('live miss input selection differs')
    from neutral_prefixes import validate_additional_prefixes
    validate_additional_prefixes(p)
    if p.get('prefill_chunk',256) not in (8,256):raise ValueError('unreviewed live prefill chunk')
    return p


def check_ready(profile, ready):
    cache=ready.get('prefix_cache',{})
    if not cache.get('enabled') or not cache.get('binding_sha256'):raise RuntimeError('prefix cache not ready')
    identity=cache.get('identity',{})
    for key,value in profile['prefix_identity'].items():
        if identity.get(key)!=value:raise RuntimeError('native profile identity differs: '+key)


def builder(profile):
    if profile.get('natural_patient_policy'):
        from natural_patient_prompt import prompt_messages
        return prompt_messages
    if profile.get('live_miss_prompt_policy')=='allowed-severity-scale-first-02':
        from severity_scale_prompt import prompt_messages
        return prompt_messages
    if profile.get('live_miss_prompt_policy'):
        from compact_fact_prompt import prompt_messages
        return prompt_messages
    if profile['prompt_policy']=='legacy':return None
    from short_prompt_adapter import prompt_messages
    return prompt_messages


def pair_budget(requests, prefix_tokens):
    total=0
    for r in requests:
        n=len(r['tokens'])-(prefix_tokens if r['cache_policy']=='TT10_REQUIRE_HIT' else 0)
        if n<=0:raise ValueError('generation must extend prefix')
        total+=72*((n+7)//8+(0 if r['op']=='cache_create' else r['max_tokens']-1))
    return total
