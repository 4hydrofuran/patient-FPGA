"""One independent CPU02 attempt; persist initial refusal details without changing gates."""
import ast
import base64
import gzip
import hashlib
import io
import json
from pathlib import Path
import shutil
import tarfile
from tt10_00_prepare import ROOT, OUT, j, save, sha


def main():
    assert j(OUT/'board_02/receipt.json')['exit_code'] == 2
    for line in (OUT/'board_02/stdout.txt').open(encoding='utf-8'):
        event = json.loads(line)
        if event['event'] != 'READBACK' or event['mode'] != 'cpu02':
            continue
        raw = base64.b64decode(event['base64'], validate=True)
        assert len(raw) == event['bytes'] and hashlib.sha256(raw).hexdigest() == event['sha256']
        target = OUT/'cpu02/failed-readback-v1'
        target.mkdir()
        (target.parent/'failed-readback-v1.tar.gz').write_bytes(raw)
        with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as archive:
            members = archive.getmembers()
            assert len(members) < 2000 and sum(m.size for m in members) < 536870912
            assert len({m.name for m in members}) == len(members)
            for m in members:
                dest = (target/m.name).resolve()
                assert dest.is_relative_to(target.resolve()) and not m.issym() and not m.islnk()
                if m.isdir():
                    dest.mkdir(parents=True, exist_ok=True)
                else:
                    assert m.isfile()
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    with dest.open('xb') as stream:
                        stream.write(archive.extractfile(m).read())
        assert j(target/'manager-exit.json')['exit_code'] == 1
        assert 'PROCESS_SCAN_INCOMPLETE_OR_WRONG_BOOT' in (target/'manager.stderr.txt').read_text()
        assert not (target/'run-v1/s1').exists() and not (target/'run-v1/result.json').exists()
        break
    else:
        raise AssertionError('missing failed CPU02 readback')

    original = (OUT/'board_driver_reviewed.py').read_text(encoding='utf-8')
    data = ast.literal_eval(next(n.value for n in ast.parse(original).body
                               if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'DATA' for t in n.targets)))
    config = next(c for c in data['configurations'] if c['mode'] == 'cpu02')
    bundle = OUT/'cpu02/bundle-v2'
    shutil.copytree(OUT/'cpu02/bundle-v1', bundle)
    window = bundle/'platform/qwen35/a12/cpu01b_window.py'
    before = window.read_text()
    anchor = '        snapshot = collect(allow_ps_display=True)\n        require_no_users(snapshot, True, boot_id=self.boot)'
    added = "        save(self.evidence / 'owner-initial-resource-scan.json', snapshot)\n"
    assert before.count(anchor) == 1
    after = before.replace(anchor, anchor.replace('        require_no_users', added+'        require_no_users'), 1)
    assert after.replace(added, '', 1) == before
    window.write_text(after, encoding='utf-8', newline='\n')
    spec = j(bundle/'control/window-spec.json')
    spec['window_id'] = 'a12-tt10-00-cpu02-20261024-v2'
    (bundle/'control/window-spec.json').write_text(json.dumps(spec, indent=2)+'\n')
    manifest = j(bundle/'manifest.json')
    manifest['budget'] = spec
    for row in manifest['files']:
        path = bundle/row['path']
        row.update(bytes=path.stat().st_size, sha256=sha(path))
    (bundle/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    parent = ROOT/'evidence/model_pl_A/20261024-cpu-opt-02-v1/candidate/readback-v1/manifest.json'
    prior = {r['path']: r for r in j(parent)['files']}
    config.update(remote='/var/lib/kv260-a12/tt10-00-cpu02-20261024-v2', manifest=manifest,
                  delta={r['path']: base64.b64encode(gzip.compress((bundle/r['path']).read_bytes())).decode()
                         for r in manifest['files'] if prior.get(r['path'], {}).get('sha256') != r['sha256']})
    config['delta']['control/preflight.json'] = base64.b64encode(gzip.compress((bundle/'control/preflight.json').read_bytes())).decode()
    data['configurations'] = [config]
    source = (ROOT/'platform/qwen35/a12/cpu01b_board_driver.py').read_text()
    source = source.replace('DATA = None', 'DATA = '+repr(data), 1)
    source = source.replace("parent=Path(DATA['parent'])", "parent=Path(config['parent'])").replace("DATA['parent_manifest_sha256']", "config['parent_manifest_sha256']")
    source = source.replace("('short_profile','natural_plain','natural_profile')", repr(('diag_exact','short_proxy','app_plain_1','app_plain_2','app_profile')))
    source = source.replace('def preflight():', 'def preflight(record=None):')
    source = source.replace('    result=json.loads(capture.getvalue())', "    result=json.loads(capture.getvalue())\n    if record is not None: save(record,result)\n    emit('PREFLIGHT_SUMMARY',no_users=result['scans'][-1]['no_users_gate'],scan_issues=result['scans'][-1].get('scan_issues'),lease=result['active_lease_exists'],module=result['module_present'],locks_free=not any(result['locks'].values()),gdm=result['gdm_state'])")
    source = source.replace("independent=preflight();save(root/'independent-postcheck.json',independent)", "time.sleep(5)\n        independent=preflight(root/'independent-postcheck.json')")
    source = source.replace("delayed=preflight();save(root/'delayed-postcheck.json',delayed)", "delayed=preflight(root/'delayed-postcheck.json')")
    # Unmodified gate predicates and bounded main; no process signals or automatic retry.
    script = "import json\nfrom pathlib import Path\nns={'__name__':'tt10_cpu02_retry_definitions'}\nexec(compile("+repr(source)+",'tt10_cpu02_retry_reviewed','exec'),ns)\n"
    script += """failed=Path('/var/lib/kv260-a12/tt10-00-cpu02-20261024-v1')
assert json.loads((failed/'manager-exit.json').read_text())['exit_code']==1
assert 'PROCESS_SCAN_INCOMPLETE_OR_WRONG_BOOT' in (failed/'manager.stderr.txt').read_text()
assert not (failed/'run-v1/s1').exists() and not (failed/'run-v1/result.json').exists()
scene=ns['preflight']()
assert not Path('/proc',str(json.loads((failed/'manager-exit.json').read_text())['pid'])).exists()
ns['emit']('FAILED_CPU02_READONLY_SCENE',preflight=scene,failed_window_preserved=True,PL_compute_started=False)
raise SystemExit(ns['main']())
"""
    compile(script, 'cpu02 retry', 'exec')
    (OUT/'board_retry03_reviewed.py').write_text(script, encoding='utf-8', newline='\n')
    compiled = 0
    for path in bundle.rglob('*.py'):
        compile(path.read_text(encoding='utf-8'), str(path), 'exec')
        compiled += 1
    save(OUT/'CPU02_RETRY_REVIEW.json', dict(status='PASS_PC_DIAGNOSTIC_ONLY_DELTA', compiled_python_files=compiled,
        bundle='cpu02/bundle-v2', native_unchanged=sha(bundle/'bin/qwen35-a12')==sha(OUT/'cpu02/bundle-v1/bin/qwen35-a12'),
        safety_gate_conditions_unchanged=True, original_file_restored_byte_exact_after_removing_one_record_line=True,
        added_line=added.strip(), automatic_retries=False, failed_initial_scan_details='UNKNOWN_NOT_SAVED_BY_PARENT',
        failure_before_workers_and_PL_mutation=True, script_sha256=sha(OUT/'board_retry03_reviewed.py')))
    print('CPU02_RETRY_DIAGNOSTIC_ONLY_REVIEW_PASS')


if __name__ == '__main__':
    main()
