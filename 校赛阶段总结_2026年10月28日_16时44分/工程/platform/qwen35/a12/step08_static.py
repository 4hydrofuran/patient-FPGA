"""Final local source/profile/manifest review; no board execution."""
import ast
import argparse
import json
from common import ROOT,sha,save
from step08_common import OUT
def j(p):return json.loads(p.read_text(encoding='utf-8'))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output-name',default='STATIC_REVIEW.json');args=parser.parse_args()
    assert '/' not in args.output_name and '\\' not in args.output_name and args.output_name.endswith('.json')
    paths=list((ROOT/'platform/qwen35/a12').glob('step08*.py'))
    for p in paths:ast.parse(p.read_text(encoding='utf-8'),str(p))
    requests=j(OUT/'REQUESTS.json');assert len(requests['diagnostic'])==1
    assert len(requests['generation'])==17 and len(requests['policy_only'])==7
    actual=j(OUT/'TOKENIZED_REQUESTS.json')['generation']
    assert [r['id'] for r in actual]==[r['id'] for r in requests['generation']]
    specs={}
    for variant in ('diagnostic','generation'):
        bundle=OUT/variant/'bundle-v1';spec=j(bundle/'control/window-spec.json');specs[variant]=spec
        assert spec['max_runs']==(1224 if variant=='diagnostic' else 47736)
        assert spec['output_token_limit']==(2 if variant=='diagnostic' else 24)
        assert spec['request_limit']==(1 if variant=='diagnostic' else 17)
        for row in j(bundle/'manifest.json')['files']:
            p=bundle/row['path'];assert p.stat().st_size==row['bytes'] and sha(p)==row['sha256']
        assert sha(bundle/'control/step08_manager.py')==sha(ROOT/'platform/qwen35/a12/step08_manager.py')
    save(OUT/args.output_name,dict(status='PASS_FINAL_PRIVATE_PROFILE_AND_SOURCE_REVIEW',
        source_sha256={p.relative_to(ROOT).as_posix():sha(p) for p in paths},specs=specs,board_contact=False))
    print('FINAL_STATIC_PROFILE_MANIFEST_SOURCE_REVIEW_PASS')
