"""PC-only derivatives for the single approved A11 execution and readback."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'evidence/mlp_board_A/20261023-integration-v1/execution-host-v1'


def main():
    OUT.mkdir(exist_ok=False)
    def put(name,text):
        with (OUT/name).open('x',encoding='utf-8',newline='\n') as f:f.write(text)
    put('launch_mlp_once.py',(ROOT/'platform/qwen35/a11/launch_mlp_once.py').read_text())
    text=(ROOT/'platform/qwen35/a10/isolated_prepare_uart.ps1').read_text()
    text=text.replace("'network','network_readback','root_stage','normal_poweroff','candidate_readonly','execute_idle'","'execute_idle'")
    text=text.replace("'launch_isolated_idle_once.py'","'launch_mlp_once.py'")
    text=text.replace("A10_ISOLATED_PREPARATION_UART_V1","A11_EXECUTION_UART_V1")
    text=text.replace("A10_ISOLATED_AUTH","A11_EXECUTION_AUTH")
    text=text.replace("[string]$ExpectedKernel='6.8.0-1036-xilinx'","[string]$ExpectedKernel='6.8.12-a10irq2'")
    text=text.replace("if($ValidateOnly){","if([Text.Encoding]::UTF8.GetByteCount($command) -gt 3900){throw 'Helper exceeds safe UART line budget'}\nif($ValidateOnly){")
    text=text.replace("compute=$false}","compute=$true}")
    text=text.replace("if($Step -eq 'execute_idle'){$report.pl_loads=$null}","if($Step -eq 'execute_idle'){$report.pl_loads=$null;$report.compute_runs=$null}")
    text=text.replace("RETAINED\"') 120","RETAINED\"') 360")
    put('execute_once.ps1',text)
    text=(ROOT/'platform/qwen35/a10/read_single_result.py').read_text()
    text=text.replace('/var/lib/kv260-a10/a10-isolated-single-20261023-v1','/var/lib/kv260-a11/a11-mlp-20261023-v1')
    text=text.replace('a10-isolated-single-20261023-v1','a11-mlp-20261023-v1')
    text=text.replace('c5baeabe-273d-447e-b323-ff07dd7af201','8422f92f-d01f-4849-ad19-6e66b640a9ad')
    text=text.replace('ae21f1acacadbf5ceaeed85384cade0c575fbe8a5a88012530c911ebfce7cfb7','3b3c46700f92565839abda962e07e557018b8fd1be9e7846613ff46ecf89f11c')
    text=text.replace('4 * 1024 * 1024','64 * 1024 * 1024')
    text=text.replace("'single-receipt.json'","'mlp-receipt.json', 'STOP.json', 'trial-profile.json', 'baseline.raw.txt'")
    marker="    lifecycle = root / 'lifecycle.jsonl'"
    text=text.replace(marker,"    for path in sorted((root/'outputs').glob('job-*.f32')):\n        assert not path.is_symlink()\n        files[str(path.relative_to(root))]=pack(path.read_bytes())\n"+marker)
    text=text.replace('A10_SINGLE_RESULT_READONLY_V1','A11_MLP_RESULT_READONLY_V1')
    put('read_single_result.py',text)
    text=(ROOT/'platform/qwen35/a10/fetch_single_result.py').read_text()
    text=text.replace("ROOT = Path(__file__).resolve().parents[3]","ROOT = Path('C:/Patientqwen')")
    text=text.replace('A10_READONLY_EVIDENCE_AUTH','A11_READONLY_EVIDENCE_AUTH')
    text=text.replace("        with (args.output / name).open('xb') as f:",
        "        if Path(name).is_absolute() or '..' in Path(name).parts:raise RuntimeError('unsafe capture path')\n        (args.output/name).parent.mkdir(parents=True,exist_ok=True)\n        with (args.output / name).open('xb') as f:")
    put('fetch_result.py',text)
    print(json.dumps(dict(board_contact=False,files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.iterdir()})))


if __name__=='__main__':main()
