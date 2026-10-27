"""Reviewed case-free input prefix choices; never contains or returns model answers."""
import copy
from fast_response_profile import digest


def prefix_choices(profile):
    primary=dict(cache_id=profile['cache_id'],prefix_tokens=profile['prefix_tokens'],
        prefix_token_ids=profile.get('prefix_token_ids'),neutral_text=profile.get('neutral_text'))
    return [primary]+copy.deepcopy(profile.get('additional_neutral_prefixes',[]))


def validate_additional_prefixes(profile):
    extras=profile.get('additional_neutral_prefixes',[])
    if not isinstance(extras,list) or len(extras)>1:raise ValueError('only two existing neutral slots are supported')
    if not extras:return
    policy=profile.get('live_miss_prompt_policy')
    if policy not in ('allowed-compact-01','allowed-severity-scale-first-02'):raise ValueError('secondary prefix requires the reviewed live prompt')
    extra=extras[0];ids=extra.get('prefix_token_ids')
    if policy=='allowed-severity-scale-first-02':
        from severity_scale_prompt import PUBLIC_SEVERITY_PREFIX
        allowed_text=(profile['neutral_text']+PUBLIC_SEVERITY_PREFIX,);label='severity_scale_label'
        added_tokens=9
    else:
        allowed_text=(profile['neutral_text']+'疼痛程度是',profile['neutral_text']+'疼痛程度是 ');label='severity_label'
        added_tokens=4 if extra.get('neutral_text','').endswith(' ') else 3
    if (extra.get('scope')!='PUBLIC_LINGUISTIC_PREFIX_NO_CASE_VALUES' or extra.get('label')!=label
        or extra.get('trigger')!='LONGEST_EXACT_RENDERED_PROMPT_PREFIX'
        or extra.get('neutral_text') not in allowed_text
        or not isinstance(ids,list) or len(ids)!=profile['prefix_tokens']+added_tokens
        or ids[:profile['prefix_tokens']]!=profile['prefix_token_ids']
        or any(type(x) is not int or not 0<=x<248320 for x in ids)
        or extra.get('prefix_tokens')!=len(ids) or extra.get('prefix_sha256')!=digest(ids)
        or extra.get('cache_id')!='severity'+str(len(ids))+'-t'+str(profile['threads'])):
        raise ValueError('unreviewed secondary neutral prefix')
    if profile['prefix_identity'].get('neutral_prefix_routing_sha256')!=digest(extras):
        raise ValueError('neutral prefix routing identity differs')
    if profile['prefix_identity'].get('neutral_prefix_choices_sha256')!=digest([profile['prefix_token_ids'],ids]):
        raise ValueError('neutral prefix token choices differ')


def select_prefix(profile,request):
    choices=prefix_choices(profile)
    prompt=request.get('prompt')
    if not isinstance(prompt,str):return choices[0]
    matching=[p for p in choices if p.get('neutral_text') and prompt.startswith(p['neutral_text'])]
    return max(matching,key=lambda p:p['prefix_tokens']) if matching else choices[0]


def warm_requests(profile,primary):
    result=[copy.deepcopy(primary)]
    for choice in prefix_choices(profile)[1:]:
        request=copy.deepcopy(primary)
        request.update(id='warm-'+choice['cache_id'],tokens=choice['prefix_token_ids'],cache_id=choice['cache_id'])
        result.append(request)
    return result
