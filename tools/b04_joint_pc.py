"""Rebuild unchanged A host/meta/control tests and B's independent fixture on PC.

Windows uses a visibly test-only OS lock adapter and the real OpenSSL DLL.
It does not establish Linux flock flags, ARM execution, XRT or BOARD behavior.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from b04_common import ROOT, FLAGS, compiler, digest, now, read_json, run, write_json


def execute(args):
    delivery = (ROOT / args.delivery).resolve()
    work = (ROOT / args.work).resolve()
    work.mkdir(parents=True, exist_ok=False)
    cxx, extra, env = compiler(args.cxx)
    suffix = '.exe' if os.name == 'nt' else ''
    runtime = delivery / 'modules/linear_A/xrt'
    suite = delivery / 'platform/qwen35/a07'
    includes = ['-I' + str(delivery / 'contracts/qwen35'), '-I' + str(runtime),
                '-I' + str(delivery / 'third_party/nlohmann')]
    flags = ['-std=c++17', '-O2', '-fno-fast-math', '-ffp-contract=off', '-Wall', '-Wextra', '-Werror']
    steps = {}
    outputs = {}
    sources = {}

    def build(name, inputs, additional=()):
        executable = work / (name + suffix)
        command = [cxx, *extra, *flags, *includes, *map(str, inputs), *map(str, additional), '-o', str(executable)]
        _, steps[name + '_compile'] = run(command, ROOT, work / (name + '_compile.log'), env, 180)
        for path in inputs:
            sources[str(Path(path).relative_to(ROOT).as_posix())] = digest(path)
        return executable

    executable = build('host_rules', [suite / 'test_host.cpp', runtime / 'host_contract.cpp'])
    output, steps['host_rules_run'] = run([str(executable), str(delivery)], work, work / 'host_rules.log', env)
    outputs['host_rules'] = json.loads(output)
    if outputs['host_rules'].get('assertions') != 970:
        raise ValueError('Expected original 970 host-rule assertions')

    executable = build('meta_replay', [suite / 'b04/meta_replay.cpp', runtime / 'host_contract.cpp'])
    output, steps['meta_replay_run'] = run([str(executable), str(ROOT / 'vectors/b04_meta')], work,
                                        work / 'meta_replay.log', env)
    outputs['meta_replay'] = json.loads(output)
    if outputs['meta_replay'].get('actual_meta_records') != 66 or outputs['meta_replay'].get('tamper_rejections') != 396:
        raise ValueError('Expected original 66 meta records and 396 rejection probes')

    control_inputs = [suite / 'control/test_api.cpp', runtime / 'backend.cpp', runtime / 'host_contract.cpp']
    additional = ['-DSP_LINEAR_CONTROL_TEST=1', '-I' + str(suite / 'control/stubs'), '-pthread']
    native_adapter = None
    if os.name == 'nt':
        crypto = Path(args.crypto).resolve()
        if not crypto.is_file():
            raise FileNotFoundError('Supply an existing real OpenSSL 3 DLL; never install one implicitly')
        env['PATH'] = str(crypto.parent) + os.pathsep + env['PATH']
        control_inputs.append(ROOT / 'tests/b04/native/file_lock.cpp')
        additional.extend(['-I' + str(ROOT / 'tests/b04/native'), str(crypto)])
        native_adapter = {'scope': 'Windows PC control only; Linux O_NOFOLLOW/O_CLOEXEC/flock NOT_REEXECUTED',
                          'crypto_dll': str(crypto), 'crypto_sha256': digest(crypto),
                          'headers': {path.relative_to(ROOT).as_posix(): digest(path)
                                      for path in (ROOT / 'tests/b04/native').rglob('*.h')}}
    else:
        additional.append('-lcrypto')
    executable = build('control', control_inputs, additional)
    _, steps['control_run'] = run([sys.executable, str(suite / 'control/run_cases.py'), str(executable),
                                  str(work / 'control_cases')], work, work / 'control.log', env, 180)
    outputs['control'] = read_json(work / 'control_cases/SUMMARY.json')
    if outputs['control'].get('cases') != 29 or outputs['control'].get('checks') != 554:
        raise ValueError('Expected original 29 scenarios / 554 control assertions')

    # 普通 C++ 编译器不理解 HLS pragma；仅此固定核回放按已有 PC 入口忽略该类诊断。
    fixture = build('kernel_fixture', [ROOT / 'tests/numerical/fixture_replay.cpp', ROOT / 'src/w4a8_prefill_v1.cpp'],
                    [*FLAGS, '-Wno-unknown-pragmas'])
    output, steps['kernel_fixture_run'] = run([str(fixture)], ROOT, work / 'kernel_fixture.log', env)
    if 'fixture PASS transactions=3 output_checks=32' not in output:
        raise ValueError('Independent fixed golden fixture failed')
    outputs['kernel_fixture'] = {'transactions': 3, 'output_checks': 32,
                                 'execution': 'PC_NATIVE_FROZEN_KERNEL_INDEPENDENT_HAND_GOLDEN'}
    sources['tools/b04_joint_pc.py'] = digest(ROOT / 'tools/b04_joint_pc.py')
    sources['tools/b04_common.py'] = digest(ROOT / 'tools/b04_common.py')
    if native_adapter:
        sources.update(native_adapter['headers'])
    report = {'status': 'PASS', 'finished_at': now(), 'delivery': str(delivery),
              'outputs': outputs, 'steps': steps, 'source_sha256': sources,
              'native_adapter': native_adapter, 'new_sanitizer_run': False,
              'A_archived_sanitizers': 'REVIEW_SEPARATELY_ORIGINAL_LINUX_EVIDENCE',
              'BOARD': 'NOT_TESTED', 'ARM_execution': 'NOT_TESTED',
              'scope': 'Actual unchanged A host rules/parser/backend control tests, existing XRT doubles. Numeric kernel fixture is separate PC execution, not end-to-end FPGA.'}
    write_json(ROOT / args.receipt, report)
    print('PASS B04 PC joint checks: host970 meta66/tamper396 control29/check554 fixture3/output32', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--delivery', default='evidence/b04/a07_received_20261021')
    parser.add_argument('--cxx', default='g++')
    parser.add_argument('--crypto', default='')
    parser.add_argument('--work', default='build/b04/joint_20261021/pc')
    parser.add_argument('--receipt', default='reports/b04/joint_20261021/pc.json')
    execute(parser.parse_args())
