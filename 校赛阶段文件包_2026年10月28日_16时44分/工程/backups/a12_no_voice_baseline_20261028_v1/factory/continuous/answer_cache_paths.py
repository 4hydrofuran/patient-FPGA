"""Resolve workspace and flat deployment layouts without changing model defaults."""
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent


def vendor_source():
    return HERE/'web_gateway/src' if (HERE/'web_gateway/src').is_dir() else HERE/'vendor/web_gateway/src'


def default_parent():
    return HERE.parent if (HERE/'profile.json').is_file() else HERE.parents[2]/'release/a12_fast_response_20261027_v2/short34-threads2'


def project_root(parent):
    return Path(json.loads((Path(parent)/'PC_DEPENDENCIES.json').read_text(encoding='utf-8'))['project_root'])
