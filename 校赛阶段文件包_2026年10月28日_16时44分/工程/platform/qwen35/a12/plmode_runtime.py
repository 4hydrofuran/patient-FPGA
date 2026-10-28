"""Concrete pinned A53 runtime references and strict offline relocation check."""
import argparse
import copy
import re
import subprocess
from pathlib import Path
from plmode_evidence import ROOT,OUT,PARENT,BUNDLE,read,save,sha
from plm_journal import need

def machine(path):
    with Path(path).open('rb') as f:h=f.read(20)
    need(h[:6]==b'\x7fELF\x02\x01','ELF64 little endian artifact required');return int.from_bytes(h[18:20],'little')

def create(revision):
    b=read(OUT/f'BUILD-v{revision}.json');old=read(ROOT/'evidence/model_pl_A/20261026-model-route-v1/ARM_BUILD-v5.json')
    model_build=read(ROOT/'evidence/model_pl_A/20261026-model-route-v1/BUILD-v5.json')
    native=Path(model_build['workspace'])/'arm/qwen35-a12';backend=Path(b['prepared_Board_candidate'])
    math=[row for row in old['original_math_before_and_after'] if row['path'].endswith('.so') or '.so.' in row['path']]
    need(len(math)==5,'five original A53 mathematical DSOs required')
    for row in math:need(sha(row['path'])==row['sha256'],'A53 mathematical DSO changed')
    writer=read(ROOT/'evidence/model_pl_A/20261026-pl-manager-v1/BUILD-v4.json')['ARM_artifacts'][1]
    generation=read(PARENT/'BUILD-v2.json')['manager_artifacts'][1]
    need(sha(writer['path'])==writer['sha256'] and sha(generation['path'])==generation['sha256'],'original manager artifacts changed')
    artifacts=[dict(role='native',path=str(native),sha256=sha(native)),dict(role='backend',path=str(backend),sha256=sha(backend))]+[dict(r,role='math_library') for r in math]
    for row in artifacts:need(machine(row['path'])==183,'Board runtime reference is not AArch64')
    libraries={Path(r['path']).name.split('.so')[0]+'.so':r['sha256'] for r in artifacts if r['role']!='native'}
    aliases=[]
    for row in artifacts:
        if row['role']=='native':continue
        text=subprocess.run(['readelf','-d',row['path']],capture_output=True,text=True,check=True).stdout
        names=re.findall(r'\(SONAME\).*\[([^]]+)\]',text)
        for name in names:aliases.append(dict(name=name,target_basename=Path(row['path']).name,sha256=row['sha256']))
    template=BUNDLE/'control/prefix-config.json';profile=read(BUNDLE/'config/profile.pending.json')
    need(sha(BUNDLE/'w4a8.xclbin')==profile['xclbin_sha256'],'pinned original xclbin changed')
    result=dict(domain='A12_PREPARED_BOARD_MODEL_PLM_V1',workspace=b['workspace'],native=str(native),runtime_artifacts=artifacts,
        backend_library=str(backend),backend_sha256=sha(backend),writer_library=writer['path'],writer_sha256=writer['sha256'],
        generation_writer=generation['path'],generation_writer_sha256=generation['sha256'],
        observer_library=str(Path(b['workspace'])/'libplmode_observer_a53.so'),observer_sha256=sha(Path(b['workspace'])/'libplmode_observer_a53.so'),
        model=str(ROOT/'artifacts/qwen35-0.8b/qwen35-text-Q4_K_M.gguf'),kernel_source=str(BUNDLE/'KERNEL_SOURCE.json'),xclbin=str(BUNDLE/'w4a8.xclbin'),
        prefix_template=str(template),prefix_libraries=libraries,
        library_search_path=':'.join(sorted({str(Path(r['path']).parent) for r in artifacts if r['role']!='native'})),
        base_bundle=str(BUNDLE),asset_root=str(ROOT),native_asset_root='/opt/patient-qwen',loader_aliases=aliases,
        authorization_included=False,BOARD='NOT_TESTED',ARM_execution='NOT_EXECUTED',production_enabled=False,ordinary_probe_first=True)
    # Auxiliary resources stay pinned as well. Model/sidecar files are referenced,
    # not copied/scanned again; original native/Owner startup asset gates remain.
    result['auxiliary_artifacts']=[dict(role=role,path=result[path],sha256=result[key]) for role,path,key in
        [('page_writer','writer_library','writer_sha256'),('source_writer','generation_writer','generation_writer_sha256'),('observer','observer_library','observer_sha256')]]
    result['auxiliary_artifacts'] += [dict(role='prefix_template',path=str(template),sha256=sha(template)),
        dict(role='kernel_source',path=result['kernel_source'],sha256=sha(result['kernel_source'])),dict(role='xclbin',path=result['xclbin'],sha256=profile['xclbin_sha256'])]
    save(OUT/f'BOARD_BUILD-v{revision}-complete.json',result)
    save(OUT/f'BOARD_BUILD_REVIEW-v{revision}-complete.json',dict(status='PASS_CONCRETE_A53_REFERENCES_ONLY_NO_BOARD_EXECUTION',runtime_artifacts=artifacts,
        auxiliary_artifacts=result['auxiliary_artifacts'],math_recompiled=False,model_copied=False,source_lease_created=False,BOARD='NOT_TESTED'))
    return result

def relocate(prepared,root):
    """Inspect already placed review artifacts; no install, download or enable."""
    b=copy.deepcopy(prepared);root=Path(root).resolve();mapping={}
    for row in b['runtime_artifacts']+b['auxiliary_artifacts']:
        target=root/('bin' if row['role'] not in ('prefix_template','kernel_source','xclbin') else 'assets')/Path(row['path']).name
        need(target.is_file() and not target.is_symlink() and sha(target)==row['sha256'],'placed artifact missing/changed: '+str(target))
        mapping[row['path']]=str(target);row['path']=str(target)
    for field in ('native','backend_library','writer_library','generation_writer','observer_library','prefix_template','kernel_source','xclbin'):
        b[field]=mapping[b[field]]
    b['library_search_path']=str(root/'bin');b['asset_root']=str(root)
    for alias in b['loader_aliases']:
        path=root/'bin'/alias['name']
        need(path.is_file() and sha(path)==alias['sha256'],'required loader SONAME alias missing/changed')
    b['model']=str(root/'artifacts/qwen35-0.8b/qwen35-text-Q4_K_M.gguf');b['base_bundle']=str(root/'ordinary-resource-probe')
    need(sha(Path(b['base_bundle'])/'manifest.json')=='4fcb6af2d9e7d5b89f876697de6bd8f11e36174666169544a9016009551f070f','unchanged ordinary base bundle missing')
    return b

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--revision',type=int,required=True);a=p.parse_args();create(a.revision)
    print('PASS_CONCRETE_A53_REFERENCES_ONLY_NO_BOARD_EXECUTION')
