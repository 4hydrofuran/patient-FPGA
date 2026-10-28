"""Replay saved complete PC bytes using Linux I/O; no model or board calls."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import time
from tt10_01_diag_reader import DiagnosticReader, NumericalStreams
from tt10_01_numeric import concatenated

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'evidence/model_pl_A/20261024-ttft10-01-v1/cma-reader-20261025-v1'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    if not args.name.startswith('replay-') or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in args.name):
        raise ValueError('fresh replay-* output name required')
    dest = OUT / args.name
    dest.mkdir(exist_ok=False)
    args.work.mkdir(mode=0o700, parents=True, exist_ok=False)
    source = ROOT / 'evidence/model_pl_A/20261024-ttft10-01-v1/pc-run-04/pc-new'
    names = {'warm_prefix': 'warm_70', 'diag_full_R0': 'full_R0', 'diag_hit': 'full_cache_70'}
    pins = {}
    for name, old in names.items():
        current = args.work / name / 'diag'
        current.mkdir(mode=0o700, parents=True)
        for p in sorted((source / old / 'diag').iterdir()):
            if not p.is_file() or p.is_symlink():
                raise ValueError('only complete original regular files accepted')
            q = current / p.name
            shutil.copyfile(p, q)
            q.chmod(0o600)
            h = hashlib.sha256()
            with q.open('rb') as f:
                for block in iter(lambda: f.read(1048576), b''):
                    h.update(block)
            pins[f'{name}/diag/{p.name}'] = dict(bytes=q.stat().st_size, sha256=h.hexdigest())
    old = concatenated(args.work / 'diag_full_R0', args.work / 'warm_prefix', args.work / 'diag_hit')
    counts = {}
    progress = {}
    def observe(event, **data):
        counts[event] = counts.get(event, 0) + 1
        if event == 'FILE_ADVISED':
            key = data['case'] + '/diag/' + data['file']
            progress[key] = progress.get(key, 0) + 1
    start = time.monotonic_ns()
    reader = DiagnosticReader(args.work, observe, expected_uid=os.getuid())
    try:
        joined, full = NumericalStreams(), NumericalStreams()
        ledgers = {}
        for name, streams in (('warm_prefix', joined), ('diag_full_R0', full), ('diag_hit', joined)):
            ledgers[name] = streams.scan(reader, name, completed=True, quiescent=True)
        candidate = full.compare(joined)
        reader.verify()
        assert candidate == old and candidate['equal']
        all_files = {name + '/diag/' + filename: entry for name, data in ledgers.items() for filename, entry in data['files'].items()}
        assert all_files == pins and all(n == 1 for n in progress.values()) and set(progress) == set(pins)
        total = dict(files=reader.total_files, bytes=reader.total_bytes)
    finally:
        reader.close()
    elapsed = (time.monotonic_ns() - start) / 1e9
    # Independent post-read hash: test verification only, never part of the runtime adapter.
    for name, old_name in names.items():
        for p in sorted((source / old_name / 'diag').iterdir()):
            h1, h2 = hashlib.sha256(), hashlib.sha256()
            for file, h in ((p, h1), (args.work / name / 'diag' / p.name, h2)):
                with file.open('rb') as f:
                    for block in iter(lambda: f.read(1048576), b''):
                        h.update(block)
            assert h1.hexdigest() == h2.hexdigest() == pins[f'{name}/diag/{p.name}']['sha256']
    mem = {s.split(':')[0]: int(s.split()[1]) for s in Path('/proc/meminfo').read_text().splitlines()}
    report = dict(status='PASS_PC_FULL_ORIGINAL_REPLAY_BYTE_EQUIVALENT', domain='PC_LINUX_REAL_FSYNC_FADVISE',
        source=str(source), independent_work_copy=str(args.work), source03_model_rerun=False, model_runs=0,
        same_all_comparison_fields=True, source_and_copy_bytes_unchanged=True, runtime_read_passes_per_file=1,
        total=total, file_advice_calls=len(progress), events=counts, runtime_replay_elapsed_s=elapsed,
        original_35s_board_performance_not_comparable=True,
        local_CMA_counters={k: mem.get(k) for k in ('CmaTotal', 'CmaFree')},
        board_CMA_recovery='NOT_TESTED', BOARD='NOT_TESTED', PL_calls=0, TTFT_board_s=None, task01_complete=False)
    for name, obj in (('RESULT.json', report), ('FILES.json', all_files), ('NUMERICAL.json', candidate)):
        with (dest / name).open('x', encoding='utf-8') as f:
            json.dump(obj, f, ensure_ascii=False, indent=2); f.write('\n')
    print(json.dumps(dict(status=report['status'], total=total, same_all_comparison_fields=True,
        board_CMA_recovery='NOT_TESTED', elapsed_s=elapsed)))


if __name__ == '__main__':
    main()
