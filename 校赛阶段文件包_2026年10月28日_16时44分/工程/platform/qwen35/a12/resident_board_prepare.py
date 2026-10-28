"""Pin existing A53 artifacts and policy for review only, no ARM execution."""
import copy
from pathlib import Path
from resident_evidence import ROOT,OUT,WORK,read,save,sha
from plmode_runtime import machine
from plm_journal import need


def relocate(prepared, root):
    """Read-only verification of an already placed layout; never install/enable."""
    b=copy.deepcopy(prepared);root=Path(root)
    need(root.is_absolute() and not root.is_symlink(), 'absolute non-symlink review root required')
    assets={'prefix_template','kernel_source','xclbin','resident_policy','chat_template'}
    mapping={}
    for row in b['runtime_artifacts']+b['auxiliary_artifacts']:
        directory=root/('assets' if row['role'] in assets else 'bin')
        need(not directory.is_symlink(), 'placed directory symlink refused')
        target=directory/Path(row['path']).name
        need(target.is_file() and not target.is_symlink() and sha(target)==row['sha256'], 'placed artifact changed/missing')
        mapping[row['path']]=str(target);row['path']=str(target)
    for field in ('native','backend_library','writer_library','generation_writer','observer_library',
                  'prefix_template','kernel_source','xclbin','resident_policy','chat_template'):
        b[field]=mapping[b[field]]
    app=root/'resident-app';need(not app.is_symlink(), 'placed application symlink refused')
    policy=read(b['resident_policy'])
    for row in policy['files']:
        relative=Path(row['path'])
        need(not relative.is_absolute() and '..' not in relative.parts, 'unsafe policy path')
        target=app/relative
        need(all(not q.is_symlink() for q in (target,*target.parents) if q!=root.parent), 'placed application path symlink')
        need(target.is_file() and sha(target)==row['sha256'], 'placed original application changed/missing')
    for alias in b['loader_aliases']:
        target=root/'bin'/alias['name']
        need(target.is_file() and sha(target)==alias['sha256'], 'required loader SONAME alias changed/missing')
    manifest=root/'ordinary-resource-probe/manifest.json'
    need(manifest.is_file() and not manifest.is_symlink() and
         sha(manifest)=='4fcb6af2d9e7d5b89f876697de6bd8f11e36174666169544a9016009551f070f',
         'unchanged ordinary baseline manifest missing')
    b.update(resident_app=str(app),asset_root=str(root),library_search_path=str(root/'bin'),
             model=str(root/'artifacts/qwen35-0.8b/qwen35-text-Q4_K_M.gguf'),
             base_bundle=str(root/'ordinary-resource-probe'),relocation_required=False,
             authorization_included=False,physical_release_allowed=False)
    return b


def main():
    b=copy.deepcopy(read(ROOT/'evidence/model_pl_A/20261026-pl-mode-v1/BOARD_BUILD-v2-complete.json'))
    pc=read(OUT/'SERVICE_BUILD-v3.json')
    control=read(OUT/'CONTROL_BUILD-v1.json')
    pins={Path(r['path']).name:r for r in control['artifacts']}
    native=read(OUT/'NATIVE_REVIEW-v1.json')['A53']
    backend=pins['liba12_resident_bound_candidate.so']
    writer=pins['libplm_writer_a53.so']
    for row in [native,backend,writer]:
        need(sha(row['path'])==row['sha256'] and machine(row['path'])==183,'changed/non-A53 resident artifact')
    for row in b['runtime_artifacts']:
        if row['role']=='native':row.update(native)
        elif row['role']=='backend':row.update(backend)
        need(sha(row['path'])==row['sha256'] and machine(row['path'])==183,'A53 runtime reference differs')
    old_prefix=b['prefix_template']
    b.update(workspace=str(WORK),native=native['path'],backend_library=backend['path'],backend_sha256=backend['sha256'],
             writer_library=writer['path'],writer_sha256=writer['sha256'],resident_request_limit=9,
             **{k:pc[k] for k in ('resident_policy','resident_policy_sha256','resident_app','chat_template','chat_template_sha256',
                                  'prefix_template','prefix_template_sha256')})
    # Concrete PC build paths are review references. Relocation must rewrite all
    # linked policy/app/template paths to the fixed reviewed root, then repin the
    # build and obtain fresh Owner review. This document does not enable them.
    b['prefix_libraries']={Path(r['path']).name.split('.so')[0]+'.so':r['sha256']
                           for r in b['runtime_artifacts'] if r['role']!='native'}
    b['library_search_path']=':'.join(sorted({str(Path(r['path']).parent) for r in b['runtime_artifacts'] if r['role']!='native'}))
    for row in b['auxiliary_artifacts']:
        if row['role']=='page_writer':row.update(path=writer['path'],sha256=writer['sha256'])
        elif row['role']=='prefix_template':row.update(path=b['prefix_template'],sha256=b['prefix_template_sha256'])
    b['auxiliary_artifacts'] += [dict(role='resident_policy',path=b['resident_policy'],sha256=b['resident_policy_sha256']),
                                dict(role='chat_template',path=b['chat_template'],sha256=b['chat_template_sha256'])]
    b.update(loader_aliases=[q for q in b['loader_aliases'] if not q['target_basename'].startswith('liba12_plmode_')],
             authorization_included=False,physical_release_allowed=False,BOARD='NOT_TESTED',ARM_execution='NOT_EXECUTED',
             production_enabled=False,ordinary_probe_first=True,application_factory='NOT_ENABLED_FOR_BOARD',
             relocation_required=True)
    save(OUT/'BOARD_BUILD-v1-review-only.json',b)
    save(OUT/'BOARD_PREPARE-v1.json',dict(status='A53_REFERENCES_AND_TYPED_MANAGER_PREPARED_NO_EXECUTION',
         artifacts=b['runtime_artifacts']+b['auxiliary_artifacts'],public_ABI_changed=False,
         math_recompiled=False,new_CMA_BOs=0,heavy_diagnostics=False,BOARD='NOT_TESTED',
         remaining=['fixed-root relocation and repinning','fresh original Owner resident review',
                    'ordinary baseline and actual PL numerical/content/lifecycle validation'],
         original_prefix_template=old_prefix,PC_numeric_SHA_used_as_Board_tolerance=False))
    print('PREPARED_A53_REVIEW_REFERENCES_NO_BOARD_EXECUTION')


if __name__=='__main__':main()
