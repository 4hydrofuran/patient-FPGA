"""Extract and cross-check the actual frozen XO and compile its private ABI layout."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

from b04_common import ROOT, FLAGS, compiler, digest, now, read_json, run, write_json

NAMES = ['w_packed', 'sw', 'xq', 'sx', 'y', 'meta', 't', 'n', 'k', 'w_bytes', 'sw_bytes',
         'x_bytes', 'sx_bytes', 'y_bytes', 'meta_bytes', 'job_id', 'abi_version']
FIELDS = [('abi_magic', 0, 4), ('kernel_build_id', 4, 4), ('job_id', 8, 8), ('status', 16, 4),
          ('done', 20, 4), ('hw_completed_count', 24, 8), ('algorithm_weight_bytes', 32, 8)]
ROLES = ['weight_input', 'weight_scale_input', 'activation_input', 'activation_scale_input',
         'output', 'completion_record']


def build(args):
    candidate = read_json(ROOT / 'artifact/b03_candidate/candidate.json')
    locked = read_json(ROOT / 'contracts/contract_lock.json')
    files = {name: digest(ROOT / 'contracts' / name) for name in locked['files']}
    if any(files[name] != expected for name, expected in locked['files'].items()):
        raise RuntimeError('Frozen public contract changed')
    source_checks = {
        'src/w4a8_prefill_v1.cpp': candidate['artifact']['source_sha256'],
        'src/w4a8_linear_v1.hpp': candidate['artifact']['header_sha256'],
        'artifact/b03_candidate/w4a8_linear_v1.xo': candidate['artifact']['xo_sha256'],
        'artifact/b03_candidate/kernel.xml': candidate['artifact']['kernel_xml_sha256'],
    }
    receipt = read_json(ROOT / candidate['artifact']['synthesis_receipt'])
    source_checks['hls_prefill_double.cfg'] = receipt['input_sha256']['hls_prefill_double.cfg'].lower()
    for name, expected in source_checks.items():
        if digest(ROOT / name).lower() != expected.lower():
            raise RuntimeError('Selected frozen input changed: ' + name)
    xo = ROOT / 'artifact/b03_candidate/w4a8_linear_v1.xo'
    with zipfile.ZipFile(xo) as archive:
        if archive.testzip():
            raise RuntimeError('XO CRC failed')
        xml_data = archive.read('w4a8_linear_v1/kernel.xml')
    delivery_xml = (ROOT / 'artifact/b03_candidate/kernel.xml').read_bytes()
    canonical = ET.canonicalize(xml_data.decode('utf-8'), strip_text=True)
    if canonical != ET.canonicalize(delivery_xml.decode('utf-8'), strip_text=True):
        raise RuntimeError('XO embedded XML meaning differs from delivery XML')
    kernel = ET.fromstring(xml_data).find('kernel')
    ports = {port.attrib['name']: int(port.attrib['dataWidth']) for port in kernel.find('ports')}
    xml_args = [dict(arg.attrib) for arg in kernel.find('args')]
    if [arg['name'] for arg in xml_args] != NAMES or [int(arg['id']) for arg in xml_args] != list(range(17)):
        raise RuntimeError('Frozen parameter order changed')
    if kernel.attrib['hwControlProtocol'] != 'ap_ctrl_hs':
        raise RuntimeError('Control protocol mismatch')
    if xml_args[2]['port'] != xml_args[3]['port']:
        raise RuntimeError('X and Sx must retain the frozen shared memory interface')
    work = ROOT / args.work
    work.mkdir(parents=True, exist_ok=False)
    cxx, extra, env = compiler(args.cxx)
    suffix = '.exe' if os.name == 'nt' else ''
    executable = work / ('layout_probe' + suffix)
    compile_args = [cxx, *extra, '-std=c++17', '-O2', *FLAGS,
                    'tests/b04/layout_probe.cpp', '-o', executable.relative_to(ROOT).as_posix()]
    _, compiled = run(compile_args, ROOT, work / 'compile.log', env)
    text, executed = run([str(executable.resolve())], ROOT, work / 'layout.log', env)
    layout = json.loads(text)
    expected_offsets = {name: offset for name, offset, _ in FIELDS}
    if layout['meta_bytes'] != 40 or layout['build_id'] != 0xB3030002 or layout['magic'] != 0x57344138 or layout['offsets'] != expected_offsets:
        raise RuntimeError('Compiled real kernel ABI layout differs')
    arguments = []
    for arg in xml_args:
        index = int(arg['id'])
        pointer = int(arg['addressQualifier']) == 1
        arguments.append({
            'index': index, 'name': arg['name'], 'kind': 'BO' if pointer else 'scalar',
            'control_offset': int(arg['offset'], 16), 'control_bytes': int(arg['size'], 16),
            'port': arg['port'], 'port_width_bits': ports[arg['port']],
            'role': ROLES[index] if pointer else 'control_input',
            'runtime_memory_group': None,
            'memory_group_rule': 'Query matching loaded xclbin metadata for this argument; do not equate argument index with bank number' if pointer else None,
        })
    profile = {
        'schema_version': 1, 'candidate': 'B03_double', 'kernel_name': kernel.attrib['name'],
        'build_id': layout['build_id'], 'build_id_hex': '0xB3030002', 'private_abi_version': 1,
        'public_api_version': 1, 'public_contract_sha256': locked['contract_sha256'],
        'part': 'xck26-sfvc784-2LV-c', 'hls_clock_target_ns': 6.667,
        'compile_options': kernel.attrib['compileOptions'],
        'hls_estimates': candidate['nominal']['synthesis'],
        'xo_sha256': candidate['artifact']['xo_sha256'], 'frozen_files': source_checks,
        'embedded_kernel_xml_sha256': hashlib.sha256(xml_data).hexdigest(),
        'kernel_xml_semantic_sha256': hashlib.sha256(canonical.encode('utf-8')).hexdigest(),
        'control_protocol': 'ap_ctrl_hs', 'arguments': arguments,
        'meta': {'bytes': 40, 'endianness': 'little', 'magic': layout['magic'],
                 'fields': [{'name': name, 'offset': offset, 'bytes': width} for name, offset, width in FIELDS],
                 'done_means': 'call finished, including errors; success additionally requires private status zero',
                 'counter_storage': 'meta BO memory, read and updated by kernel; not a persistent device-global register'},
        'buffer_minimum_bytes': {'w_packed': 'Np*Kp/2', 'sw': 'Np*(Kp/128)*4', 'xq': 'T*Kp',
                                 'sx': 'T*4', 'y': 'T*Np*4', 'meta': 40},
        'dimensions': {'T': [1, 8], 'N': [1, 4864], 'K': [1, 4864], 'N_alignment': 32, 'K_alignment': 128},
        'private_to_public_status': {'0': 0, '1': 2, '2': 1, '3': 3, '4': 1, '5': 9},
        'private_status_mapping_owner': 'B supplies conformance rules; A owns runtime translation/isolation',
        'data_sync': {'host_to_device': ['w_packed', 'sw', 'xq', 'sx', 'meta_initial_state'],
                      'device_to_host': ['meta_before_consuming_y', 'y_only_after_valid_success']},
        'hardware_measurements': {'runtime_memory_groups': None, 'measured_bus_bytes': None, 'board_latency_ms': None},
        'readiness': {'B_profile': 'PASS', 'XRT_runtime': 'WAITING_A', 'implementation': 'NOT_TESTED',
                      'ARM64_runtime': 'NOT_TESTED', 'BOARD': 'NOT_TESTED'},
    }
    write_json(ROOT / 'config/b04/kernel_profile.json', profile)
    report = {'status': 'PASS', 'finished_at': now(), 'candidate': 'double',
              'profile_sha256': digest(ROOT / 'config/b04/kernel_profile.json'),
              'frozen_inputs': source_checks, 'contract_files': files,
              'compiled_layout': layout, 'steps': {'compile': compiled, 'run': executed},
              'xml_comparison': 'XML canonicalization, strip formatting whitespace; all elements/attributes preserved',
              'embedded_xml_raw_sha256': hashlib.sha256(xml_data).hexdigest(),
              'input_sha256': {name: digest(ROOT / name) for name in ('tests/b04/layout_probe.cpp', 'host/b04_private_probe.hpp', 'tools/b04_profile.py', 'tools/b04_common.py')},
              'scope': 'Frozen XO/XML identity and actual C++ layout; no XRT, implementation, ARM runtime or BOARD proof.'}
    write_json(ROOT / args.receipt, report)
    print('PASS B04 frozen profile: 17 arguments, shared X/Sx, meta40 and compiled layout')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cxx', default='g++')
    parser.add_argument('--work', default='build/b04/profile')
    parser.add_argument('--receipt', default='reports/b04/profile.receipt.json')
    build(parser.parse_args())
