"""PC-only pinned shutdown derivative for the observed original-system boot."""
import hashlib
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'evidence/mlp_board_A/20261023-integration-v1'
BOOT='f4a2ac41-8010-43ee-ad8a-3b89e05034be'

if __name__=='__main__':
    source=ROOT/'platform/qwen35/a10/shutdown_complete_uart.ps1'
    data=source.read_bytes()
    assert hashlib.sha256(data).hexdigest()=='6b9e28510a90864a89138777be23a7c90a86898e7d45945106fbd98198cc5083'
    text=data.decode().replace('c5baeabe-273d-447e-b323-ff07dd7af201',BOOT)
    text=text.replace('6.8.12-a10irq2','6.8.0-1036-xilinx').replace('A10_NORMAL_SHUTDOWN_V1','A11_PRE_IRQ2_NORMAL_SHUTDOWN_V1')
    target=OUT/'poweroff_original_once.ps1'
    with target.open('x',encoding='utf-8',newline='\n') as f:f.write(text)
    print(json.dumps(dict(path=str(target),sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                         board_contact=False,boot=BOOT,shutdown_commands=0)))
