"""Load immutable cache data before the original Owner, retain it in this process."""
import copy
import json
from pathlib import Path
from verified_answer_cache import VerifiedAnswerCache,model_identity

_PREPARED={}


def prepare_answer_cache(window,config):
    window=Path(window).resolve();spec=config.get('answer_cache')
    if spec is None:return None
    if spec.get('enabled') is not True:raise ValueError('explicit cache profile required')
    profile=json.loads((window/config['profile']).read_text(encoding='utf-8'))
    identity=model_identity(profile['prefix_identity'],window/'web_gateway/src/patient_web/reference')
    cache=VerifiedAnswerCache(window/spec['path'],identity=identity,expected_sha256=spec['sha256'])
    _PREPARED[str(window)]=(copy.deepcopy(config),cache)
    return cache


def prepared_answer_cache(window,config):
    if not config.get('answer_cache'):return None
    entry=_PREPARED.get(str(Path(window).resolve()))
    if entry is None or entry[0]!=config:raise RuntimeError('answer cache not prepared before Owner/PL')
    return entry[1]
