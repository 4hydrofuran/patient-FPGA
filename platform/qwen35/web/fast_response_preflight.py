"""Resolve the complete local candidate dependency closure before Owner/PL entry."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys


def preflight(window):
    window=Path(window).resolve();bundle=window/'bundle'
    read=lambda p:json.loads(p.read_text(encoding='utf-8'))
    raw_profile=read(window/'profile.json')
    required=['web_managed.py','native_pl.py','fast_response_profile.py',
              'web_gateway/src/patient_web/managed.py','web_gateway/src/patient_web/reference/session.py']
    if raw_profile['prompt_policy']=='facts-only-02':required.append('short_prompt_adapter.py')
    for name in required:
        if not (window/name).is_file():raise ImportError('missing packaged dependency before Owner/PL: '+name)
    config=read(window/'web-config.json')
    if raw_profile.get('realtime_draft_strategy') is not None:
        if not (window/'realtime_draft.py').is_file():raise ImportError('missing real-time draft host module')
        if config.get('realtime_draft_strategy')!=raw_profile['realtime_draft_strategy']:
            raise RuntimeError('realtime draft selection differs')
    for p in config.get('dependency_paths',[]):
        if Path(p).is_dir():sys.path.insert(0,p)
    for p in (window/'web_gateway/src',window):sys.path.insert(0,str(p))
    import uvicorn
    from web_managed import create_app
    from patient_web.managed import create_managed_app
    from fast_response_profile import load_profile,builder,pair_budget
    profile=load_profile(window/'profile.json');builder(profile)
    from answer_cache_profile import prepare_answer_cache
    cache=prepare_answer_cache(window,config)
    cfg=read(bundle/'control/prefix-config.json')
    if cfg['identity']!=profile['prefix_identity'] or cfg['allowed_prefixes']!=[profile['prefix_token_ids']]:
        raise RuntimeError('profile/prefix config differs')
    spec=read(bundle/'control/window-spec.json');requests=read(bundle/'control/requests.json')
    if spec['authorization_included'] is not False:raise RuntimeError('workload authorization differs')
    if pair_budget(requests,profile['prefix_tokens'])!=spec['calculated_worst_case']:raise RuntimeError('pair budget differs')
    path=bundle/'control/resource_probe_manager.py'
    s=importlib.util.spec_from_file_location('fast_response_preflight_manager',path)
    manager=importlib.util.module_from_spec(s);s.loader.exec_module(manager)
    from resource_probe_binding import require_manager_api
    require_manager_api(manager)
    from board_entry import prepared_main
    prepared_main(path.read_text(encoding='utf-8'))
    if spec['max_runs']==5000:
        from resource_probe_policy import validate_plan
        validate_plan(requests,spec)
    return dict(status='PASS_OFFLINE_IMPORTS_PROFILE_BUDGET',profile_id=profile['profile_id'],
                window=window.name,answer_cache=cache.report() if cache else None,
                owner_created=False,worker_started=False,board_contacted=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--window',type=Path,required=True)
    print(json.dumps(preflight(p.parse_args().window),indent=2))
