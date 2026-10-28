"""Summarize actual final-source ARM64 artifacts, exported ABI and ISA flags."""
import json
from pathlib import Path
import subprocess
import sys
from common import ROOT, EVIDENCE, sha, save


def main(work,llama=None,name='ARM_BUILD.json'):
    work=Path(work);rows={}
    llama=Path(llama) if llama else work/'llama'
    binaries=[work/'model/qwen35-a12',work/'model/libsp_linear_cpu.so',work/'libsp_linear_a12_trial.so']
    binaries += [llama/'bin'/s for s in ('libllama.so','libggml.so','libggml-base.so','libggml-cpu.so')]
    for p in binaries:
        header=subprocess.check_output(['readelf','-h',str(p)],text=True)
        dynamic=subprocess.check_output(['readelf','-d',str(p)],text=True)
        version=subprocess.check_output(['readelf','-V',str(p)],text=True)
        assert 'AArch64' in header
        if p.name.startswith('libsp_linear'):
            exports=subprocess.check_output(['nm','-D','--defined-only',str(p)],text=True)
            symbols=[s.split()[-1].split('@')[0] for s in exports.splitlines() if ' sp_linear_' in s]
            assert len(symbols)==6
        else:symbols=[]
        rows[p.name]=dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size,
            needed=[s.strip() for s in dynamic.splitlines() if 'NEEDED' in s],
            rpath=[s.strip() for s in dynamic.splitlines() if 'PATH' in s],symbols=symbols,
            header=header,version_requirements=version)
    commands=json.loads((llama/'compile_commands.json').read_text())
    assert all('-march=native' not in r['command'] and '-mcpu=native' not in r['command'] for r in commands)
    save(EVIDENCE/name,dict(status='CROSS_BUILD_PASS_NOT_EXECUTED',domain='CROSS_BUILD',
        workspace=str(work),files=rows,translation_units=len(commands),settings='unknown',BOARD='NOT_TESTED',
        final_sources={name:sha(Path('/home/member-a/qwen35-a05/source-v3')/name)
                       for name in ('src/llama-graph.cpp','ggml/src/ggml-cpu/ops.cpp','include/llama.h')},
        cpu_non_mlp_schedule='FINAL_A05_SOURCE_REBUILT_IN_FRESH_ARM_DIRECTORY',
        runtime_root='/opt/patient-qwen',board_root_assets='NOT_VERIFIED_THIS_ROUND'))
    print(json.dumps(dict(status='CROSS_BUILD_PASS_NOT_EXECUTED',artifacts=len(rows))))


if __name__=='__main__':main(*sys.argv[1:])
