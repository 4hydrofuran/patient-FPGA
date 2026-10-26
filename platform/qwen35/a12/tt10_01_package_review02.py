"""Reduce readback duplication, retain all remote diagnostic originals and all safety evidence."""
import ast,base64,gzip,json,shutil
from tt10_01_common import ROOT,OUT,FROZEN,j,sha,save
from tt10_01_numeric import concatenated


def main():
    run=OUT/'pc-run-04/pc-new'
    gate=concatenated(run/'full_R0',run/'warm_70',run/'full_cache_70');assert gate['equal']
    save(OUT/'NUMERICAL_STREAM_READER_PC.json',dict(status='PASS_STREAMING_READER_ON_ACTUAL_FULL_PC_BYTES',gate=gate))
    before=OUT/'candidate/bundle-v1';bundle=OUT/'candidate/bundle-v2';shutil.copytree(before,bundle)
    for name in ('tt10_01_numeric.py','tt10_01_case.py'):
        shutil.copyfile(ROOT/'platform/qwen35/a12'/name,bundle/'platform/qwen35/a12'/name)
    manifest=j(bundle/'manifest.json')
    for row in manifest['files']:
        p=bundle/row['path'];row.update(bytes=p.stat().st_size,sha256=sha(p))
    (bundle/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    source=(OUT/'board_driver_reviewed.py').read_text()
    data=ast.literal_eval(next(n.value for n in ast.parse(source).body if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='DATA' for x in n.targets)))
    cfg=data['configurations'][0];cfg['manifest']=manifest
    for name in ('platform/qwen35/a12/tt10_01_numeric.py','platform/qwen35/a12/tt10_01_case.py'):
        cfg['delta'][name]=base64.b64encode(gzip.compress((bundle/name).read_bytes())).decode()
    assignment=next(n for n in ast.parse(source).body if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='DATA' for x in n.targets))
    lines=source.splitlines(True);source=''.join(lines[:assignment.lineno-1])+'DATA = '+repr(data)+'\n'+''.join(lines[assignment.end_lineno:])
    at=source.index('\ndef readback(')
    filtering="""
def readback_filter(member):
    name=member.name
    selected=any('/'+case+'/diag/' in name for case in ('warm_prefix','diag_full_R0','diag_hit'))
    if selected and member.isfile():
        if name.endswith(('.x.bin','.y.bin')):return None
        if name.endswith('.f32'):
            final_positions={str(107-1),str(70-1)}
            leaf=name.rsplit('/',1)[-1]
            if leaf!='logits-decode-0.f32' and leaf not in {'logits-prefill-'+p+'.f32' for p in final_positions}:return None
    return member

"""
    source=source[:at]+filtering+source[at:]
    source=source.replace('tar.add(path,arcname=name,recursive=True)','tar.add(path,arcname=name,recursive=True,filter=readback_filter)')
    source=source.replace("fresh=preflight();emit('FRESH_GATE_PASS'", "assert shutil.disk_usage('/var/lib/kv260-a12').free>=2147483648\n        fresh=preflight();emit('FRESH_GATE_PASS'")
    compile(source,'tt10_01_reviewed02','exec');(OUT/'board_driver_reviewed02.py').write_text(source,encoding='utf-8',newline='\n')
    for p in bundle.rglob('*.py'):compile(p.read_text(encoding='utf-8'),str(p),'exec')
    save(OUT/'PACKAGE-02.json',dict(j(OUT/'PACKAGE.json'),status='READY_REVIEWED_COMPACT_READBACK',local_bundle='candidate/bundle-v2',
        script_sha256=sha(OUT/'board_driver_reviewed02.py'),remote_originals_deleted=False,min_remote_free_disk_bytes=2147483648,
        reason='Full numerical originals exceed 1GiB; all remain remote. Streamed projection hashes, per-file hashes, full state and key full logits retained in readback.',
        all_permission_health_lifecycle_logs_included=True,PC_stream_reader_pass=True))
    print('TT10_01_COMPACT_READBACK_REVIEW_PASS_NO_REMOTE_DELETION')


if __name__=='__main__':main()
