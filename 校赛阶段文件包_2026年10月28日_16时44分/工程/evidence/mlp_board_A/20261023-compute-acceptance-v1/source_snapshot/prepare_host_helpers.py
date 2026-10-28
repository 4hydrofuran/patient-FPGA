"""Generate bounded A11 host helpers from reviewed A10 transport, PC only."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'evidence/mlp_board_A/20261023-integration-v1/host-v1'
PIN='3b3c46700f92565839abda962e07e557018b8fd1be9e7846613ff46ecf89f11c'


def main():
    OUT.mkdir(exist_ok=False)
    def put(name,text):
        with (OUT/name).open('x',encoding='utf-8',newline='\n') as f:f.write(text)
    src=ROOT/'platform/qwen35/a10/single_candidate_readonly.py'
    text=src.read_text()
    text=text.replace('/var/lib/kv260-a10/a10-isolated-single-20261023-v1','/var/lib/kv260-a11/a11-mlp-20261023-v1')
    text=text.replace('ae21f1acacadbf5ceaeed85384cade0c575fbe8a5a88012530c911ebfce7cfb7',PIN)
    text=text.replace('from single_compute_policy import','from mlp_policy import')
    put('candidate_readonly.py',text)
    put('stage_bundle.py',(ROOT/'platform/qwen35/a11/stage_bundle.py').read_text())
    put('native_probe.py',(ROOT/'platform/qwen35/a11/native_probe.py').read_text())
    src=ROOT/'platform/qwen35/a10/isolated_prepare_uart.ps1'
    text=src.read_text()
    text=text.replace("'network','network_readback','root_stage','normal_poweroff','candidate_readonly','execute_idle'",
                      "'root_stage','candidate_readonly','native_probe'")
    text=text.replace("@('root_stage','candidate_readonly','execute_idle')","@('root_stage','candidate_readonly','native_probe')")
    text=text.replace("'stage_isolated_idle.py'","'stage_bundle.py'").replace("'isolated_candidate_readonly.py'","'candidate_readonly.py'")
    text=text.replace("'execute_idle' {'launch_isolated_idle_once.py'}","'native_probe' {'native_probe.py'}")
    text=text.replace("'network','root_stage','normal_poweroff','candidate_readonly','execute_idle'","'root_stage','candidate_readonly','native_probe'")
    text=text.replace("A10_ISOLATED_PREPARATION_UART_V1","A11_PREPARATION_UART_V1")
    text=text.replace("A10_ISOLATED_AUTH","A11_PREPARATION_AUTH")
    text=text.replace("[string]$ExpectedKernel='6.8.0-1036-xilinx'","[string]$ExpectedKernel='6.8.12-a10irq2'")
    # Remove unreachable old mutation plans, rather than expose them in this A11 tool.
    a=text.index("if($Step -eq 'network'){");b=text.index("if($Step -in @('root_stage'",a)
    text=text[:a]+text[b:]
    a=text.index("if($Step -eq 'normal_poweroff'){");b=text.index('if($ValidateOnly)',a)
    text=text[:a]+text[b:]
    text=text.replace("if($ValidateOnly){", "if([Text.Encoding]::UTF8.GetByteCount($command) -gt 3900){throw 'Helper exceeds safe UART line budget'}\nif($ValidateOnly){")
    put('prepare_uart.ps1',text)
    print(json.dumps(dict(board_contact=False,files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.iterdir()})))


if __name__=='__main__':main()
