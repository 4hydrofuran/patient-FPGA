"""PC执行真实派生C拒绝条件，保留旧u64回绕反例；不是AXI DMA系统仿真。"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[4]
E = ROOT / 'evidence/a13_A/20261025-audio-codec-master-v1'


def guard(text):
    begin = text.index('/* A13 fixed 1024-byte periods')
    begin = text.index('if (', begin)
    end = text.index('return NULL;', begin) + len('return NULL;')
    return text[begin:end]


def main():
    out = E / 'dma-guard-pc'
    out.mkdir(exist_ok=False)
    spec = importlib.util.spec_from_file_location('reviewed_private_dma', Path(__file__).resolve().parent / 'prepare_dma.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    os.chdir(out)
    module.main()
    old = E / 'module-candidates-v4-v2/modules/a13_period_dma.c'
    new = out / 'modules/a13_period_dma.c'
    vectors = [
        (0, 2048, 1024, 1), ((1 << 32) - 2048, 2048, 1024, 1),
        ((1 << 32) - 2044, 2048, 1024, 0), (1 << 32, 2048, 1024, 0),
        ((1 << 64) - 2048, 4096, 1024, 0), (0x1001, 2048, 1024, 0),
        (0, 2048, 0, 0), (0, 2048, 512, 0), (0, 1024, 1024, 0),
        (0, 1024 * 65, 1024, 0), (0, 2049, 1024, 0)]
    commands = []
    for name, path, expected in [('old', old, 1), ('fixed', new, 0)]:
        condition = guard(path.read_text(encoding='utf-8'))
        source = ('#include <stdint.h>\n#include <stddef.h>\n#include <stdio.h>\n'
                  'typedef uint64_t u64;\nstatic void *test_guard(uint64_t buf_addr,size_t buf_len,size_t period_len) {\n' +
                  condition + '\nreturn (void *)(uintptr_t)1;\n}\nint main(void) {\n')
        for index, (address, length, period, wanted) in enumerate(vectors):
            source += ('if ((test_guard({}ULL,{}ULL,{}ULL)!=NULL)!={}) '
                       '{{puts("FAIL vector={}");return 1;}}\n').format(address, length, period, wanted, index)
        source += 'puts("PASS DMA_GUARD_PC checks=11 NOT_FULL_DMA_COSIM");return 0;}\n'
        cfile = out / (name + '.c')
        cfile.write_text(source, encoding='utf-8')
        for argv, code in [(['gcc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror', str(cfile), '-o', str(out / name)], 0),
                            ([str(out / name)], expected)]:
            run = subprocess.run(argv, capture_output=True, text=True)
            record = {'argv': argv, 'exit_code': run.returncode, 'expected_exit_code': code,
                      'stdout': run.stdout, 'stderr': run.stderr}
            commands.append(record)
            (out / 'COMMANDS.json').write_text(json.dumps(commands, indent=2) + '\n', encoding='utf-8')
            assert run.returncode == code, record
    result = {'status': 'PASS_PC_ACTUAL_DMA_GUARD_OLD_OVERFLOW_REPRODUCED', 'checks': 11,
              'old_exit_code': 1, 'fixed_exit_code': 0,
              'old_source_sha256': hashlib.sha256(old.read_bytes()).hexdigest(),
              'fixed_source_sha256': hashlib.sha256(new.read_bytes()).hexdigest(),
              'BOARD': 'NOT_TESTED', 'full_DMA_cosimulation': 'NOT_TESTED'}
    (out / 'RESULT.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
