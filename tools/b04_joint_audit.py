"""Independently audit pinned A files, real xclbin sections and routed evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile

from b04_a_preflight import inspect
from b04_common import ROOT, digest, now, read_json, run, safe_path, write_json


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit(args):
    delivery = (ROOT / args.delivery).resolve()
    work = (ROOT / args.work).resolve()
    work.mkdir(parents=True, exist_ok=False)
    steps = {}
    manifest = read_json(delivery / 'files.sha256.json')
    actual_names = {p.relative_to(delivery).as_posix() for p in delivery.rglob('*') if p.is_file()}
    require(actual_names == set(manifest) | {'files.sha256.json'}, 'Unexpected or missing A files')
    for name, expected in manifest.items():
        path = safe_path(delivery, name)
        require(path.stat().st_size == expected['bytes'] and digest(path) == expected['sha256'], 'A file mismatch: ' + name)
    provenance = read_json(delivery / 'a_delivery.json')
    source = read_json(delivery / 'source_manifest.json')
    require(provenance['source_revision'] == 'sha256:' + digest(delivery / 'source_manifest.json'), 'A source manifest identity mismatch')
    for name, expected in source.items():
        require(digest(safe_path(delivery, name)) == expected, 'A source mismatch: ' + name)
    preflight = inspect(delivery, args.readelf, ROOT / args.receipt_dir / 'a_preflight.json')
    implementation = delivery / 'reports/implementation'
    original = read_json(implementation / 'REVIEW.json')
    for name, expected in original['report_sha256'].items():
        require(digest(implementation / 'routed' / name) == expected, 'Routed report mismatch: ' + name)
    require(read_json(implementation / 'vivado.json')['exit_code'] == 0, 'A routed report tool failed')
    linked = read_json(delivery / 'reports/link/link.json')
    require(linked['exit_code'] == 0 and '--target' in linked['argv'] and 'hw' in linked['argv'], 'No successful actual hardware link')
    require(digest(delivery / 'artifacts/w4a8.xclbin') == original['xclbin_sha256'], 'Wrong xclbin')
    profile = read_json(ROOT / 'config/b04/kernel_profile.json')
    require(original['source_xo_sha256'] == profile['xo_sha256'] == digest(ROOT / 'artifact/b03_candidate/w4a8_linear_v1.xo'), 'Wrong source XO')

    sections = {'EMBEDDED_METADATA': ('RAW', 'xml'), 'IP_LAYOUT': ('JSON', 'json'),
                'GROUP_CONNECTIVITY': ('JSON', 'json'), 'CONNECTIVITY': ('JSON', 'json'),
                'GROUP_TOPOLOGY': ('JSON', 'json'), 'MEM_TOPOLOGY': ('JSON', 'json'),
                'BUILD_METADATA': ('JSON', 'json'), 'SYSTEM_METADATA': ('RAW', 'json'),
                'BITSTREAM': ('RAW', 'bit')}
    command = [args.xclbinutil, '--input', str(delivery / 'artifacts/w4a8.xclbin'), '--info']
    for name, (kind, extension) in sections.items():
        command.extend(['--dump-section', name + ':' + kind + ':' + str(work / (name + '.' + extension))])
    info, steps['actual_xclbin_extract'] = run(command, ROOT, work / 'xclbinutil.log', timeout=120)
    require(original['xclbin_uuid'] in info, 'Actual xclbin UUID differs')
    section_checks = {}
    for name, (kind, extension) in sections.items():
        path = work / (name + '.' + extension)
        if name == 'BITSTREAM':
            require(digest(path) == digest(delivery / 'artifacts/MPSoC_ext_platform.bit') == original['matching_files']['bit']['sha256'], 'Actual bitstream differs')
        elif name == 'EMBEDDED_METADATA':
            require(ET.canonicalize(from_file=path) == ET.canonicalize(from_file=implementation / (name + '.xml')), 'Embedded XML differs from A evidence')
        else:
            require(read_json(path) == read_json(implementation / (name + '.json')), 'Actual section differs: ' + name)
        section_checks[name] = {'sha256': digest(path), 'bytes': path.stat().st_size}

    kernel = ET.parse(work / 'EMBEDDED_METADATA.xml').find('.//kernel')
    with zipfile.ZipFile(ROOT / 'artifact/b03_candidate/w4a8_linear_v1.xo') as archive:
        raw = next(archive.read(name) for name in archive.namelist() if name.endswith('kernel.xml'))
    original_kernel = ET.fromstring(raw).find('.//kernel')
    if original_kernel is None and ET.fromstring(raw).tag == 'kernel':
        original_kernel = ET.fromstring(raw)
    require(kernel.get('name') == original_kernel.get('name') == 'w4a8_linear_v1', 'Kernel name differs')
    require(kernel.get('hwControlProtocol') == original_kernel.get('hwControlProtocol') == 'ap_ctrl_hs', 'Control protocol differs')
    arguments, originals = list(kernel.iter('arg')), list(original_kernel.iter('arg'))
    require(len(arguments) == len(originals) == 17, 'Not 17 kernel arguments')
    for got, expected in zip(arguments, originals):
        for field in ('name', 'id', 'port', 'size', 'offset', 'hostSize', 'addressQualifier', 'type'):
            require(got.get(field) == expected.get(field), 'Kernel argument differs: ' + field)
    ports = {p.get('name'): {key: p.get(key) for key in ('mode', 'dataWidth', 'portType')} for p in kernel.iter('port')}
    for port in original_kernel.iter('port'):
        require(ports[port.get('name')] == {key: port.get(key) for key in ('mode', 'dataWidth', 'portType')}, 'Kernel port differs')
    connections = read_json(work / 'GROUP_CONNECTIVITY.json')['group_connectivity']['m_connection']
    groups = {}
    for item in connections:
        index, group = int(item['arg_index']), int(item['mem_data_index'])
        require(int(item['m_ip_layout_index']) == 0 and (index not in groups or groups[index] == group), 'Conflicting group mapping')
        groups[index] = group
    require(groups == dict.fromkeys(range(6), 3), 'Pointer group mapping differs')
    ip = read_json(work / 'IP_LAYOUT.json')['ip_layout']['m_ip_data']
    require(len(ip) == 1 and ip[0]['m_ip_control'] == 'AP_CTRL_HS', 'Wrong compute-unit topology')
    hwh = delivery / 'artifacts/MPSoC_ext_platform.hwh'
    require(digest(hwh) == original['matching_files']['hwh']['sha256'], 'HWH hash differs')
    module = next(m for m in ET.parse(hwh).iter('MODULE') if m.get('INSTANCE') == 'w4a8_linear_v1_1')
    clock = next(p for p in module.iter('PORT') if p.get('NAME') == 'ap_clk')
    require(clock.get('CLKFREQUENCY') == '149998500', 'Actual kernel clock differs')

    timing = (implementation / 'routed/timing.rpt').read_text(encoding='utf-8')
    require('All user specified timing constraints are met.' in timing, 'Timing constraints not met')
    names = ('WNS_ns', 'TNS_ns', 'setup_failing_endpoints', 'setup_total_endpoints', 'WHS_ns', 'THS_ns',
             'hold_failing_endpoints', 'hold_total_endpoints', 'WPWS_ns', 'TPWS_ns', 'pulse_failing_endpoints', 'pulse_total_endpoints')
    values = timing.split('WNS(ns)', 1)[1].splitlines()[2].split()
    require(len(values) == 12, 'Unexpected timing table')
    summary = dict(zip(names, map(float, values)))
    require(summary == original['timing'], 'Timing summary differs')
    require(all(summary[name] >= 0 for name in ('WNS_ns', 'WHS_ns', 'WPWS_ns')), 'Negative implementation slack')
    require(all(summary[name] == 0 for name in ('TNS_ns', 'THS_ns', 'TPWS_ns', 'setup_failing_endpoints', 'hold_failing_endpoints', 'pulse_failing_endpoints')), 'Failing timing endpoints')
    checks = {name: int(count) for name, count in re.findall(r'checking ([a-z_]+) \((\d+)\)', timing)}
    require(len(checks) == 12 and not any(checks.values()), 'Timing-check failures')
    route = (implementation / 'routed/route_status.rpt').read_text(encoding='utf-8')
    errors = int(re.search(r'nets with routing errors[^:]*:\s*(\d+)', route)[1])
    fully = int(re.search(r'fully routed nets[^:]*:\s*(\d+)', route)[1])
    routable = int(re.search(r'of routable nets[^:]*:\s*(\d+)', route)[1])
    require(errors == 0 and fully == routable, 'Incomplete or erroneous routing')
    resources = {}
    utilization = (implementation / 'routed/utilization.rpt').read_text(encoding='utf-8')
    for name in ('MPSoC_ext_platform_wrapper', 'w4a8_linear_v1_1'):
        row = next(line for line in utilization.splitlines() if line.startswith('|') and line.split('|')[1].strip() == name)
        fields = ('total_LUT', 'logic_LUT', 'LUTRAM', 'SRL', 'FF', 'RAMB36', 'RAMB18', 'URAM', 'DSP')
        resources[name] = dict(zip(fields, (int(value.strip()) for value in row.split('|')[3:-1])))
    require(resources == original['resources'], 'Resource summary differs')
    diagnostics = {}
    for name, expected in (('drc', original['drc']), ('methodology', original['methodology'])):
        text = (implementation / 'routed' / (name + '.rpt')).read_text(encoding='utf-8')
        rows = re.findall(r'^\|\s*([A-Z]+-\d+)\s*\|\s*(Warning|Advisory|Critical Warning|Error)\s*\|[^\n]*\|\s*(\d+)\s*\|$', text, re.M)
        parsed = {rule: {'severity': severity, 'count': int(count)} for rule, severity, count in rows}
        require(parsed == expected and sum(int(n) for _, _, n in rows) == int(re.search(r'Checks found:\s*(\d+)', text)[1]), 'Unexpected implementation diagnostic')
        require(all(value['severity'] not in ('Error', 'Critical Warning') for value in parsed.values()), 'Critical implementation diagnostic')
        diagnostics[name] = parsed
    require('All paths are Safely Timed.' in (implementation / 'routed/cdc.rpt').read_text(encoding='utf-8'), 'CDC evidence differs')

    control = read_json(delivery / 'reports/control/REPORT.json')
    require(control['production_stubs_absent'] and control['target'] == 'Cortex-A53', 'Wrong production ARM build')
    build_sources = read_json(delivery / 'reports/control/source_manifest.json')
    control_build_inputs = read_json(delivery / 'reports/control/control-build-inputs.json')
    for name in ('modules/linear_A/xrt/backend.cpp', 'modules/linear_A/xrt/host_contract.cpp',
                 'modules/linear_A/xrt/host_contract.hpp', 'modules/linear_A/xrt/release_gate.hpp',
                 'platform/qwen35/a07/control/test_api.cpp'):
        require(digest(delivery / name) == control_build_inputs[name], 'Production/control build source differs: ' + name)
        if name in build_sources:
            require(digest(delivery / name) == build_sources[name]['sha256'], 'Original production source differs: ' + name)
    sanitizer_commands = {}
    for variant in ('control-normal', 'control-sanitized'):
        records = list((delivery / 'reports/control' / variant).glob('*/command.json'))
        require(len(records) == 29, 'A original control command coverage differs')
        results = []
        for path in records:
            record = read_json(path)
            require(record['exit_code'] == 0 and not record['stderr'].strip(), 'A original control/sanitizer command failed')
            result = json.loads(record['stdout'])
            require(result['domain'] == 'PC_CONTROL_DOUBLE_NOT_FPGA' and result['case'] == path.parent.name, 'Original control case identity differs')
            results.append(result)
        require(sum(result['checks'] for result in results) == 554, 'A original control assertion count differs')
        sanitizer_commands[variant] = {'scenarios': 29, 'assertions': 554, 'all_exit_zero': True}
    for name in ('libsp_linear_xrt_candidate.so', 'sp-linear-host'):
        require(digest(delivery / 'artifacts' / name) == control['artifacts'][name]['sha256'], 'ARM artifact differs from original build')
    for role in ('arm64_library', 'arm64_host'):
        raw = safe_path(delivery, provenance['artifacts'][role]['path']).read_bytes()
        require(all(token not in raw for token in (b'CONTROL_ONLY', b'CONTROL_TEST_DOUBLE', b'CONTROL_TEST_ONLY.lock')), 'Control stub leaked into production ARM')
        require(all(not name.startswith(('/mnt/', '/home/')) for name in preflight['binary_checks'][role + '_needed']), 'Absolute build dependency leaked')
    for summary_control in control['control']:
        require(summary_control['cases'] == 29 and summary_control['checks'] == 554 and summary_control['BOARD'] == 'NOT_TESTED', 'A control coverage differs')
    clean = read_json(delivery / 'reports/clean/REPORT.json')
    require(clean['status'] == 'PASS_CLEAN_DELIVERY_REBUILD' and clean['queue_job']['exit_code'] == 0 and clean['same_tests_ASAN_UBSAN'] == 'PASS', 'A clean rebuild or sanitizer evidence incomplete')
    build = read_json(delivery / 'reports/commands/control-v2-run.json')
    require(build['exit_code'] == 0 and json.loads(build['stdout'])['exit_code'] == 0, 'A SDK build command failed')
    build_output = ''.join((delivery / 'reports/control' / name).read_text(encoding='utf-8') for name in ('stdout.txt', 'stderr.txt'))
    require('-mcpu=cortex-a53' in build_output, 'No Cortex-A53 build flag evidence')
    platform = read_json(delivery / provenance['artifacts']['platform_profile']['path'])
    config = read_json(delivery / 'modules/linear_A/xrt/config.pending.json')
    require(platform['status'] == 'DEPLOYMENT_PENDING_BOARD' and platform['verified_bo_budget_bytes'] is None and config['allow_device_access'] is False, 'Unverified deployment must remain disabled')
    report = {'status': 'PASS_OFFLINE_ARTIFACT_AND_ORIGINAL_EVIDENCE_REVIEW', 'finished_at': now(),
              'A_files_verified': len(manifest) + 1, 'source_files_verified': len(source),
              'A_delivery_sha256': digest(delivery / 'a_delivery.json'), 'steps': steps,
              'input_sha256': {name: digest(ROOT / name) for name in
                               ('tools/b04_joint_audit.py', 'tools/b04_a_preflight.py', 'tools/b04_common.py',
                                'config/b04/kernel_profile.json')},
              'actual_xclbin_sections': section_checks, 'kernel_arguments': 17, 'logical_argument_groups': groups,
              'kernel_clock_hz': 149998500, 'timing': summary, 'resources': resources, 'diagnostics': diagnostics,
              'ARM64': {'mode': 'A_MATCHED_SDK_BUILD_REUSED_B_REAL_ELF_RECHECK',
                        'B_new_target_build': False, 'dependencies': control['dependencies'],
                        'A_clean_rebuild_byte_identity': clean['ARM64_rebuilt'],
                        'source_scope': 'Unchanged A production sources and exact delivered ARM artifacts'},
              'A_original_sanitizers': {'mode': 'PASS_REVIEWED_NOT_RERUN_ON_WINDOWS', 'commands': sanitizer_commands},
              'BOARD': 'NOT_TESTED', 'ARM_execution': 'NOT_TESTED', 'deployment': 'DISABLED_PENDING_BOARD',
              'limits': ['No new placement/routing or HLS/RTL run.', 'B re-extracted actual xclbin sections; routed reports are the hash-verified A run.',
                         'Original SDK libraries are external dependencies identified by A SHA256, not copied or executed here.',
                         'Linux lock security flags use original Linux evidence; Windows control rerun has a documented OS adapter.']}
    write_json(ROOT / args.receipt_dir / 'artifact_review.json', report)
    print('PASS B04 actual xclbin, A file/source closure, routed reports and actual ARM ELF review', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--delivery', default='evidence/b04/a07_received_20261021')
    parser.add_argument('--work', default='build/b04/joint_20261021/artifact_audit')
    parser.add_argument('--receipt-dir', default='reports/b04/joint_20261021')
    parser.add_argument('--readelf', required=True)
    parser.add_argument('--xclbinutil', required=True)
    audit(parser.parse_args())
