"""Derive callable candidate phases from sealed v1; no board execution/packaging.

Every unchanged safety helper and acquisition gate is copied exactly. New
window/boot/baseline/artifacts must be bound separately after board recovery.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OLD = ROOT / 'platform/qwen35/a13/codec_board_muted/board_manager.py'
PIN = '919e7849a8265ca1e5b55ff7d3214387b92aeef652881b23d320f6e6679404c4'
E = ROOT / 'evidence/a13_A/20261025-muted-control-repair-v1'


def derive(raw):
    if hashlib.sha256(raw).hexdigest() != PIN:
        raise ValueError('Original sealed manager changed')
    source = raw.decode('utf-8')
    tree = ast.parse(source)
    main = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'main')
    original_main = ast.get_source_segment(source, main)
    prefix, work = original_main.split('    try:\n        FW.mkdir(mode=0o755)', 1)
    prefix = prefix.replace('def main():', 'def candidate_prepare():', 1)
    prefix = prefix.replace('    global LEASE_SHA\n', '    global LEASE_SHA, raw\n', 1)
    prefix = prefix.replace("'window': 'a13-muted-20261025-v1'", "'window': REQUEST['window']")
    work = '        FW.mkdir(mode=0o755)' + work
    work = work.split('    except Exception as exc:', 1)[0]
    archive_name = "'history/a13-muted-20261025-v1-completed'"
    if work.count(archive_name) != 1:
        raise ValueError('Original normal archive marker changed')
    work = work.replace(archive_name, "('history/' + REQUEST['window'] + '-completed')")
    markers = [
        '        FW.mkdir(mode=0o755)',
        "        lease(); save('remove-default-reserved.json'",
        "        MUTED.mkdir(); save('load-muted-reserved.json'",
        '        # Deferred ASoC probe publication',
        "        pcm_cycle(1, 'drain'",
        "        pcm_cycle(2, 'drop'",
        "        save('before-normal-cleanup.json'",
    ]
    starts = []
    for marker in markers:
        if work.count(marker) != 1:
            raise ValueError('Phase marker no longer unique: ' + marker)
        starts.append(work.index(marker))
    if starts != sorted(starts):
        raise ValueError('Phase ordering changed')
    names = ('install', 'remove_default', 'apply_muted', 'bind', 'drain', 'drop', 'cleanup')
    functions = [prefix]
    for index, name in enumerate(names):
        chunk = work[starts[index]:starts[index + 1] if index + 1 < len(starts) else len(work)]
        # All cross-phase locals become explicit shared candidate context.
        body = '\n'.join(line[4:] if line.startswith('    ') else line for line in chunk.rstrip().splitlines())
        if name == 'bind':
            body = body.replace('    while True:\n', '    while True:\n        CONTROL.checkpoint()\n')
        functions.append('def candidate_' + name + '():\n    global raw, paths, index, device\n' + body + '\n')
    # Keep only imports/constants and unmodified helpers before main. No main
    # guard, no invocation, no board request, no future upload package.
    helpers = source[:source.index(original_main)]
    lease_marker = "    assert sha(CENTRAL / 'active/lease.json') == LEASE_SHA\n"
    if helpers.count(lease_marker) != 1:
        raise ValueError('Lease hook mismatch')
    helpers = helpers.replace(lease_marker, lease_marker + '    CONTROL.checkpoint()\n')
    result = helpers + '\n\n' + '\n\n'.join(functions)
    ast.parse(result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=int, choices=range(1, 10), default=1)
    args = parser.parse_args()
    out = E / ('derived-%02d' % args.attempt)
    result = derive(OLD.read_bytes())
    out.mkdir(exist_ok=False)
    target = out / 'candidate_core.py'
    target.write_text(result, encoding='utf-8')
    manifest = dict(original_sha256=PIN, derived_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                    copied_acquisition_gates=True, BOARD='NOT_TESTED', runnable_board_entry=False,
                    old_boot_and_paths='INHERITED_NOT_VALID_FOR_NEW_WINDOW_MUST_REBIND_AFTER_RECOVERY',
                    phases=['prepare', 'install', 'remove_default', 'apply_muted', 'bind', 'drain', 'drop', 'cleanup'])
    with (out / 'INPUTS.json').open('x', encoding='utf-8') as stream:
        json.dump(manifest, stream, indent=2)
    print(json.dumps(manifest))


if __name__ == '__main__':
    main()
