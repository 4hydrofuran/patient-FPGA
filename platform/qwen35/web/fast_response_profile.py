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
    if p.get('prompt_policy') not in ('legacy','facts-only-02'):raise ValueError('unknown prompt policy')
    if p.get('prefix_tokens') != (34 if p['prompt_policy']=='facts-only-02' else 70):
        raise ValueError('profile prefix differs')
    for k,v in (('context_tokens',1024),('output_tokens',24)):
        if type(p.get(k)) is not int or p[k]!=v:raise ValueError('profile bound differs: '+k)
    if p.get('threads') not in (2,3) or p.get('kernel_threads')!=p['threads']:raise ValueError('threads differ')
    tokens=p.get('prefix_token_ids')
    if not isinstance(tokens,list) or len(tokens)!=p['prefix_tokens'] or digest(tokens)!=p.get('prefix_sha256'):
        raise ValueError('prefix token digest differs')
    if not all(type(t) is int and 0<=t<248320 for t in tokens):raise ValueError('invalid prefix token')
    if p.get('authorization_included') is not False:raise ValueError('profile cannot carry authority')
    if p.get('cache_id') != ('short34-t'+str(p['threads']) if p['prompt_policy']=='facts-only-02' else 'neutral'):
        raise ValueError('profile cache namespace differs')
    return p


def check_ready(profile, ready):
    cache=ready.get('prefix_cache',{})
    if not cache.get('enabled') or not cache.get('binding_sha256'):raise RuntimeError('prefix cache not ready')
    identity=cache.get('identity',{})
    for key,value in profile['prefix_identity'].items():
        if identity.get(key)!=value:raise RuntimeError('native profile identity differs: '+key)


def builder(profile):
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
