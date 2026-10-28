"""A-maintained resolution of the reviewed frontend merge conflicts."""
import argparse
import hashlib
import json
from pathlib import Path
import re

HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def resolve(root):
    gateway=root/'web_gateway';managed=gateway/'src/patient_web/managed.py'
    source=(HERE/'vendor/web_gateway/src/patient_web/managed.py').read_text(encoding='utf-8')
    before='def create_managed_app(native_pl, *, is_ready, generation_timeout_s=180, prompt_builder=None, answer_cache=None, domain="BOARD"):';assert source.count(before)==1
    source=source.replace(before,before.removesuffix('):')+', backend_options=None):')
    before='prompt_builder=prompt_builder, answer_cache=answer_cache, domain=domain))';assert source.count(before)==1
    source=source.replace(before,'prompt_builder=prompt_builder, answer_cache=answer_cache, domain=domain), backend_options=backend_options)')
    managed.write_text(source,encoding='utf-8')
    console=gateway/'src/patient_web/static/console.js';source=console.read_text(encoding='utf-8')
    pattern=r'(?ms)^<<<<<<<[^\n]*\n(.*?)^\|\|\|\|\|\|\|[^\n]*\n(.*?)^=======\n(.*?)^>>>>>>>[^\n]*\n'
    conflicts=list(re.finditer(pattern,source));assert len(conflicts)==3
    def replace(match):
        ours,base,theirs=match.groups()
        if 'p.append(answer)' in ours:
            note=theirs[theirs.index('    if (turn.answer)'):].replace('if (turn.answer)', 'if (turn.answer && turn.answer_source !== "MODEL_CACHE")')
            marker='    if (old) old.node.replaceWith(p); else transcript.append(p);'
            assert marker in ours
            return ours.replace(marker,note+marker)
        if 'streamHealthy' in ours:
            return ours.replace('if (!sid) el("state")','if (!sid || service.phase === "SWITCHING") el("state")')
        assert 'compositionstart' in ours and 'backend-choice' in theirs
        return ours+theirs
    source=re.sub(pattern,replace,source)
    source=source.replace('turn.answer_source, turn.status, turn.error]','turn.answer_source, turn.actual_backend, turn.status, turn.error]')
    assert '<<<<<<<' not in source
    console.write_text(source,encoding='utf-8')
    metadata=json.loads((root/'MERGE.json').read_text(encoding='utf-8'))
    for row in metadata['files']:
        if row['status']=='CONFLICT_REQUIRES_A_RESOLUTION':row['status']='RESOLVED_A_KEEP_FAST_PATH_AND_B_MODES'
        row['sha256']=sha(root/row['path'])
    metadata['resolution']='A preserves prompt/cache/EOS/score/timing/IME; B mode controls and actual-backend labels added'
    (root/'MERGE.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status='MERGE_RESOLVED_REQUIRES_TESTS',files=len(metadata['files'])),indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True);resolve(p.parse_args().root)
